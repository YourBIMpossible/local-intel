"""Phase 0 re-measurement with flash attention ENABLED (2026-09-06).

    python run_phase0_smoke_fa.py <machine_profile_id>

Why this exists, and why it is a separate driver rather than a re-run of
`run_phase0_smoke.py`:

The original Phase 0 pass (`phase0_results/phase0_smoke_workstation-zeria-01.json`,
which grounds the `DEFER_LOCAL_MODEL_PATH` decision) was executed with the
Ollama server default `OLLAMA_FLASH_ATTENTION=false`. A later hardware
diagnostic (WORKLOG 2026-09-05) showed that flag alone throttled prompt
prefill to ~1.9 tok/s while the GPU sat idle -- the order of magnitude that
produced the 335 s / 902 s latencies the DEFER rested on. The flag is now
persistently on.

This driver re-measures the *same* two candidates through the *same* frozen
harness -- identical §6 kill thresholds, identical §9 `GenerationParameters`,
identical fixtures and worker view -- changing nothing but the serving-layer
flash-attention flag. It imports the original harness building blocks
unchanged so that no measurement logic is forked.

Two disciplines are enforced here:

  1. It NEVER writes the canonical `phase0_smoke_{profile_id}.json`. The
     FA-off DEFER evidence is preserved byte-for-byte. Output goes to a
     dated, FA-labelled filename.

  2. The frozen `invocation_configuration_id` (§9) does NOT yet include the
     flash-attention flag -- that §9/§14 formalization is an open human call
     (WORKLOG "Needs your call", 2026-09-05), not something this script
     decides. So the FA state is recorded out-of-band, at the top level of
     the document and confirmed from the live server log, and the config-id
     limitation is stated explicitly in the output.

This script MEASURES. It does not decide. Whether these numbers admit a
model to Phase 1a, and whether they revise the basis of the DEFER, remain
human, versioned acts (§17).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from local_intel import __version__
from local_intel.config_identity import GenerationParameters
from local_intel.hardware import load_profile
from local_intel.ollama_client import (
    get_model_digest,
    get_ollama_version,
    unload_model,
)
from fixtures.templates import FIXTURE_SPECS

# Reuse the frozen harness verbatim -- no measurement logic is forked here.
from run_phase0_smoke import (
    CANDIDATE_MODELS,
    INVOCATION_TIMEOUT_MS,
    KILL_THRESHOLDS,
    RESULTS_DIR,
    run_one,
    summarise,
)

RUN_DATE = "2026-09-06"
SERVER_LOG = Path.home() / "AppData" / "Local" / "Ollama" / "server.log"


def flash_attention_from_server_log() -> str | None:
    """Read the flash-attention flag the *running server* actually started
    with, straight from its log -- not this process's environment, which may
    differ from the server's. None if the log cannot be read or the line is
    absent."""
    try:
        text = SERVER_LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    matches = re.findall(r"OLLAMA_FLASH_ATTENTION:(true|false)", text)
    return matches[-1] if matches else None


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    profile_id = sys.argv[1]

    fa_state = flash_attention_from_server_log()
    if fa_state != "true":
        print(
            "FATAL: server log does not confirm OLLAMA_FLASH_ATTENTION:true "
            f"(saw {fa_state!r}). Refusing to run an FA-on re-measure against a "
            "server that is not demonstrably FA-on."
        )
        return 1

    profile_doc = load_profile(profile_id)
    ollama_version = get_ollama_version() or "unknown"

    digests = {}
    for m in CANDIDATE_MODELS:
        d = get_model_digest(m)
        if d is None:
            print(f"FATAL: model {m} is not installed; cannot run Phase 0.")
            return 1
        digests[m] = d

    runs: list[dict] = []
    total = len(CANDIDATE_MODELS) * len(FIXTURE_SPECS) * 2
    n = 0

    for model_tag in CANDIDATE_MODELS:
        for state in ("cold", "warm"):
            if state == "warm":
                # Unrecorded priming run so "warm" measures a resident model.
                unload_model(model_tag)
                run_one(FIXTURE_SPECS[0], model_tag, digests[model_tag], profile_id,
                        ollama_version, "cold")
            for spec in FIXTURE_SPECS:
                n += 1
                print(f"[{n}/{total}] {model_tag} {state} {spec.fixture_id} ...", flush=True)
                r = run_one(spec, model_tag, digests[model_tag], profile_id,
                            ollama_version, state)
                runs.append(r)
                print(
                    f"      total={r['local_total_duration_ms']:.0f}ms "
                    f"prefill={r['prompt_prefill_duration_ms']}ms "
                    f"valid={r['structurally_valid']} "
                    f"cite={r['citation_integrity']} "
                    f"class={r['classification']}",
                    flush=True,
                )
        unload_model(model_tag)

    summaries = [summarise(runs, m) for m in CANDIDATE_MODELS]

    document = {
        "phase": "0",
        "protocol_version": "v3",
        "run_label": "FA-ON re-measure",
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "local_intel_version": __version__,
        "serving_config": {
            "flash_attention_enabled": True,
            "flash_attention_source": "OLLAMA_FLASH_ATTENTION=1 (Windows User env, persistent)",
            "flash_attention_verified_from": str(SERVER_LOG),
            "flash_attention_log_value": fa_state,
        },
        "config_identity_note": (
            "invocation_configuration_id (§9) does NOT encode the flash-attention "
            "flag in protocol v3, so these FA-on runs carry the same config-id as "
            "the FA-off DEFER runs. The FA distinction is recorded here out-of-band. "
            "Whether flash attention becomes part of §9/§14 configuration identity "
            "is an open human call (WORKLOG 2026-09-05)."
        ),
        "supersedes_note": (
            "Does NOT overwrite or reverse phase0_smoke_%s.json, which remains the "
            "FA-off evidence grounding DEFER_LOCAL_MODEL_PATH. This is a distinct "
            "serving configuration measured at user request; the pre-committed §6 "
            "decision on these numbers is a human, versioned act (§17)." % profile_id
        ),
        "kill_thresholds": KILL_THRESHOLDS,
        "hardware_profile": profile_doc["profile"],
        "hardware_profile_hash": profile_doc["profile_hash"],
        "fixture_set_version": json.loads(
            Path("fixtures/manifest.json").read_text(encoding="utf-8")
        )["fixture_set_version"],
        "fixture_provenance": "SYNTHETIC -- see fixtures/manifest.json",
        "generation_parameters": GenerationParameters().__dict__,
        "invocation_timeout_ms": INVOCATION_TIMEOUT_MS,
        "summaries": summaries,
        "runs": runs,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"phase0_smoke_{profile_id}_fa-on_{RUN_DATE}.json"
    if out.exists():
        print(f"FATAL: {out} already exists; refusing to overwrite a prior FA-on run.")
        return 1
    out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")

    print("\n=== §6 summary (FA-ON) ===")
    for s in summaries:
        print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
