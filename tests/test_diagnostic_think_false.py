"""Failure / retry-safety tests for run_diagnostic_think_false.

Everything that touches Ollama (digest, version, unload, the generate call)
is replaced by fakes; the script's control flow, persistence, and
whole-document path redaction run for real against a temporary diagnostics
directory. These tests pin the reliability contract:

  - a completed request writes the normal success artifact and exits 0;
  - a transport/timeout/malformed-response failure exits non-zero, writes no
    success artifact, and persists a distinct, redacted failure artifact;
  - a failure never blocks a later same-day success and needs no manual
    cleanup; both attempts are preserved.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_diagnostic_think_false as diag  # noqa: E402

# A profile id carrying a redactable local path, so each test can assert the
# artifact was written through redact_local_paths -- whole-document redaction
# must cover this argv-sourced field.
PROFILE_WITH_PATH = "C:/Users/secretacct/machine-01"
REDACTED_ID = "<HOME>/machine-01"
LEAK_MARKER = "secretacct"

SUCCESS_SUFFIX = "_qwen3.5-9b_think-false.json"
FAILURE_SUFFIX = ".FAILED.json"


class _FakeResp:
    """Context-manager stand-in for the urlopen response object."""

    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _success_envelope(response_text: str = "not-json-diagnostic-output") -> dict:
    return {
        "response": response_text,
        "done_reason": "stop",
        "total_duration": 1_000_000,
        "load_duration": 400_000,
        "prompt_eval_duration": 300_000,
        "eval_duration": 300_000,
        "prompt_eval_count": 100,
        "eval_count": 50,
    }


def _successes(out_dir: Path) -> list[Path]:
    return [p for p in out_dir.glob("*.json") if p.name.endswith(SUCCESS_SUFFIX)]


def _failures(out_dir: Path) -> list[Path]:
    return list(out_dir.glob("*" + FAILURE_SUFFIX))


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Redirect output to tmp and stub every Ollama touch except urlopen."""
    out_dir = tmp_path / "diagnostics"
    monkeypatch.setattr(diag, "OUT_DIR", out_dir)
    monkeypatch.setattr(diag, "get_model_digest", lambda *a, **k: "sha256:deadbeef")
    monkeypatch.setattr(diag, "get_ollama_version", lambda *a, **k: "test-0.0.0")
    monkeypatch.setattr(diag, "unload_model", lambda *a, **k: True)
    return out_dir


def _set_urlopen(monkeypatch, behaviour):
    monkeypatch.setattr(urllib.request, "urlopen", behaviour)


def test_success_writes_redacted_artifact_exit_0(wired, monkeypatch):
    _set_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(_success_envelope()))
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 0
    assert len(_successes(wired)) == 1
    assert not _failures(wired)
    text = _successes(wired)[0].read_text(encoding="utf-8")
    assert LEAK_MARKER not in text          # redaction ran over the whole document
    assert "<HOME>" in text
    doc = json.loads(text)
    assert doc["kind"] == "single-request diagnostic"
    assert doc["hardware_profile_id"] == REDACTED_ID


def test_transport_failure_exit_nonzero_no_success_artifact(wired, monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")
    _set_urlopen(monkeypatch, boom)
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 1
    assert not _successes(wired)             # no normal success artifact
    assert len(_failures(wired)) == 1


def test_timeout_is_classified_and_recorded(wired, monkeypatch):
    def slow(req, timeout=None):
        raise TimeoutError("timed out")
    _set_urlopen(monkeypatch, slow)
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 1
    doc = json.loads(_failures(wired)[0].read_text(encoding="utf-8"))
    assert doc["failure_kind"] == "timeout"


def test_malformed_envelope_is_failure(wired, monkeypatch):
    _set_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(b"not json at all"))
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 1
    assert not _successes(wired)
    doc = json.loads(_failures(wired)[0].read_text(encoding="utf-8"))
    assert doc["failure_kind"] == "malformed_response"


