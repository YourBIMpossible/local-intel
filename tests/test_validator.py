import copy

import pytest

from local_intel.validator import validate_artifact

VALID_ARTIFACT = {
    "classification": "cascade_from_single_root_cause",
    "hypotheses": [
        {
            "statement": "An unmapped OriginSystem field may be the earliest failure.",
            "supporting_spans": [
                {"source_id": "log:integration", "start_line": 18, "end_line": 31}
            ],
            "contradicting_spans": [],
            "status": "uncertain",
        }
    ],
    "abstention_reason": None,
}

GOOD_PROVENANCE = {
    "packet_content_hash": "abc",
    "packet_builder_version": "v1",
    "worker_view_builder_version": "v1",
    "truncation_strategy_version": "v1",
    "worker_view_hash": "def",
    "configured_num_ctx": 32768,
    "max_output_tokens": 1800,
}


def _validate(artifact, **overrides):
    kwargs = {
        "authorized_source_ids": {"log:integration"},
        "packet_line_count": 500,
        "provenance": GOOD_PROVENANCE,
        "authority_class": "DERIVED",
        "max_output_chars": 8000,
    }
    kwargs.update(overrides)
    return validate_artifact(artifact, **kwargs)


def test_valid_artifact_passes_all_checks():
    result = _validate(VALID_ARTIFACT)
    assert result.ok, result.errors
    assert result.failed_checks == []


def test_abstention_with_empty_hypotheses_is_valid():
    artifact = {
        "classification": "indeterminate",
        "hypotheses": [],
        "abstention_reason": "insufficient_evidence",
    }
    assert _validate(artifact).ok


def test_non_dict_artifact_rejected():
    result = _validate(["not", "an", "object"])
    assert not result.ok
    assert "schema_validity" in result.failed_checks


def test_unknown_classification_rejected():
    artifact = copy.deepcopy(VALID_ARTIFACT)
    artifact["classification"] = "definitely_a_bug"
    result = _validate(artifact)
    assert not result.ok
    assert "schema_validity" in result.failed_checks


def test_foreign_source_id_rejected():
    artifact = copy.deepcopy(VALID_ARTIFACT)
    artifact["hypotheses"][0]["supporting_spans"][0]["source_id"] = "log:some-other-packet"
    result = _validate(artifact)
    assert not result.ok
    assert "citation_source_membership" in result.failed_checks


def test_out_of_range_span_rejected():
    artifact = copy.deepcopy(VALID_ARTIFACT)
    artifact["hypotheses"][0]["supporting_spans"][0]["end_line"] = 9999
    result = _validate(artifact)
    assert not result.ok
    assert "citation_range" in result.failed_checks


def test_inverted_span_rejected():
    artifact = copy.deepcopy(VALID_ARTIFACT)
    artifact["hypotheses"][0]["supporting_spans"][0] = {
        "source_id": "log:integration",
        "start_line": 40,
        "end_line": 12,
    }
    result = _validate(artifact)
    assert not result.ok
    assert "citation_range" in result.failed_checks


@pytest.mark.parametrize(
    "forbidden_key", ["tool_calls", "shell", "patch", "self_assessed_confidence"]
)
def test_forbidden_fields_rejected(forbidden_key):
    artifact = copy.deepcopy(VALID_ARTIFACT)
    artifact["hypotheses"][0][forbidden_key] = "anything"
    result = _validate(artifact)
    assert not result.ok
    assert "forbidden_content" in result.failed_checks


def test_missing_provenance_rejected():
    bad = dict(GOOD_PROVENANCE)
    del bad["worker_view_hash"]
    result = _validate(VALID_ARTIFACT, provenance=bad)
    assert not result.ok
    assert "provenance" in result.failed_checks


def test_wrong_authority_class_rejected():
    result = _validate(VALID_ARTIFACT, authority_class="AUTHORITATIVE")
    assert not result.ok
    assert "authority_class" in result.failed_checks


def test_over_budget_artifact_rejected():
    result = _validate(VALID_ARTIFACT, max_output_chars=10)
    assert not result.ok
    assert "budget" in result.failed_checks


def test_all_failures_reported_at_once():
    artifact = copy.deepcopy(VALID_ARTIFACT)
    artifact["hypotheses"][0]["supporting_spans"][0]["source_id"] = "log:elsewhere"
    artifact["hypotheses"][0]["shell"] = "rm -rf /"
    result = _validate(artifact, authority_class="AUTHORITATIVE")
    assert not result.ok
    assert {"citation_source_membership", "forbidden_content", "authority_class"} <= set(
        result.failed_checks
    )
