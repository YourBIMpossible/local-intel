from local_intel.packet import EvidencePacket
from local_intel.worker_view import (
    WorkerViewConfig,
    build_worker_view,
    normalize_line,
)


def _packet(lines, source_id="log:test", command="pytest -q") -> EvidencePacket:
    return EvidencePacket(
        source_id=source_id,
        kind="test_log",
        command=command,
        environment={"os": "linux", "python": "3.11"},
        lines=lines,
    )


def test_header_preserves_metadata():
    p = _packet(["ok"], command="pytest -q suite/")
    view = build_worker_view(p)
    assert "source_id: log:test" in view.serialized_text
    assert "command: pytest -q suite/" in view.serialized_text
    assert "os: linux" in view.serialized_text


def test_normalize_line_collapses_volatile_tokens():
    a = normalize_line("2026-08-22T10:00:00Z FAIL test_foo at 0xDEADBEEF (attempt 1)")
    b = normalize_line("2026-08-22T10:05:03Z FAIL test_foo at 0xC0FFEE (attempt 7)")
    assert a == b


def test_deterministic_dedup_keeps_first_occurrence_with_line_id():
    lines = [
        "FAIL test_foo: assertion error",
        "FAIL test_foo: assertion error",
        "FAIL test_foo: assertion error",
        "FAIL test_bar: timeout",
    ]
    p = _packet(lines)
    view = build_worker_view(p)
    assert view.group_count == 2
    assert view.deduplicated_occurrence_count == 2
    assert "log:test:1: FAIL test_foo: assertion error [+2 repeat(s), lines 2-3]" in view.serialized_text
    assert "log:test:4: FAIL test_bar: timeout" in view.serialized_text


def test_hash_is_deterministic_and_content_sensitive():
    p1 = _packet(["a", "b", "c"])
    p2 = _packet(["a", "b", "c"])
    p3 = _packet(["a", "b", "d"])
    v1 = build_worker_view(p1)
    v2 = build_worker_view(p2)
    v3 = build_worker_view(p3)
    assert v1.worker_view_hash == v2.worker_view_hash
    assert v1.worker_view_hash != v3.worker_view_hash
    assert v1.packet_content_hash == p1.content_hash()


def test_no_truncation_when_under_budget():
    p = _packet(["short line"] * 10)
    view = build_worker_view(p, WorkerViewConfig(target_input_tokens=24000, reserve_output_tokens=1800))
    assert view.truncated is False
    assert "omitted" not in view.serialized_text


def test_truncation_inserts_omission_marker_and_keeps_suffix():
    # Force a tiny budget so truncation is guaranteed regardless of estimator tuning.
    import itertools
    import string

    # Digit runs are deliberately collapsed by normalize_line (they're volatile
    # noise like attempt counts/timestamps), so distinct groups here need
    # non-numeric distinguishing tokens.
    labels = ["".join(p) for p in itertools.product(string.ascii_lowercase, repeat=2)][:200]
    lines = [f"FAIL test_case_{label}: unique failure detail {label}" for label in labels]
    p = _packet(lines)
    tiny_config = WorkerViewConfig(target_input_tokens=200, reserve_output_tokens=50)
    view = build_worker_view(p, tiny_config)
    assert view.truncated is True
    assert "[... omitted log:test lines" in view.serialized_text
    # The last group should survive; the first should not.
    assert f"test_case_{labels[-1]}" in view.serialized_text
    assert f"test_case_{labels[0]}:" not in view.serialized_text


def test_provenance_contains_required_fields():
    p = _packet(["x"])
    view = build_worker_view(p)
    prov = view.provenance()
    for field in (
        "packet_content_hash",
        "packet_builder_version",
        "worker_view_builder_version",
        "truncation_strategy_version",
        "worker_view_hash",
        "configured_num_ctx",
        "max_output_tokens",
    ):
        assert field in prov
