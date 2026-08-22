"""Generate the deterministic redacted fixture corpus (§11).

    python generate_fixtures.py [--out DIR] [--check]

Templates, generator source, hashes and manifest live in THIS repository.
The generated .log files are written to a separate disposable repository
(default F:/local-intel-fixtures), which can be deleted and regenerated
byte-for-byte from what is committed here.

--check regenerates and compares against the committed manifest without
writing anything, so drift is detectable rather than merely unlikely.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from local_intel.packet import EvidencePacket
from local_intel.redaction import redact_lines, redaction_identity
from local_intel.worker_view import WorkerViewConfig, build_worker_view
from fixtures.templates import BUILDERS, FIXTURE_SPECS, FixtureSpec

DEFAULT_OUT = Path("F:/local-intel-fixtures")
MANIFEST_PATH = Path("fixtures/manifest.json")
FIXTURE_SET_VERSION = "v1"

# §7 eligibility interceptor thresholds -- a fixture that does not clear
# these would never reach the worker in the first place.
MIN_LINES = 4000
MIN_POST_DEDUPE_CHARS = 100_000


def build_fixture(spec: FixtureSpec) -> tuple[list[str], dict]:
    raw_lines = BUILDERS[spec.builder](spec.size_param)
    raw_text = "\n".join(raw_lines)
    redacted_lines, hit_counts = redact_lines(raw_lines)
    redacted_text = "\n".join(redacted_lines)
    identity = redaction_identity(raw_text, redacted_text)
    identity["redaction_hits"] = hit_counts
    return redacted_lines, identity


def packet_for(spec: FixtureSpec, lines: list[str]) -> EvidencePacket:
    return EvidencePacket(
        source_id=f"log:{spec.fixture_id}",
        kind="test_log",
        command=spec.command,
        environment={
            "os": "linux",
            "python": "3.11.9",
            "runner": "pytest-8.2.0" if spec.builder != "compiler_type" else "tsc-5.4.5",
            "ci": "synthetic-fixture",
        },
        lines=lines,
    )


def measure(spec: FixtureSpec) -> dict:
    lines, redaction = build_fixture(spec)
    packet = packet_for(spec, lines)
    view = build_worker_view(packet, WorkerViewConfig())

    post_dedupe_chars = sum(
        len(line) for line in {ln.strip() for ln in lines if ln.strip()}
    )

    return {
        "fixture_id": spec.fixture_id,
        "stratum": spec.stratum,
        "expected_classification": spec.expected_classification,
        "size_param": spec.size_param,
        "command": spec.command,
        "line_count": packet.line_count,
        "raw_chars": sum(len(ln) for ln in lines),
        "post_dedupe_chars": post_dedupe_chars,
        "packet_content_hash": packet.content_hash(),
        "worker_view_hash": view.worker_view_hash,
        "worker_view_estimated_tokens": view.estimated_input_tokens,
        "worker_view_truncated": view.truncated,
        "worker_view_group_count": view.group_count,
        "worker_view_deduplicated_occurrences": view.deduplicated_occurrence_count,
        "eligible": (
            packet.line_count >= MIN_LINES and post_dedupe_chars >= MIN_POST_DEDUPE_CHARS
        ),
        "redaction": redaction,
        "lines": lines,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    config = WorkerViewConfig()
    target = config.content_budget_tokens

    entries = []
    problems = []
    for spec in FIXTURE_SPECS:
        m = measure(spec)
        lines = m.pop("lines")
        entries.append(m)

        if not m["eligible"]:
            problems.append(
                f"{m['fixture_id']}: INELIGIBLE "
                f"(lines={m['line_count']}/{MIN_LINES}, "
                f"post_dedupe_chars={m['post_dedupe_chars']}/{MIN_POST_DEDUPE_CHARS})"
            )
        # "At the frozen target" means the view fills the content budget.
        # A view materially under budget is not at the target and would make
        # the smoke test measure a smaller prompt than §6 specifies.
        if m["worker_view_estimated_tokens"] < target * 0.98:
            problems.append(
                f"{m['fixture_id']}: view {m['worker_view_estimated_tokens']} tokens "
                f"is under the {target}-token content budget"
            )

        if not args.check:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"{m['fixture_id']}.log").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )

    manifest = {
        "fixture_set_version": FIXTURE_SET_VERSION,
        "generator": "generate_fixtures.py + fixtures/templates.py + fixtures/vocab.py",
        "provenance": "SYNTHETIC. §6 specifies five representative REAL test-log "
        "packets; these are deterministic synthetic logs matching realistic "
        "structure and size. Recorded as a deviation, not as satisfying §6 verbatim.",
        "worker_view_content_budget_tokens": target,
        "eligibility": {
            "min_lines": MIN_LINES,
            "min_post_dedupe_chars": MIN_POST_DEDUPE_CHARS,
        },
        "fixtures": entries,
    }

    for e in entries:
        flag = "ok " if e["eligible"] else "INELIGIBLE"
        print(
            f"{flag} {e['fixture_id']:<26} lines={e['line_count']:>6} "
            f"groups={e['worker_view_group_count']:>6} "
            f"view_tokens={e['worker_view_estimated_tokens']:>6} "
            f"trunc={str(e['worker_view_truncated']):<5} "
            f"post_dedupe_chars={e['post_dedupe_chars']:>8}"
        )

    if args.check:
        if not MANIFEST_PATH.exists():
            print("\nNo committed manifest to check against.")
            return 1
        committed = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        drifted = []
        by_id = {e["fixture_id"]: e for e in committed["fixtures"]}
        for e in entries:
            old = by_id.get(e["fixture_id"])
            if not old:
                drifted.append(f"{e['fixture_id']}: not in committed manifest")
            elif old["packet_content_hash"] != e["packet_content_hash"]:
                drifted.append(f"{e['fixture_id']}: packet_content_hash drifted")
            elif old["worker_view_hash"] != e["worker_view_hash"]:
                drifted.append(f"{e['fixture_id']}: worker_view_hash drifted")
        if drifted:
            print("\nDRIFT:")
            for d in drifted:
                print("  " + d)
            return 1
        print("\nAll fixture hashes match the committed manifest.")
        return 0

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(entries)} logs to {args.out}")
    print(f"Wrote manifest to {MANIFEST_PATH}")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  " + p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
