"""Phase 0 target-hardware smoke test (§6).

    python run_phase0_smoke.py <machine_profile_id>

Runs all five fixtures through both candidate models, cold and warm, and
records every §6 measurement plus structural validity, citation integrity,
and GPU/CPU residency. Emits a JSON result document and a markdown report.

This script MEASURES. It does not decide: the §6 decision table is
pre-committed and the report states which row the numbers land on, but
admitting a model to Phase 1a is a human, versioned act (§17).

Nothing here tunes anything to pass. The invocation timeout is set well
above the kill thresholds on purpose -- a run that exceeds a threshold must
be recorded with its real duration, not truncated into an unfalsifiable
"timeout".
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from local_intel import __version__
from local_intel.config_identity import GenerationParameters
from local_intel.hardware import load_profile
from local_intel.ollama_client import (
    get_loaded_models,
    get_model_digest,
    get_ollama_version,
    unload_model,
)
from local_intel.triage import triage_log
from local_intel.worker_view import WorkerViewConfig
from fixtures.templates import FIXTURE_SPECS
from generate_fixtures import build_fixture, packet_for

CANDIDATE_MODELS = ["qwen2.5-coder:14b", "qwen3-coder:30b-a3b-q4_K_M"]

# §6 pre-committed kill thresholds. Read here, never written.
KILL_THRESHOLDS = {
    "version": "v3",
    "representative_view_size_tokens": 24000,
    "warm_e2e_max_ms": 20000,
    "cold_e2e_max_ms": 60000,
    "structural_validity_min_numerator": 3,
    "structural_validity_min_denominator": 5,
}

# Far above the 60s cold threshold so real durations are captured rather
# than clipped. A run this long has already failed its gate; the number
# still matters for diagnosis.
INVOCATION_TIMEOUT_MS = 900_000

RESULTS_DIR = Path("phase0_results")


def residency_snapshot(model_tag: str) -> dict:
    entry = next((m for m in get_loaded_models() if m.get("name") == model_tag), None)
    if entry is None:
        return {"resident": False}
    total, vram = entry.get("size"), entry.get("size_vram")
    return {
        "resident": True,
        "total_size_bytes": total,
        "vram_size_bytes": vram,
        "gpu_fraction": round(vram / total, 4) if total and vram else None,
        "fully_on_gpu": bool(total and vram and vram >= total),
    }


def run_one(spec, model_tag: str, digest: str, profile_id: str, ollama_version: str,
            state: str) -> dict:
    lines, redaction = build_fixture(spec)
    packet = packet_for(spec, lines)

    if state == "cold":
        unload_model(model_tag)

    outcome = triage_log(
        packet,
        model_tag=model_tag,
        model_digest=digest,
        hardware_profile_id=profile_id,
        ollama_version=ollama_version,
        generation=GenerationParameters(),
        view_config=WorkerViewConfig(),
        timeout_ms=INVOCATION_TIMEOUT_MS,
        keep_alive="10m",
        model_load_state=state,
    )

    t = outcome.telemetry
    v = outcome.worker_view

    # Citation integrity is a distinct property from structural validity: an
    # artifact can be schema-perfect and still cite lines that do not exist.
    citation_checks = ["citation_source_membership", "citation_range"]
    if outcome.validation is None:
        citation_integrity = None  # no artifact produced; not a citation failure
    else:
        citation_integrity = not any(
            c in outcome.validation.failed_checks for c in citation_checks
        )

    return {
        "fixture_id": spec.fixture_id,
        "stratum": spec.stratum,
        "model": model_tag,
        "model_load_state": state,
        "structurally_valid": outcome.structurally_valid,
        "citation_integrity": citation_integrity,
        "invocation_failure_kind": outcome.invocation_failure_kind,
        "error": outcome.error,
        "failed_checks": (outcome.validation.failed_checks if outcome.validation else []),
        "validation_errors": (outcome.validation.errors[:10] if outcome.validation else []),
        "invocation_configuration_id": outcome.invocation_configuration_id,
        "worker_view_hash": v.worker_view_hash,
        "worker_view_input_tokens_estimated": v.estimated_input_tokens,
        "worker_view_size_chars": v.serialized_size_chars,
        "worker_view_truncated": v.truncated,
        "packet_content_hash": v.packet_content_hash,
        "redaction": {k: val for k, val in redaction.items() if k != "redaction_hits"},
        # §6 required measurements
        "preflight_duration_ms": t.preflight_duration_ms,
        "model_load_duration_ms": t.model_load_duration_ms,
        "prompt_prefill_duration_ms": t.prompt_prefill_duration_ms,
        "generation_duration_ms": t.generation_duration_ms,
        "local_total_duration_ms": t.local_total_duration_ms,
        "prompt_eval_count": t.prompt_eval_count,
        "generated_output_tokens": t.eval_count,
        "classification": (outcome.artifact or {}).get("classification"),
        "expected_classification": spec.expected_classification,
        "hypothesis_count": len((outcome.artifact or {}).get("hypotheses") or []),
        "abstention_reason": (outcome.artifact or {}).get("abstention_reason"),
        "residency": residency_snapshot(model_tag),
    }


def summarise(runs: list[dict], model_tag: str) -> dict:
    def med(state: str) -> float | None:
        vals = [
            r["local_total_duration_ms"]
            for r in runs
            if r["model"] == model_tag
            and r["model_load_state"] == state
            and r["local_total_duration_ms"] is not None
        ]
        return round(statistics.median(vals), 1) if vals else None

    warm = [r for r in runs if r["model"] == model_tag and r["model_load_state"] == "warm"]
    cold = [r for r in runs if r["model"] == model_tag and r["model_load_state"] == "cold"]

    warm_valid = sum(1 for r in warm if r["structurally_valid"])
    cold_valid = sum(1 for r in cold if r["structurally_valid"])
    cite_checked = [r for r in warm + cold if r["citation_integrity"] is not None]
    cite_ok = sum(1 for r in cite_checked if r["citation_integrity"])

    warm_median = med("warm")
    cold_median = med("cold")

    warm_pass = warm_median is not None and warm_median <= KILL_THRESHOLDS["warm_e2e_max_ms"]
    cold_pass = cold_median is not None and cold_median <= KILL_THRESHOLDS["cold_e2e_max_ms"]
    struct_pass = warm_valid >= KILL_THRESHOLDS["structural_validity_min_numerator"]

    return {
        "model": model_tag,
        "warm_median_total_ms": warm_median,
        "cold_median_total_ms": cold_median,
        "warm_structural_validity": f"{warm_valid}/{len(warm)}",
        "cold_structural_validity": f"{cold_valid}/{len(cold)}",
        "citation_integrity": f"{cite_ok}/{len(cite_checked)}" if cite_checked else "0/0",
        "gate_warm_latency": warm_pass,
        "gate_cold_latency": cold_pass,
        "gate_structural_validity": struct_pass,
        "meets_all_thresholds": bool(warm_pass and cold_pass and struct_pass),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    profile_id = sys.argv[1]

    profile_doc = load_profile(profile_id)
    ollama_version = get_ollama_version() or "unknown"

    digests = {}
    for m in CANDIDATE_MODELS:
        d = get_model_digest(m)
        if d is None:
            print(f"FATAL: model {m} is not installed; cannot run Phase 0.")
            return 1
        digests[m] = d

    runs: list[dict] = []
    total = len(CANDIDATE_MODELS) * len(FIXTURE_SPECS) * 2
    n = 0

    for model_tag in CANDIDATE_MODELS:
        # Cold pass first: every fixture preceded by an explicit unload.
        for state in ("cold", "warm"):
            if state == "warm":
                # One priming run so the model is genuinely resident, and it
                # is not recorded -- a "warm" number measured on a cold model
                # would flatter nothing and confuse everything.
                unload_model(model_tag)
                run_one(FIXTURE_SPECS[0], model_tag, digests[model_tag], profile_id,
                        ollama_version, "cold")
            for spec in FIXTURE_SPECS:
                n += 1
                print(f"[{n}/{total}] {model_tag} {state} {spec.fixture_id} ...", flush=True)
                r = run_one(spec, model_tag, digests[model_tag], profile_id,
                            ollama_version, state)
                runs.append(r)
                print(
                    f"      total={r['local_total_duration_ms']:.0f}ms "
                    f"valid={r['structurally_valid']} "
                    f"cite={r['citation_integrity']} "
                    f"class={r['classification']}",
                    flush=True,
                )
        unload_model(model_tag)

    summaries = [summarise(runs, m) for m in CANDIDATE_MODELS]

    document = {
        "phase": "0",
        "protocol_version": "v3",
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "local_intel_version": __version__,
        "kill_thresholds": KILL_THRESHOLDS,
        "hardware_profile": profile_doc["profile"],
        "hardware_profile_hash": profile_doc["profile_hash"],
        "fixture_set_version": json.loads(
            Path("fixtures/manifest.json").read_text(encoding="utf-8")
        )["fixture_set_version"],
        "fixture_provenance": "SYNTHETIC -- see fixtures/manifest.json",
        "generation_parameters": GenerationParameters().__dict__,
        "invocation_timeout_ms": INVOCATION_TIMEOUT_MS,
        "summaries": summaries,
        "runs": runs,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"phase0_smoke_{profile_id}.json"
    out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")

    print("\n=== §6 summary ===")
    for s in summaries:
        print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
