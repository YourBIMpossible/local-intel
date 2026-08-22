"""Minimal bounded Ollama invocation with §14 telemetry.

Scope limits enforced here, per §16 (process isolation) and §2 (laws):
  - The model receives a serialized worker view on the prompt and nothing
    else: no filesystem, no shell, no network, no Git, no MCP, no tools.
  - The host process owns invocation, timeouts, validation, and persistence.
  - A timeout or unavailable model discards the artifact and falls back
    (§14 resource policy); it never queues and never CPU-swaps.

Every invocation returns telemetry regardless of outcome, because §6 needs
latency numbers for failed runs too -- a model that is slow AND invalid must
be measurable as both.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DEFAULT_HOST = "http://localhost:11434"
PREFLIGHT_TIMEOUT_MS = 500  # §14 resource_policy.preflight_timeout_ms


@dataclass
class InvocationTelemetry:
    """§14 required hardware telemetry (host-observable subset)."""

    model_load_state: str  # "cold" | "warm"
    preflight_duration_ms: float | None = None
    model_load_duration_ms: float | None = None
    prompt_prefill_duration_ms: float | None = None
    generation_duration_ms: float | None = None
    local_total_duration_ms: float | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


@dataclass
class InvocationResult:
    ok: bool
    raw_text: str | None
    parsed: Any | None
    telemetry: InvocationTelemetry
    failure_kind: str | None = None  # "unavailable" | "timeout" | "transport" | "unparseable"
    error: str | None = None


def _post_json(url: str, payload: dict, timeout_s: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def preflight(host: str = DEFAULT_HOST) -> tuple[bool, float]:
    """Cheap availability probe. Returns (available, duration_ms)."""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=PREFLIGHT_TIMEOUT_MS / 1000):
            pass
        return True, (time.perf_counter() - start) * 1000
    except (urllib.error.URLError, OSError, TimeoutError):
        return False, (time.perf_counter() - start) * 1000


def get_model_digest(model_tag: str, host: str = DEFAULT_HOST) -> str | None:
    """Model digest for configuration identity (§9). None if not installed."""
    try:
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
        return None
    for model in data.get("models", []):
        if model.get("name") == model_tag:
            return model.get("digest")
    return None


def unload_model(model_tag: str, host: str = DEFAULT_HOST) -> bool:
    """Force the model out of memory so the next call is a genuine cold
    measurement (§6 requires cold and warm numbers separately)."""
    try:
        _post_json(
            f"{host}/api/generate",
            {"model": model_tag, "prompt": "", "keep_alive": 0},
            timeout_s=30,
        )
        return True
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
        return False


def invoke(
    *,
    model_tag: str,
    prompt: str,
    schema: dict,
    generation: Any,  # GenerationParameters
    timeout_ms: int,
    keep_alive: str = "5m",
    model_load_state: str = "warm",
    host: str = DEFAULT_HOST,
) -> InvocationResult:
    """One bounded, structured-output invocation.

    `schema` is passed as Ollama's `format`, which constrains decoding. The
    deterministic post-validator (§8) still runs on the result: constrained
    decoding shapes the JSON, it does not make the citations real.
    """
    available, preflight_ms = preflight(host)
    telemetry = InvocationTelemetry(
        model_load_state=model_load_state, preflight_duration_ms=preflight_ms
    )

    if not available:
        # §14 on_unavailable: fallback_to_baseline. No queueing, no retry.
        return InvocationResult(
            ok=False,
            raw_text=None,
            parsed=None,
            telemetry=telemetry,
            failure_kind="unavailable",
            error=f"Ollama preflight failed at {host} after {preflight_ms:.0f}ms",
        )

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
        "model": model_tag,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "options": options,
        "keep_alive": keep_alive,
    }

    start = time.perf_counter()
    try:
        response = _post_json(f"{host}/api/generate", payload, timeout_s=timeout_ms / 1000)
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        telemetry.local_total_duration_ms = elapsed_ms
        is_timeout = isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()
        return InvocationResult(
            ok=False,
            raw_text=None,
            parsed=None,
            telemetry=telemetry,
            # §14 on_timeout: discard_artifact_and_fallback.
            failure_kind="timeout" if is_timeout else "transport",
            error=f"{type(exc).__name__}: {exc}",
        )

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Ollama reports durations in nanoseconds.
    def _ns_to_ms(key: str) -> float | None:
        v = response.get(key)
        return v / 1e6 if isinstance(v, (int, float)) else None

    telemetry.model_load_duration_ms = _ns_to_ms("load_duration")
    telemetry.prompt_prefill_duration_ms = _ns_to_ms("prompt_eval_duration")
    telemetry.generation_duration_ms = _ns_to_ms("eval_duration")
    telemetry.local_total_duration_ms = _ns_to_ms("total_duration") or elapsed_ms
    telemetry.prompt_eval_count = response.get("prompt_eval_count")
    telemetry.eval_count = response.get("eval_count")

    raw_text = response.get("response", "")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return InvocationResult(
            ok=False,
            raw_text=raw_text,
            parsed=None,
            telemetry=telemetry,
            failure_kind="unparseable",
            error=f"response was not valid JSON: {exc}",
        )

    return InvocationResult(ok=True, raw_text=raw_text, parsed=parsed, telemetry=telemetry)
