"""Complete configuration identity (§9).

Every artifact, session, and evaluation event requires an immutable
`invocation_configuration_id` derived from canonicalized configuration
values. Law 9: every artifact must be attributable to its complete
invocation configuration.

Changing generation parameters creates a NEW candidate configuration, not a
variant of an existing one (§9 "Pre-committed generation parameters").
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GenerationParameters:
    """Frozen before Phase 1a per §9. Phase 0 uses greedy decoding so that
    repeated runs measure runtime nondeterminism only, not model sampling
    variance -- §12 requires stating which interpretation applies."""

    temperature: float = 0.0
    top_p: float = 1.0
    top_k: int = 1
    seed: int | None = 0
    num_ctx: int = 32768
    max_output_tokens: int = 1800

    @property
    def decoding_interpretation(self) -> str:
        if self.temperature == 0.0:
            return "greedy: repetitions measure runtime nondeterminism only"
        return "sampled: repetitions measure model stability"


@dataclass(frozen=True)
class HardwareProfile:
    """§6 target hardware profile -- part of reproducibility context and of
    the batch identity."""

    machine_profile_id: str
    cpu_model: str
    system_ram_gb: float | None
    gpu_model: str | None
    gpu_vram_gb: float | None
    gpu_driver_version: str | None
    os_version: str
    ollama_version: str
    local_intel_version: str
    # §6 lists storage type as required "when material to load time". On this
    # class of hardware a multi-GB model load is disk-bound when cold, so it
    # is always recorded rather than judged material case by case.
    storage_type: str | None = None
    power_profile: str | None = None
    cpu_cores: int | None = None
    cpu_threads: int | None = None
    model_store_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def profile_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class InvocationConfiguration:
    worker_id: str
    worker_version: str
    provider: str
    model_tag: str
    model_digest: str
    prompt_text: str
    schema_hash: str
    schema_version: str
    validator_version: str
    evidence_packet_version: str
    packet_builder_version: str
    worker_view_builder_version: str
    truncation_strategy_version: str
    generation: GenerationParameters
    timeout_ms: int
    keep_alive: str
    hardware_profile_id: str
    ollama_version: str
    # Phase 1b presentation-layer identity (§5). Null in Phase 0/1a, which
    # have no presentation layer -- recorded explicitly rather than omitted
    # so that a Phase 1b config is never mistaken for a Phase 0 one.
    presentation_contract_version: str | None = None
    artifact_renderer_version: str | None = None
    span_retrieval_tool_version: str | None = None
    available_tool_set_hash: str | None = None
    fixture_set_version: str | None = None
    redaction_version: str | None = None

    @property
    def prompt_hash(self) -> str:
        return hashlib.sha256(self.prompt_text.encode("utf-8")).hexdigest()

    def canonical_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Store the prompt by hash, not by full text: the id must be stable
        # and compact, and the full text lives in the ledger.
        d.pop("prompt_text")
        d["prompt_hash"] = self.prompt_hash
        return d

    def invocation_configuration_id(self) -> str:
        canonical = json.dumps(self.canonical_dict(), sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def detect_hardware_profile(
    machine_profile_id: str,
    ollama_version: str,
    local_intel_version: str,
) -> HardwareProfile:
    """Best-effort autodetection. Any field that cannot be determined is
    recorded as None rather than guessed -- a wrong hardware profile
    silently corrupts reproducibility context for every batch that cites it."""
    cpu_model = platform.processor() or platform.machine() or "unknown"

    system_ram_gb: float | None = None
    gpu_model: str | None = None
    gpu_vram_gb: float | None = None
    gpu_driver_version: str | None = None
    storage_type: str | None = None
    power_profile: str | None = None
    cpu_cores: int | None = None
    cpu_threads: int | None = None

    model_store_path = os.environ.get("OLLAMA_MODELS") or str(
        Path.home() / ".ollama" / "models"
    )

    if platform.system() == "Windows":
        ram_out = _run(
            ["powershell", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"]
        )
        if ram_out and ram_out.isdigit():
            system_ram_gb = round(int(ram_out) / (1024 ** 3), 1)

        cpu_out = _run(
            ["powershell", "-NonInteractive", "-Command",
             "$c=Get-CimInstance Win32_Processor|Select-Object -First 1;"
             "\"$($c.Name)|$($c.NumberOfCores)|$($c.NumberOfLogicalProcessors)\""]
        )
        if cpu_out and "|" in cpu_out:
            name, cores, threads = (cpu_out.split("|") + ["", ""])[:3]
            cpu_model = name.strip() or cpu_model
            cpu_cores = int(cores) if cores.strip().isdigit() else None
            cpu_threads = int(threads) if threads.strip().isdigit() else None

        scheme = _run(["powercfg", "/getactivescheme"])
        if scheme and "(" in scheme:
            power_profile = scheme.rsplit("(", 1)[-1].rstrip(")").strip()

        # Media type of the physical disk actually holding the model store,
        # resolved through drive letter -> partition -> disk. A generic
        # "first disk in the machine" answer would be worthless here: this
        # box has three NVMe drives and the models sit on exactly one.
        drive_letter = Path(model_store_path).drive.rstrip(":")
        if drive_letter:
            disk_out = _run(
                ["powershell", "-NonInteractive", "-Command",
                 f"$p=Get-Partition -DriveLetter {drive_letter};"
                 "$d=Get-PhysicalDisk -DeviceNumber $p.DiskNumber;"
                 "\"$($d.MediaType)|$($d.BusType)|$($d.FriendlyName)\""]
            )
            if disk_out and "|" in disk_out:
                media, bus, friendly = (disk_out.split("|") + ["", ""])[:3]
                storage_type = f"{media.strip()} ({bus.strip()}) {friendly.strip()}".strip()

    nvidia = _run(
        ["nvidia-smi",
         "--query-gpu=name,memory.total,driver_version",
         "--format=csv,noheader,nounits"]
    )
    if nvidia:
        first = nvidia.splitlines()[0]
        parts = [p.strip() for p in first.split(",")]
        if len(parts) == 3:
            gpu_model = parts[0]
            try:
                gpu_vram_gb = round(float(parts[1]) / 1024, 1)
            except ValueError:
                gpu_vram_gb = None
            gpu_driver_version = parts[2]

    return HardwareProfile(
        machine_profile_id=machine_profile_id,
        cpu_model=cpu_model,
        system_ram_gb=system_ram_gb,
        gpu_model=gpu_model,
        gpu_vram_gb=gpu_vram_gb,
        gpu_driver_version=gpu_driver_version,
        os_version=f"{platform.system()} {platform.version()}",
        ollama_version=ollama_version,
        local_intel_version=local_intel_version,
        storage_type=storage_type,
        power_profile=power_profile,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        model_store_path=model_store_path,
    )
