"""Capture and persist the §6 target hardware profile.

The profile is reproducibility context and part of the batch identity: every
smoke-test and evaluation batch records it. Persisting it as a committed
file (rather than re-detecting at read time) is the point -- a profile that
silently re-detects would report today's machine for yesterday's numbers.

Re-running capture on changed hardware produces a NEW profile id and a new
batch boundary. It never overwrites an existing profile in place.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from local_intel import __version__
from local_intel.config_identity import HardwareProfile, detect_hardware_profile
from local_intel.ollama_client import DEFAULT_HOST, get_installed_models, get_ollama_version

PROFILE_SCHEMA_VERSION = "v1"
DEFAULT_PROFILE_DIR = Path("hardware_profiles")


def capture_profile(
    machine_profile_id: str,
    host: str = DEFAULT_HOST,
) -> tuple[HardwareProfile, dict[str, Any]]:
    """Detect the profile plus the observed local-model environment.

    Model residency is captured alongside the static profile because §6's
    latency thresholds are only interpretable against it: the same model tag
    on the same GPU behaves differently when it fits in VRAM than when it
    spills to CPU.
    """
    ollama_version = get_ollama_version(host) or "unknown"
    profile = detect_hardware_profile(
        machine_profile_id=machine_profile_id,
        ollama_version=ollama_version,
        local_intel_version=__version__,
    )
    environment = {
        "installed_models": get_installed_models(host),
        "ollama_host": host,
    }
    return profile, environment


def write_profile(
    profile: HardwareProfile,
    environment: dict[str, Any],
    notes: list[str],
    profile_dir: Path = DEFAULT_PROFILE_DIR,
) -> Path:
    profile_dir.mkdir(parents=True, exist_ok=True)
    path = profile_dir / f"{profile.machine_profile_id}.json"
    if path.exists():
        raise FileExistsError(
            f"{path} already exists. A hardware profile is immutable; capture "
            f"a new one under a new machine_profile_id instead of overwriting."
        )
    document = {
        "profile_schema_version": PROFILE_SCHEMA_VERSION,
        "profile": profile.to_dict(),
        "profile_hash": profile.profile_hash(),
        "environment": environment,
        "notes": notes,
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def load_profile(machine_profile_id: str, profile_dir: Path = DEFAULT_PROFILE_DIR) -> dict:
    path = profile_dir / f"{machine_profile_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))
