"""One-request diagnostic: does `qwen3.5:9b` return a schema-valid artifact
when the request carries top-level `think: false`?

    python run_diagnostic_think_false.py <machine_profile_id>

Context: in the 2026-09-06 operational batch `qwen3.5:9b` scored 0/5
structural validity with `unparseable` responses. The explanation offered
(tokens written to a `thinking` field, `response` empty) had no committed
evidence. This script commits that evidence, one way or the other.

What it does NOT do: it is not a Phase 0 run, it does not touch the
candidate list, and it records nothing that feeds a §6 decision. It sends
exactly one request, identical in shape to `local_intel.ollama_client.invoke`
(same prompt builder, same `format` schema, same frozen §9 options, same
request keep_alive) plus the top-level `think: false` field, then runs the
same §8 validator on whatever comes back and writes a small artifact.

On a transport/timeout/malformed-response failure it writes no success
artifact, records a sanitized failure artifact under a distinct FAILED path,
and exits non-zero -- leaving the date-only success path free for a later
same-day retry with no manual cleanup.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from local_intel import __version__
from local_intel.artifact import ARTIFACT_SCHEMA, SCHEMA_VERSION, schema_hash
from local_intel.config_identity import GenerationParameters
from local_intel.ollama_client import (
    DEFAULT_HOST,
    get_model_digest,
    get_ollama_version,
    unload_model,
)
from local_intel.prompt import PROMPT_VERSION, build_prompt
from local_intel.redact_paths import redact_local_paths
from local_intel.triage import MAX_ARTIFACT_CHARS
from local_intel.validator import VALIDATOR_VERSION, validate_artifact
from local_intel.worker_view import WorkerViewConfig, build_worker_view
from fixtures.templates import FIXTURE_SPECS
from generate_fixtures import build_fixture, packet_for
from run_phase0_smoke import INVOCATION_TIMEOUT_MS, REQUEST_KEEP_ALIVE, RESULTS_DIR

MODEL = "qwen3.5:9b"
OUT_DIR = RESULTS_DIR / "diagnostics"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    profile_id = argv[0]

    started = datetime.now(timezone.utc)
    out = OUT_DIR / f"{started.strftime('%Y-%m-%d')}_qwen3.5-9b_think-false.json"
    if out.exists():
        print(f"FATAL: {out} exists; refusing to overwrite a prior diagnostic.")
        return 1

    digest = get_model_digest(MODEL)
    if digest is None:
        print(f"FATAL: {MODEL} not installed.")
        return 1
    ollama_version = get_ollama_version() or "unknown"

    spec = FIXTURE_SPECS[0]
    lines, _redaction = build_fixture(spec)
    packet = packet_for(spec, lines)
    generation = GenerationParameters()
    view = build_worker_view(
        packet, WorkerViewConfig(),
        configured_num_ctx=generation.num_ctx,
        max_output_tokens=generation.max_output_tokens,
    )
    prompt = build_prompt(view.serialized_text)

    options = {
        "temperature": generation.temperature,
        "top_p": generation.top_p,
        "top_k": generation.top_k,
        "num_ctx": generation.num_ctx,
        "num_predict": generation.max_output_tokens,
    }
    if generation.seed is not None:
        options["seed"] = generation.seed
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": ARTIFACT_SCHEMA,
        "options": options,
        "keep_alive": REQUEST_KEEP_ALIVE,
        "think": False,  # the one field the batch harness did not send
    }

    # Same start condition as the batch's warm runs is not reproducible here
    # without a preload; run process-cold-of-model and say so.
    unload_model(MODEL)

    request_shape = {k: v for k, v in payload.items() if k not in ("prompt", "format")}
    request_shape["prompt_sha256"] = _sha256(prompt)
    request_shape["prompt_chars"] = len(prompt)
    request_shape["prompt_version"] = PROMPT_VERSION
    request_shape["format_schema_hash"] = schema_hash()
    request_shape["format_schema_version"] = SCHEMA_VERSION

    t0 = time.perf_counter()
    error = None
    failure_kind: str | None = None
    response: dict | None = None
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{DEFAULT_HOST}/api/generate", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=INVOCATION_TIMEOUT_MS / 1000) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except TimeoutError as exc:
        error, failure_kind = f"{type(exc).__name__}: {exc}", "timeout"
    except urllib.error.URLError as exc:
        # URLError subclasses OSError and wraps a socket timeout as its reason.
        # Mirror local_intel.ollama_client.invoke's classification so the two
        # code paths bucket timeouts identically.
        reason = getattr(exc, "reason", None)
        is_timeout = isinstance(reason, TimeoutError) or "timed out" in str(exc).lower()
        error = f"{type(exc).__name__}: {exc}"
        failure_kind = "timeout" if is_timeout else "transport"
    except (json.JSONDecodeError, UnicodeDecodeError, http.client.HTTPException) as exc:
        # The HTTP call returned, but the body could not be read/decoded into a
        # usable JSON envelope (invalid JSON, non-UTF-8 bytes, or a connection
        # dropped mid-body -> IncompleteRead). No usable response was obtained,
        # so treat it as a request failure, not a diagnostic result.
        error, failure_kind = f"{type(exc).__name__}: {exc}", "malformed_response"
    except OSError as exc:
        error, failure_kind = f"{type(exc).__name__}: {exc}", "transport"
    wall_ms = (time.perf_counter() - t0) * 1000

    if error is None and not isinstance(response, dict):
        # A valid JSON body that is not an object (list/scalar) is not a usable
        # Ollama envelope; the success path indexes it as a dict, so route it
        # through the failure branch instead of crashing on `.get`.
        error = f"non-dict response envelope: {type(response).__name__}"
        failure_kind = "malformed_response"

    if error is not None:
        # The request yielded no diagnostic signal. Do NOT write the normal
        # success artifact and do NOT occupy the date-only success path (`out`),
        # so a later same-day run can still produce a genuine diagnostic with no
        # manual cleanup. Persist a sanitized, self-describing failure artifact
        # under a distinct run-id path and exit non-zero.
        failed = datetime.now(timezone.utc)
        failure_document = {
            "kind": "single-request diagnostic (FAILED)",
            "outcome": "failure",
            "purpose": (
                "Attempted to verify or refute the unverified explanation for "
                "qwen3.5:9b's 0/5 structural validity in the 2026-09-06 "
                "operational batch. The generate request did not complete, so no "
                "diagnostic signal was obtained. Not a Phase 0 run; feeds no §6 "
                "decision; candidate list unchanged."
            ),
            "failure_kind": failure_kind,
            "failure_reason": error,
            "started_utc": started.isoformat(),
            "failed_utc": failed.isoformat(),
            "wall_clock_ms": round(wall_ms, 1),
            # Runtime identity gathered before the request (all pre-failure).
            "local_intel_version": __version__,
            "ollama_version": ollama_version,
            "hardware_profile_id": profile_id,
            "model": {"tag": MODEL, "digest": digest},
            "model_load_state": "cold-of-model (unloaded immediately before; page cache not controlled)",
            "fixture_id": spec.fixture_id,
            "worker_view_hash": view.worker_view_hash,
            "request_shape": request_shape,
            "difference_from_batch_request": "top-level `think: false` added; everything else identical",
            "note": (
                "This artifact records a failed attempt only. It is NOT a "
                "diagnostic result, occupies a distinct FAILED path, and leaves "
                f"the success path free for a retry: {out.name}"
            ),
        }
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        fail_out = OUT_DIR / (
            f"{started.strftime('%Y-%m-%dT%H%M%S-%f')}_qwen3.5-9b_think-false.FAILED.json"
        )
        fail_out.write_text(
            redact_local_paths(json.dumps(failure_document, indent=2)) + "\n",
            encoding="utf-8",
        )
        # unload_model never raises (returns False on a down server), so this
        # best-effort cleanup is safe even when the failure was a dead server.
        unload_model(MODEL)
        print(json.dumps({
            "outcome": "failure",
            "failure_kind": failure_kind,
            "failure_reason": error,
            "wall_clock_ms": round(wall_ms, 1),
        }, indent=2))
        print(f"Request failed ({failure_kind}); wrote failure artifact {fail_out}")
        print(f"Success path {out} left free for a later retry.")
        return 1

    def _ns(key: str) -> float | None:
        v = (response or {}).get(key)
        return v / 1e6 if isinstance(v, (int, float)) else None

    raw_response = (response or {}).get("response")
    thinking = (response or {}).get("thinking")
    parsed = None
    parse_error = None
    if isinstance(raw_response, str) and raw_response:
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)

    validation = None
    if parsed is not None:
        v = validate_artifact(
            parsed,
            authorized_source_ids={packet.source_id},
            packet_line_count=packet.line_count,
            provenance=view.provenance(),
            authority_class="DERIVED",
            max_output_chars=MAX_ARTIFACT_CHARS,
        )
        validation = {"ok": v.ok, "failed_checks": v.failed_checks, "errors": v.errors[:20]}

    document = {
        "kind": "single-request diagnostic",
        "purpose": (
            "Verify or refute the unverified explanation for qwen3.5:9b's 0/5 "
            "structural validity in the 2026-09-06 operational batch (thinking "
            "output diverted from `response`). Not a Phase 0 run; feeds no §6 "
            "decision; candidate list unchanged."
        ),
        "started_utc": started.isoformat(),
        "local_intel_version": __version__,
        "ollama_version": ollama_version,
        "hardware_profile_id": profile_id,
        "model": {"tag": MODEL, "digest": digest},
        "model_load_state": "cold-of-model (unloaded immediately before; page cache not controlled)",
        "fixture_id": spec.fixture_id,
        "worker_view_hash": view.worker_view_hash,
        "request_shape": request_shape,
        "difference_from_batch_request": "top-level `think: false` added; everything else identical",
        "transport_error": error,
        "timing_ms": {
            "wall_clock": round(wall_ms, 1),
            "total_duration": _ns("total_duration"),
            "load_duration": _ns("load_duration"),
            "prompt_eval_duration": _ns("prompt_eval_duration"),
            "eval_duration": _ns("eval_duration"),
            "prompt_eval_count": (response or {}).get("prompt_eval_count"),
            "eval_count": (response or {}).get("eval_count"),
        },
        "response_fields_present": sorted((response or {}).keys()),
        "raw_response": raw_response,
        "raw_response_chars": len(raw_response) if isinstance(raw_response, str) else None,
        "thinking_field": thinking,
        "thinking_field_chars": len(thinking) if isinstance(thinking, str) else None,
        "done_reason": (response or {}).get("done_reason"),
        "json_parse_error": parse_error,
        "validation": validation,
        "structurally_valid": bool(validation and validation["ok"]),
        "validator_version": VALIDATOR_VERSION,
        "limitations": [
            "One request, one fixture, one model-load state. Not a validity rate.",
            "The batch's failing responses were not captured raw, so this shows "
            "what `think:false` produces, not what the batch produced.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(redact_local_paths(json.dumps(document, indent=2)) + "\n", encoding="utf-8")
    unload_model(MODEL)

    print(json.dumps({k: document[k] for k in (
        "structurally_valid", "raw_response_chars", "thinking_field_chars",
        "json_parse_error", "done_reason", "timing_ms", "transport_error")}, indent=2))
    if validation and not validation["ok"]:
        print("failed_checks:", validation["failed_checks"])
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
