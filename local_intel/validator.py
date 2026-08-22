"""Hard artifact validation (§8).

An artifact is presented only when ALL checks pass. This is a gate, not a
scoring function: there is no partial credit and no "mostly valid" state.

The eight required checks (§8 "Hard validation"):
  1. JSON Schema validity.
  2. Required provenance and configuration identity.
  3. Every source ID belongs to the submitted packet.
  4. Every cited span is in range.
  5. Every citation belongs to the authorized worker-view/source membership.
  6. Output fits configured budgets.
  7. No forbidden field, tool request, side-effect request, or
     authority-expansion content.
  8. Correct derived authority classification.

What passing does NOT establish (§8):

    schema valid      != citation supported
    citation exists   != claim correct
    claim plausible   != workflow useful
    workflow useful   != verified correct
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import jsonschema

from local_intel.artifact import (
    ARTIFACT_SCHEMA,
    FORBIDDEN_KEYS,
    MAX_STATEMENT_CHARS,
)

VALIDATOR_VERSION = "v1"

# §8 check 8: the artifact must declare itself derived, non-authoritative
# analysis. Any other value is a rejection -- a worker asserting a stronger
# authority class than DERIVED is exactly what law 7 forbids.
REQUIRED_AUTHORITY_CLASS = "DERIVED"

REQUIRED_PROVENANCE_FIELDS = (
    "packet_content_hash",
    "packet_builder_version",
    "worker_view_builder_version",
    "truncation_strategy_version",
    "worker_view_hash",
    "configured_num_ctx",
    "max_output_tokens",
)


@dataclass
class ValidationResult:
    ok: bool
    failed_checks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def fail(self, check: str, message: str) -> None:
        self.ok = False
        if check not in self.failed_checks:
            self.failed_checks.append(check)
        self.errors.append(f"[{check}] {message}")


def _walk_keys(node: Any):
    """Yield every key appearing anywhere in a nested JSON structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_keys(item)


def validate_artifact(
    artifact: Any,
    *,
    authorized_source_ids: set[str],
    packet_line_count: int,
    provenance: dict[str, Any],
    authority_class: str,
    max_output_chars: int,
) -> ValidationResult:
    """Run all eight §8 checks. Every check runs even after an earlier one
    fails, so a rejection report names every reason at once rather than
    forcing an iterate-and-rerun cycle."""
    result = ValidationResult(ok=True)

    # --- Check 1: JSON Schema validity -----------------------------------
    if not isinstance(artifact, dict):
        result.fail("schema_validity", f"artifact is {type(artifact).__name__}, not an object")
        # Every remaining check assumes a dict; nothing further is meaningful.
        return result

    schema_errors = sorted(
        jsonschema.Draft202012Validator(ARTIFACT_SCHEMA).iter_errors(artifact),
        key=lambda e: list(e.path),
    )
    for err in schema_errors:
        path = "/".join(str(p) for p in err.path) or "<root>"
        result.fail("schema_validity", f"{path}: {err.message}")

    # --- Check 2: required provenance and configuration identity ---------
    for f in REQUIRED_PROVENANCE_FIELDS:
        if f not in provenance or provenance[f] in (None, ""):
            result.fail("provenance", f"missing or empty provenance field: {f}")

    # --- Check 7: forbidden fields (run early; independent of schema) ----
    for key in _walk_keys(artifact):
        if key in FORBIDDEN_KEYS:
            result.fail(
                "forbidden_content",
                f"forbidden key present: {key!r} (tool/side-effect/authority-expansion)",
            )

    # --- Check 8: derived authority classification -----------------------
    if authority_class != REQUIRED_AUTHORITY_CLASS:
        result.fail(
            "authority_class",
            f"authority_class is {authority_class!r}, must be {REQUIRED_AUTHORITY_CLASS!r}",
        )

    # --- Checks 3/4/5: citation source membership and range --------------
    hypotheses = artifact.get("hypotheses")
    if isinstance(hypotheses, list):
        for h_idx, hypothesis in enumerate(hypotheses):
            if not isinstance(hypothesis, dict):
                continue

            statement = hypothesis.get("statement")
            if isinstance(statement, str) and len(statement) > MAX_STATEMENT_CHARS:
                result.fail(
                    "budget",
                    f"hypotheses/{h_idx}/statement exceeds {MAX_STATEMENT_CHARS} chars",
                )

            for span_kind in ("supporting_spans", "contradicting_spans"):
                spans = hypothesis.get(span_kind)
                if not isinstance(spans, list):
                    continue
                for s_idx, span in enumerate(spans):
                    if not isinstance(span, dict):
                        continue
                    loc = f"hypotheses/{h_idx}/{span_kind}/{s_idx}"

                    source_id = span.get("source_id")
                    if source_id not in authorized_source_ids:
                        # Checks 3 and 5 collapse to the same failure here:
                        # the only authorized membership in Phase 0 is the
                        # submitted packet's own source set.
                        result.fail(
                            "citation_source_membership",
                            f"{loc}: source_id {source_id!r} is not in the submitted packet",
                        )

                    start = span.get("start_line")
                    end = span.get("end_line")
                    if not isinstance(start, int) or not isinstance(end, int):
                        continue  # schema check already reported this
                    if start > end:
                        result.fail(
                            "citation_range",
                            f"{loc}: start_line {start} > end_line {end}",
                        )
                    if start < 1 or end > packet_line_count:
                        result.fail(
                            "citation_range",
                            f"{loc}: span {start}-{end} outside packet lines 1-{packet_line_count}",
                        )

    # --- Check 6: output fits configured budgets -------------------------
    import json as _json

    serialized_len = len(_json.dumps(artifact, ensure_ascii=False))
    if serialized_len > max_output_chars:
        result.fail(
            "budget",
            f"serialized artifact {serialized_len} chars exceeds budget {max_output_chars}",
        )

    return result
