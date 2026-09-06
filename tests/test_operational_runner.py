"""Focused tests for the corrective revision of run_phase0_operational.py.

Everything that touches Ollama, nvidia-smi, or the server log is replaced
by module-level fakes; the driver's control flow, persistence, and
redaction run for real against a temporary results root.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_phase0_operational as op  # noqa: E402
from local_intel.runtime_identity import (  # noqa: E402
    GpuIdentity,
    ModelIdentity,
    ResidencyObservation,
    ServerEnvironment,
)

FAKE_HOME_PATH = r"C:\Users\someone\AppData\Local\Ollama\server.log"
FAKE_SEGMENT = (
    f"time=... msg=\"starting llama server\" cmd=\"{FAKE_HOME_PATH} --ctx-size 32768\"\n"
    "load_tensors: offloaded 49/49 layers to GPU\n"
)


class FakeRunOne:
    """Scriptable stand-in for run_phase0_smoke.run_one."""

    def __init__(self, behaviour=None):
        self.calls: list[tuple] = []
        self.behaviour = behaviour or (lambda i, spec, tag, state: None)

    def __call__(self, spec, model_tag, digest, profile_id, ollama_version, state, keep_alive=None):
        self.calls.append((spec.fixture_id, model_tag, state, keep_alive))
        override = self.behaviour(len(self.calls), spec, model_tag, state)
        if isinstance(override, BaseException):
            raise override
        run = {
            "fixture_id": spec.fixture_id,
            "stratum": getattr(spec, "stratum", "s"),
            "model": model_tag,
            "model_load_state": state,
            "structurally_valid": True,
            "citation_integrity": True,
            "invocation_failure_kind": None,
            "error": None,
            "failed_checks": [],
            "validation_errors": [],
            "invocation_configuration_id": "cfg",
            "local_total_duration_ms": 15000.0,
            "model_load_duration_ms": 120.0,
            "prompt_prefill_duration_ms": 10000.0,
            "generation_duration_ms": 4000.0,
            "prompt_eval_count": 27000,
            "generated_output_tokens": 120,
            "classification": "ok",
            "raw_path_leak": FAKE_HOME_PATH,
        }
        if isinstance(override, dict):
            run.update(override)
        return run


TIMEOUT_RUN = {
    "structurally_valid": False,
    "citation_integrity": None,
    "invocation_failure_kind": "timeout",
    "error": "timed out after 900000 ms",
    "local_total_duration_ms": 900000.0,
    "model_load_duration_ms": None,
    "prompt_prefill_duration_ms": None,
    "generation_duration_ms": None,
    "prompt_eval_count": None,
    "generated_output_tokens": None,
}


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """Wire the driver to fakes and a temp results root; return a helper."""
    results_root = tmp_path / "results"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"fixture_set_version": "test-fixtures"}), encoding="utf-8")
    specs = list(op.FIXTURE_SPECS)[:2]
    models = ["model-a:1b", "model-b:2b"]

    monkeypatch.setattr(op, "RESULTS_ROOT", results_root)
    monkeypatch.setattr(op, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(op, "FIXTURE_SPECS", specs)
    monkeypatch.setattr(op, "MODELS", models)
    monkeypatch.setattr(op, "read_server_environment", lambda: ServerEnvironment(
        ollama_version="0.32.14", flash_attention="true", keep_alive="30m0s",
        kv_cache_type="", max_loaded_models="1", log_banner_line_no=1))
    monkeypatch.setattr(op, "read_gpu_identity", lambda: GpuIdentity(
        name="Fake GPU", driver_version="1", vram_total_mib=16303,
        vram_used_mib_at_start=100, vram_free_mib_at_start=16000))
    monkeypatch.setattr(op, "load_profile", lambda pid: {
        "profile": {"machine_profile_id": pid, "model_store_path": FAKE_HOME_PATH},
        "profile_hash": "deadbeef"})
    monkeypatch.setattr(op, "get_ollama_version", lambda: "0.32.14")
    monkeypatch.setattr(op, "get_model_digest", lambda tag: "sha256:" + tag)
    monkeypatch.setattr(op, "read_model_identity", lambda tag: ModelIdentity(
        tag=tag, digest="sha256:" + tag, family="fake", parameter_size="1B", quantization="Q4",
        size_bytes=1, total_layers=48, native_context_length=32768, has_vision_projector=False))
    monkeypatch.setattr(op, "unload_model", lambda tag: True)
    monkeypatch.setattr(op, "get_loaded_models", lambda: [])
    monkeypatch.setattr(op, "server_log_offset", lambda: 0)
    monkeypatch.setattr(op, "server_log_segment", lambda off: FAKE_SEGMENT)
    monkeypatch.setattr(op, "read_residency", lambda tag: ResidencyObservation(resident=True))
    # No nvidia-smi in tests; make the sampler tick fast and succeed.
    monkeypatch.setattr(op.Sampler, "_gpu", lambda self: ["50", "8000", "200", "2000", "1000", "60"])
    monkeypatch.setattr(op, "wait_unloaded", lambda tag, timeout_s=60: True)

    class H:
        root = results_root

        def install(self, run_one: FakeRunOne) -> FakeRunOne:
            monkeypatch.setattr(op, "run_one", run_one)
            return run_one

        def documents(self) -> list[Path]:
            return sorted(results_root.glob("phase0_operational_*.json"))

        def document(self) -> dict:
            docs = self.documents()
            assert len(docs) == 1, docs
            return json.loads(docs[0].read_text(encoding="utf-8"))

        def csvs(self) -> list[Path]:
            return sorted((results_root / "telemetry").rglob("*.csv"))

        def all_text(self) -> str:
            return "".join(p.read_text(encoding="utf-8", errors="replace")
                           for p in results_root.rglob("*") if p.is_file())

    return H()


# --- normal completed batch -------------------------------------------------

def test_completed_batch_writes_full_document_and_records_request_keep_alive(harness):
    run_one = harness.install(FakeRunOne())
    assert op.main(["test-box"]) == op.EXIT_OK
    doc = harness.document()
    assert doc["complete"] is True
    assert doc["aborted"] is None
    assert len(doc["runs"]) == 2 * 2 * 2  # 2 models x 2 states x 2 fixtures
    assert len(harness.csvs()) == 8
    assert all(c["complete"] for c in doc["conditions"]) and len(doc["conditions"]) == 4
    # request keep_alive recorded separately from the server value
    assert doc["server_environment"]["keep_alive"] == "30m0s"
    assert doc["request_keep_alive"] == op.REQUEST_KEEP_ALIVE
    assert doc["runs"][0]["runtime_identity"]["request_keep_alive"] == op.REQUEST_KEEP_ALIVE
    assert doc["runs"][0]["runtime_identity"]["server"]["keep_alive"] == "30m0s"
    assert "request keep_alive 10m" in doc["run_label"]
    # every measured request and every preload was sent the request keep_alive
    assert all(call[3] == op.REQUEST_KEEP_ALIVE for call in run_one.calls)
    # summaries present for every model, medians filled
    assert [s["model"] for s in doc["summaries"]] == op.MODELS
    assert doc["summaries"][0]["warm_median_total_ms"] == 15000.0
    # prompt-cache note is set on the warm run that shares the preload fixture
    warm_first = [r for r in doc["runs"] if r["model_load_state"] == "warm"][0]
    assert warm_first["prompt_cache_note"]
    assert doc["run_date"] in doc["runs"][0]["runtime_identity"]["disk_cache_condition"]


# --- timeout / None-duration path -------------------------------------------

def test_timeout_run_with_none_durations_is_recorded_not_crashed(harness, capsys):
    harness.install(FakeRunOne(lambda i, spec, tag, state: TIMEOUT_RUN if i == 2 else None))
    assert op.main(["test-box"]) == op.EXIT_OK  # timeout is evidence, not a stop condition
    doc = harness.document()
    assert doc["complete"] is True
    timed_out = [r for r in doc["runs"] if r["invocation_failure_kind"] == "timeout"]
    assert len(timed_out) == 1
    r = timed_out[0]
    assert r["model_load_duration_ms"] is None
    assert r["derived"] == {"prefill_tok_s": None, "decode_tok_s": None, "inference_only_ms": 900000.0}
    out = capsys.readouterr().out
    assert "load=n/a" in out and "failure=timeout" in out
    assert doc["summaries"][0]["invocation_failures"] == 1


def test_ms_formatter_is_none_safe():
    assert op._ms(None) == "n/a"
    assert op._ms(1234.6) == "1235ms"


# --- injected exception path ------------------------------------------------

def test_injected_exception_preserves_partial_results_and_reraises(harness):
    harness.install(FakeRunOne(lambda i, spec, tag, state: RuntimeError("boom") if i == 3 else None))
    with pytest.raises(RuntimeError, match="boom"):
        op.main(["test-box"])
    doc = harness.document()
    assert doc["complete"] is False
    assert len(doc["runs"]) == 2  # runs 1 and 2 completed before the failure
    assert doc["aborted"]["kind"] == "exception"
    assert doc["aborted"]["reason"] == "RuntimeError: boom"
    # call 3 is the unrecorded warm preload, so the last recorded run index is 2
    assert doc["aborted"]["at_run"] == 2
    assert "RuntimeError" in doc["aborted"]["traceback"]
    assert doc["summaries"]  # summaries computed over the partial runs
    assert doc["ended_utc"] is not None
    # the aborting condition is on record even though it never completed
    assert doc["conditions"][-1]["complete"] is False


# --- Ctrl-C path --------------------------------------------------------------

def test_keyboard_interrupt_preserves_partial_results_and_exits_130(harness):
    harness.install(FakeRunOne(lambda i, spec, tag, state: KeyboardInterrupt() if i == 2 else None))
    assert op.main(["test-box"]) == op.EXIT_INTERRUPTED
    doc = harness.document()
    assert doc["aborted"]["kind"] == "keyboard_interrupt"
    assert doc["aborted"]["at_run"] == 2
    assert len(doc["runs"]) == 1


# --- sampler cleanup / partial-artifact persistence ---------------------------

def test_sampler_stopped_and_csv_flushed_when_run_one_raises(harness):
    harness.install(FakeRunOne(lambda i, spec, tag, state: KeyboardInterrupt() if i == 2 else None))
    op.main(["test-box"])
    csvs = harness.csvs()
    assert len(csvs) == 2  # run 1 complete + the in-flight run 2 sampler
    doc = harness.document()
    in_flight = doc["aborted"]["in_flight_telemetry"]
    assert in_flight["samples"] >= 1
    assert in_flight["sampler_join_timed_out"] is False
    with csvs[1].open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and set(rows[0]) == set(op.Sampler.FIELDS)
    assert "gpu_query_ms" in rows[0]


def test_stop_condition_records_reason_and_exits_3(harness, monkeypatch):
    harness.install(FakeRunOne())
    monkeypatch.setattr(op, "server_log_segment", lambda off: FAKE_SEGMENT + "CUDA error: device lost\n")
    assert op.main(["test-box"]) == op.EXIT_STOP_CONDITION
    doc = harness.document()
    assert doc["aborted"]["kind"] == "stop_condition"
    assert "CUDA error" in doc["aborted"]["reason"]
    assert len(doc["runs"]) == 1  # the run that tripped the condition is kept


def test_sampler_join_timeout_is_recorded_and_is_a_stop_condition(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "SAMPLER_JOIN_TIMEOUT_S", 0.05)
    import threading
    release = threading.Event()

    def wedged(self):
        release.wait(5)
        return None

    monkeypatch.setattr(op.Sampler, "_gpu", wedged)
    s = op.Sampler(tmp_path / "t.csv", interval_s=0.01).start()
    summary = s.stop()
    release.set()
    assert summary["sampler_join_timed_out"] is True
    assert summary["gpu_query_failures"] == 1  # counted before the query returned
    assert (tmp_path / "t.csv").exists()
    with pytest.raises(op.StopBatch, match="sampler did not stop"):
        op.check_stop_conditions(summary, "", {})


def test_sampler_stamps_elapsed_before_gpu_query(tmp_path, monkeypatch):
    import time as _t

    def slow(self):
        _t.sleep(0.2)
        return ["1", "2", "3", "4", "5", "6"]

    monkeypatch.setattr(op.Sampler, "_gpu", slow)
    s = op.Sampler(tmp_path / "t.csv", interval_s=0.01).start()
    _t.sleep(0.5)
    summary = s.stop()
    assert summary["samples"] >= 2
    assert summary["gpu_query_ms"]["min"] >= 150
    # gap between ticks includes the query, but elapsed is stamped at tick start
    assert s.rows[0]["elapsed_s"] < 0.1


# --- overwrite / cross-run contamination guard --------------------------------

def test_refuses_to_start_when_any_output_path_exists(harness, monkeypatch, capsys):
    harness.install(FakeRunOne())
    from datetime import datetime, timezone
    fixed = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(op, "datetime", FixedDT)
    paths = op.RunPaths(harness.root, "test-box", op.make_run_id(fixed))
    paths.telemetry_dir.mkdir(parents=True)
    assert op.main(["test-box"]) == 1
    assert "refusing to overwrite" in capsys.readouterr().out
    assert harness.documents() == []


def test_two_batches_never_share_paths(harness):
    harness.install(FakeRunOne())
    from datetime import datetime, timezone
    a = op.RunPaths(harness.root, "p", op.make_run_id(datetime(2026, 9, 6, 1, 0, 0, tzinfo=timezone.utc)))
    b = op.RunPaths(harness.root, "p", op.make_run_id(datetime(2026, 9, 6, 1, 0, 1, tzinfo=timezone.utc)))
    assert {a.document, a.telemetry_dir, a.log_segment_dir}.isdisjoint({b.document, b.telemetry_dir, b.log_segment_dir})


# --- redaction coverage -------------------------------------------------------

def test_no_local_account_path_reaches_disk(harness):
    harness.install(FakeRunOne())
    op.main(["test-box"])
    text = harness.all_text()
    assert "someone" not in text
    assert r"C:\Users" not in text and "C:\\\\Users" not in text
    assert "<HOME>" in text
    doc = harness.document()
    assert doc["hardware_profile"]["model_store_path"].startswith("<HOME>")
    assert doc["runs"][0]["raw_path_leak"].startswith("<HOME>")
    segs = sorted((harness.root / "server_log_segments").rglob("*.log"))
    assert segs and all("<HOME>" in p.read_text(encoding="utf-8") for p in segs)


def test_redaction_also_applies_on_abort(harness):
    harness.install(FakeRunOne(lambda i, spec, tag, state: RuntimeError(FAKE_HOME_PATH) if i == 2 else None))
    with pytest.raises(RuntimeError):
        op.main(["test-box"])
    assert "someone" not in harness.all_text()
