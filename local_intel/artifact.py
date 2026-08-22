"""DerivedArtifact contract and JSON Schema (§8).

Phase 0 uses this schema to exercise Ollama structured output and the hard
validator. The frozen `DerivedArtifact` contract is a Phase 1a deliverable
(§18 Phase 1a step 1); this is the minimal shape needed to measure whether
the models can produce structurally valid, source-grounded output at all.

Epistemic status of anything built here (§2):

    DERIVED -> CLAIM -> REQUIRES EVIDENCE

Never DERIVED -> TRUTH. A schema-valid artifact is not a supported claim
(§8 "What validation does not prove").
"""

from __future__ import annotations

import hashlib
import json

SCHEMA_VERSION = "v1"

# Legitimate abstention states (§8). A worker must be able to decline;
# it must never be forced into a diagnosis.
ABSTENTION_REASONS = [
    "insufficient_evidence",
    "contradictory_evidence",
    "ambiguous_evidence",
    "out_of_domain_input",
    "malformed_input",
    "evidence_outside_authority_boundary",
    "unable_to_determine",
]

CLASSIFICATIONS = [
    "single_failure",
    "cascade_from_single_root_cause",
    "multiple_independent_failures",
    "environment_or_infrastructure_failure",
    "no_failure_detected",
    "indeterminate",
]

HYPOTHESIS_STATUSES = ["likely", "uncertain", "unlikely"]

# §5 presentation security: cap hypothesis statement length.
MAX_STATEMENT_CHARS = 400
MAX_HYPOTHESES = 5
MAX_SPANS_PER_LIST = 8

SPAN_SCHEMA = {
    "type": "object",
    "properties": {
        "source_id": {"type": "string"},
        "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
    },
    "required": ["source_id", "start_line", "end_line"],
    "additionalProperties": False,
}

ARTIFACT_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {"type": "string", "enum": CLASSIFICATIONS},
        "hypotheses": {
            "type": "array",
            "maxItems": MAX_HYPOTHESES,
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string", "maxLength": MAX_STATEMENT_CHARS},
                    "supporting_spans": {
                        "type": "array",
                        "maxItems": MAX_SPANS_PER_LIST,
                        "items": SPAN_SCHEMA,
                    },
                    "contradicting_spans": {
                        "type": "array",
                        "maxItems": MAX_SPANS_PER_LIST,
                        "items": SPAN_SCHEMA,
                    },
                    "status": {"type": "string", "enum": HYPOTHESIS_STATUSES},
                },
                "required": [
                    "statement",
                    "supporting_spans",
                    "contradicting_spans",
                    "status",
                ],
                "additionalProperties": False,
            },
        },
        "abstention_reason": {
            "type": ["string", "null"],
            "enum": ABSTENTION_REASONS + [None],
        },
    },
    "required": ["classification", "hypotheses", "abstention_reason"],
    "additionalProperties": False,
}

# Fields a worker may never emit (§8 check 7, §2 laws 7/11/12). Presence of
# any of these is a hard rejection, not a warning: it is an attempt to
# expand authority or cause a side effect.
FORBIDDEN_KEYS = frozenset(
    {
        "tool_calls",
        "tool_call",
        "tools",
        "action",
        "actions",
        "command",
        "commands",
        "shell",
        "exec",
        "patch",
        "diff",
        "write",
        "writes",
        "file_write",
        "network",
        "fetch",
        "url",
        "mcp",
        "authority",
        "permissions",
        "escalate",
        "self_assessed_confidence",
    }
)


def schema_hash() -> str:
    """Content hash of the schema, for configuration identity (§9)."""
    canonical = json.dumps(ARTIFACT_SCHEMA, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
