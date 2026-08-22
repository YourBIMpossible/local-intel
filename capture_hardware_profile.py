"""Phase 0 step 4: capture the target hardware profile (§6).

Usage:
    python capture_hardware_profile.py <machine_profile_id>

Also probes each candidate model's residency at the Phase 0 context size,
because §6's latency thresholds are only interpretable against whether the
model actually fits in VRAM. A model that spills to CPU is not a slow model;
it is a differently-configured one, and conflating the two would let a
hardware limit masquerade as a model verdict.

This script loads models but submits no evidence packets. It is not a Phase 0
measurement run.
"""

from __future__ import annotations

import sys

from local_intel.config_identity import GenerationParameters
from local_intel.hardware import capture_profile, write_profile
from local_intel.ollama_client import (
    DEFAULT_HOST,
    get_loaded_models,
    invoke,
    unload_model,
)

CANDIDATE_MODELS = ["qwen2.5-coder:14b", "qwen3-coder:30b-a3b-q4_K_M"]


def probe_residency(model_tag: str, num_ctx: int, host: str = DEFAULT_HOST) -> dict:
    """Load the model at the Phase 0 context size and report its VRAM/CPU
    split. A minimal generation is required: Ollama sizes the allocation when
    it actually serves a request."""
    unload_model(model_tag, host)
    generation = GenerationParameters(num_ctx=num_ctx, max_output_tokens=8)
    result = invoke(
        model_tag=model_tag,
        prompt="ok",
        schema={"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
        generation=generation,
        timeout_ms=300_000,
        keep_alive="30s",
        model_load_state="cold",
        host=host,
    )

    # The probe caps output at a few tokens, so the returned JSON is normally
    # truncated and unparseable. That is expected and says nothing about the
    # model: what matters is whether the request was SERVED, which is what
    # forces Ollama to size the allocation being measured.
    served = result.telemetry.local_total_duration_ms is not None

    entry = next((m for m in get_loaded_models(host) if m.get("name") == model_tag), None)
    if entry is None:
        return {
            "model": model_tag,
            "num_ctx": num_ctx,
            "resident": False,
            "request_served": served,
            "error": result.error,
        }

    total = entry.get("size")
    vram = entry.get("size_vram")
    fully_on_gpu = bool(total and vram and vram >= total)
    gpu_fraction = round(vram / total, 4) if total and vram else None

    return {
        "model": model_tag,
        "num_ctx": num_ctx,
        "resident": True,
        "request_served": served,
        "total_size_bytes": total,
        "vram_size_bytes": vram,
        "gpu_fraction": gpu_fraction,
        "fully_on_gpu": fully_on_gpu,
        "cold_load_duration_ms": result.telemetry.model_load_duration_ms,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    machine_profile_id = sys.argv[1]

    profile, environment = capture_profile(machine_profile_id)
    print(f"Detected profile for {machine_profile_id}:")
    for k, v in profile.to_dict().items():
        print(f"  {k}: {v}")

    num_ctx = GenerationParameters().num_ctx
    print(f"\nProbing candidate-model residency at num_ctx={num_ctx} ...")
    residency = []
    for model_tag in CANDIDATE_MODELS:
        print(f"  {model_tag} ...", flush=True)
        info = probe_residency(model_tag, num_ctx)
        residency.append(info)
        if info.get("resident"):
            pct = (info.get("gpu_fraction") or 0) * 100
            fit = "fully on GPU" if info["fully_on_gpu"] else "PARTIAL -- spills to CPU"
            print(f"    {pct:.1f}% on GPU -- {fit}")
        else:
            print(f"    not resident: {info.get('error')}")
        unload_model(model_tag)

    environment["candidate_model_residency"] = residency

    notes = [
        "Captured for Phase 0 step 4. No evidence packets submitted; this is "
        "not a Phase 0 measurement run.",
        "Residency probed at the frozen Phase 0 num_ctx. A model that does not "
        "fit in VRAM at this context size is measured as configured, not "
        "reconfigured to make it fit -- changing num_ctx would create a new "
        "candidate configuration under §9.",
    ]

    path = write_profile(profile, environment, notes)
    print(f"\nWrote {path}")
    print(f"profile_hash = {profile.profile_hash()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
