import json
from pathlib import Path

import pytest

from fixtures.templates import FIXTURE_SPECS
from generate_fixtures import (
    MIN_LINES,
    MIN_POST_DEDUPE_CHARS,
    build_fixture,
    measure,
    packet_for,
)
from local_intel.worker_view import WorkerViewConfig, build_worker_view

MANIFEST = Path("fixtures/manifest.json")


@pytest.mark.parametrize("spec", FIXTURE_SPECS, ids=lambda s: s.fixture_id)
def test_fixture_generation_is_deterministic(spec):
    """Regeneration must be byte-identical or the manifest hashes are
    meaningless as reproducibility anchors."""
    a, _ = build_fixture(spec)
    b, _ = build_fixture(spec)
    assert a == b


@pytest.mark.parametrize("spec", FIXTURE_SPECS, ids=lambda s: s.fixture_id)
def test_fixture_clears_eligibility_interceptor(spec):
    """§7: a packet below these thresholds never reaches the worker, so a
    fixture below them cannot exercise the path under test."""
    m = measure(spec)
    assert m["line_count"] >= MIN_LINES
    assert m["post_dedupe_chars"] >= MIN_POST_DEDUPE_CHARS


@pytest.mark.parametrize("spec", FIXTURE_SPECS, ids=lambda s: s.fixture_id)
def test_worker_view_reaches_frozen_target(spec):
    """§6 pins the representative view size at 24000 tokens. A view well
    under budget would silently measure a smaller prompt than the smoke
    test claims to measure."""
    lines, _ = build_fixture(spec)
    view = build_worker_view(packet_for(spec, lines), WorkerViewConfig())
    budget = WorkerViewConfig().content_budget_tokens
    assert view.truncated
    assert budget * 0.98 <= view.estimated_input_tokens <= budget * 1.02


@pytest.mark.parametrize("spec", FIXTURE_SPECS, ids=lambda s: s.fixture_id)
def test_manifest_hashes_match_regeneration(spec):
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = next(e for e in committed["fixtures"] if e["fixture_id"] == spec.fixture_id)
    m = measure(spec)
    assert m["packet_content_hash"] == entry["packet_content_hash"]
    assert m["worker_view_hash"] == entry["worker_view_hash"]


def test_cascade_root_cause_survives_truncation():
    """The root cause is announced once, at the head of the log. Suffix-only
    truncation would delete it -- which would be a compressor-recall failure
    charged to the worker-view builder (§7), not a model failure."""
    spec = next(s for s in FIXTURE_SPECS if s.builder == "cascade_root_cause")
    lines, _ = build_fixture(spec)
    view = build_worker_view(packet_for(spec, lines), WorkerViewConfig())
    assert "a7f2_add_origin_system" in view.serialized_text
    assert "is missing column" in view.serialized_text


def test_environment_failure_root_cause_survives_truncation():
    spec = next(s for s in FIXTURE_SPECS if s.builder == "environment_failure")
    lines, _ = build_fixture(spec)
    view = build_worker_view(packet_for(spec, lines), WorkerViewConfig())
    assert "No space left on device" in view.serialized_text


@pytest.mark.parametrize("spec", FIXTURE_SPECS, ids=lambda s: s.fixture_id)
def test_redaction_ran_and_left_no_obvious_pii(spec):
    lines, identity = build_fixture(spec)
    assert identity["redaction_policy_version"]
    assert identity["redaction_input_hash"]
    assert identity["redaction_output_hash"]
    text = "\n".join(lines)
    assert "@" not in text or "<redacted:email>" in text
    assert "C:\\Users\\" not in text


def test_truncated_view_carries_an_omission_marker():
    for spec in FIXTURE_SPECS:
        lines, _ = build_fixture(spec)
        view = build_worker_view(packet_for(spec, lines), WorkerViewConfig())
        assert "[... omitted" in view.serialized_text, spec.fixture_id