def test_failure_artifact_is_distinct_and_redacted_and_self_describing(wired, monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("refused")
    _set_urlopen(monkeypatch, boom)
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 1
    failures = _failures(wired)
    assert len(failures) == 1
    fp = failures[0]
    assert fp.name.endswith(FAILURE_SUFFIX)
    assert not fp.name.endswith(SUCCESS_SUFFIX)      # distinct from the success path
    text = fp.read_text(encoding="utf-8")
    assert LEAK_MARKER not in text and "<HOME>" in text
    doc = json.loads(text)
    assert doc["outcome"] == "failure"
    assert doc["failure_kind"] == "transport"
    assert doc["failure_reason"]
    assert doc["hardware_profile_id"] == REDACTED_ID
    # runtime identity available before failure is recorded
    for key in (
        "started_utc", "failed_utc", "local_intel_version", "ollama_version",
        "model", "request_shape", "worker_view_hash", "fixture_id",
    ):
        assert key in doc, key


def test_failure_then_same_day_success_needs_no_deletion(wired, monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("refused")
    _set_urlopen(monkeypatch, boom)
    assert diag.main([PROFILE_WITH_PATH]) == 1
    assert len(_failures(wired)) == 1
    assert not _successes(wired)

    # Same day, same output dir: a success must proceed with no manual cleanup.
    _set_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(_success_envelope()))
    assert diag.main([PROFILE_WITH_PATH]) == 0
    assert len(_successes(wired)) == 1
    assert len(_failures(wired)) == 1        # both attempts preserved


def test_existing_success_artifact_is_still_refused(wired, monkeypatch):
    _set_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(_success_envelope()))
    assert diag.main([PROFILE_WITH_PATH]) == 0
    # A second same-day success run must still refuse to overwrite a genuine result.
    assert diag.main([PROFILE_WITH_PATH]) == 1
    assert len(_successes(wired)) == 1


def test_bad_argv_returns_2(wired):
    assert diag.main([]) == 2
    assert diag.main(["a", "b"]) == 2


def test_model_not_installed_returns_1_and_writes_nothing(wired, monkeypatch):
    monkeypatch.setattr(diag, "get_model_digest", lambda *a, **k: None)
    assert diag.main([PROFILE_WITH_PATH]) == 1
    assert not _successes(wired) and not _failures(wired)


def test_incomplete_read_is_malformed_failure(wired, monkeypatch):
    import http.client

    class _DropResp(_FakeResp):
        def read(self):  # connection dropped mid-body
            raise http.client.IncompleteRead(b"partial")

    _set_urlopen(monkeypatch, lambda req, timeout=None: _DropResp(b""))
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 1
    assert not _successes(wired)
    doc = json.loads(_failures(wired)[0].read_text(encoding="utf-8"))
    assert doc["failure_kind"] == "malformed_response"


def test_non_utf8_body_is_malformed_failure(wired, monkeypatch):
    _set_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(b"\xff\xfe\x00bad"))
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 1
    assert not _successes(wired)
    doc = json.loads(_failures(wired)[0].read_text(encoding="utf-8"))
    assert doc["failure_kind"] == "malformed_response"


def test_non_dict_envelope_is_malformed_failure(wired, monkeypatch):
    _set_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp([1, 2, 3]))
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 1
    assert not _successes(wired)
    doc = json.loads(_failures(wired)[0].read_text(encoding="utf-8"))
    assert doc["failure_kind"] == "malformed_response"


def test_urlerror_timed_out_string_is_classified_timeout(wired, monkeypatch):
    def slow(req, timeout=None):
        raise urllib.error.URLError("The operation timed out")
    _set_urlopen(monkeypatch, slow)
    rc = diag.main([PROFILE_WITH_PATH])
    assert rc == 1
    doc = json.loads(_failures(wired)[0].read_text(encoding="utf-8"))
    assert doc["failure_kind"] == "timeout"
