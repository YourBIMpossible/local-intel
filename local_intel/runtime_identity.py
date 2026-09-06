"""Runtime serving identity -- dated additive amendment, 2026-09-06.

§9 `InvocationConfiguration` (frozen) does not encode the serving layer:
flash attention, keep-alive, KV-cache type, GPU offload, driver version, or
the benchmark condition. The FA-off / FA-on Phase 0 runs therefore share an
`invocation_configuration_id` while differing by an order of magnitude in
latency. This module records those facts OUT-OF-BAND, per invocation,
without touching the frozen dataclass or its id.

Nothing here is inferred. Every field is read from the live server
(`/api/version`, `/api/show`, `/api/ps`, `/api/tags`), from `nvidia-smi`,
or from the server-log segment written during the load that served the
request. A field that cannot be read is `None`, never guessed.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_HOST = "http://localhost:11434"
SERVER_LOG = Path.home() / "AppData" / "Local" / "Ollama" / "server.log"

RUNTIME_IDENTITY_VERSION = "2026-09-06.1"


def _get_json(url: str, payload: dict | None = None, timeout_s: float = 10) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.loads(r.read().decode("utf-8"))


def _nvidia_smi(fields: str) -> list[str] | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return None
    return [p.strip() for p in out.split(",")]


@dataclass(frozen=True)
class ServerEnvironment:
    """Effective server configuration, read from the current server.log
    banner (the env block Ollama prints at startup), never from the shell
    environment -- the shell may be newer than the running process."""

    ollama_version: str | None
    flash_attention: str | None      # "true"/"false" as logged
    keep_alive: str | None           # e.g. "30m0s"
    kv_cache_type: str | None        # "" means server default (f16)
    max_loaded_models: str | None
    log_banner_line_no: int | None


def read_server_environment(host: str = DEFAULT_HOST) -> ServerEnvironment:
    try:
        version = _get_json(f"{host}/api/version").get("version")
    except Exception:
        version = None
    fa = ka = kv = mlm = None
    line_no = None
    if SERVER_LOG.exists():
        text = SERVER_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        for i in range(len(text) - 1, -1, -1):
            line = text[i]
            if "OLLAMA_FLASH_ATTENTION:" in line and "OLLAMA_KEEP_ALIVE:" in line:
                line_no = i + 1
                m = re.search(r"OLLAMA_FLASH_ATTENTION:(\w+)", line)
                fa = m.group(1) if m else None
                m = re.search(r"OLLAMA_KEEP_ALIVE:([^\s\]]+)", line)
                ka = m.group(1) if m else None
                m = re.search(r"OLLAMA_KV_CACHE_TYPE:([^\s\]]*)", line)
                kv = m.group(1) if m else None
                m = re.search(r"OLLAMA_MAX_LOADED_MODELS:(\d+)", line)
                mlm = m.group(1) if m else None
                break
    return ServerEnvironment(version, fa, ka, kv, mlm, line_no)


@dataclass(frozen=True)
class GpuIdentity:
    name: str | None
    driver_version: str | None
    vram_total_mib: int | None
    vram_used_mib_at_start: int | None
    vram_free_mib_at_start: int | None


def read_gpu_identity() -> GpuIdentity:
    p = _nvidia_smi("name,driver_version,memory.total,memory.used,memory.free")
    if not p or len(p) < 5:
        return GpuIdentity(None, None, None, None, None)
    return GpuIdentity(p[0], p[1], int(p[2]), int(p[3]), int(p[4]))


@dataclass(frozen=True)
class ModelIdentity:
    tag: str
    digest: str | None
    family: str | None
    parameter_size: str | None
    quantization: str | None
    size_bytes: int | None
    total_layers: int | None         # <arch>.block_count from /api/show
    native_context_length: int | None
    has_vision_projector: bool | None  # 'vision' capability advertised
    capabilities: list[str] = field(default_factory=list)


def read_model_identity(tag: str, host: str = DEFAULT_HOST) -> ModelIdentity:
    show = _get_json(f"{host}/api/show", {"model": tag})
    mi = show.get("model_info", {}) or {}
    det = show.get("details", {}) or {}
    caps = list(show.get("capabilities") or [])
    block = next((v for k, v in mi.items() if k.endswith(".block_count") and ".vision." not in k), None)
    ctx = next((v for k, v in mi.items() if k.endswith(".context_length") and ".vision." not in k), None)
    size = digest = None
    try:
        for m in _get_json(f"{host}/api/tags").get("models", []):
            if m.get("name") == tag or m.get("model") == tag:
                size, digest = m.get("size"), m.get("digest")
                break
    except Exception:
        pass
    return ModelIdentity(
        tag=tag, digest=digest, family=det.get("family"),
        parameter_size=det.get("parameter_size"), quantization=det.get("quantization_level"),
        size_bytes=size, total_layers=block, native_context_length=ctx,
        has_vision_projector=("vision" in caps), capabilities=caps,
    )


@dataclass(frozen=True)
class LoadObservation:
    """Facts from the server-log segment written while a model loaded."""

    offloaded_layers: int | None
    total_layers: int | None
    overflowing_layers: int | None   # layers whose weights spill to system RAM
    flash_attn_logged: str | None    # "enabled"/"disabled"/"auto"
    kv_cache_k_type: str | None
    kv_cache_v_type: str | None
    kv_cache_mib: float | None
    n_ctx: int | None
    projector_loaded: bool | None
    segment_chars: int


_RE_OFFLOAD = re.compile(r"offloaded (\d+)/(\d+) layers to GPU")
_RE_OVERFLOW = re.compile(r"\((\d+) overflowing\)")
_RE_FA = re.compile(r"flash_attn\s*=\s*(\w+)")
_RE_KV = re.compile(
    r"llama_kv_cache: size =\s*([\d.]+) MiB \(\s*(\d+) cells.*?K \((\w+)\).*?V \((\w+)\)"
)
_RE_PROJ = re.compile(r"(mmproj|clip_model_load|projector|vision model)", re.IGNORECASE)


def parse_load_segment(segment: str) -> LoadObservation:
    off = _RE_OFFLOAD.findall(segment)
    ov = _RE_OVERFLOW.findall(segment)
    fa = _RE_FA.findall(segment)
    kv = _RE_KV.search(segment)
    return LoadObservation(
        offloaded_layers=int(off[-1][0]) if off else None,
        total_layers=int(off[-1][1]) if off else None,
        overflowing_layers=int(ov[-1]) if ov else (0 if off else None),
        flash_attn_logged=fa[-1] if fa else None,
        kv_cache_k_type=kv.group(3) if kv else None,
        kv_cache_v_type=kv.group(4) if kv else None,
        kv_cache_mib=float(kv.group(1)) if kv else None,
        n_ctx=int(kv.group(2)) if kv else None,
        projector_loaded=(bool(_RE_PROJ.search(segment)) if segment else None),
        segment_chars=len(segment),
    )


def server_log_offset() -> int:
    return SERVER_LOG.stat().st_size if SERVER_LOG.exists() else 0


def server_log_segment(start: int) -> str:
    if not SERVER_LOG.exists():
        return ""
    with SERVER_LOG.open("rb") as f:
        f.seek(start)
        return f.read().decode("utf-8", errors="replace")


@dataclass(frozen=True)
class ResidencyObservation:
    """From /api/ps after the request: what the server says is resident."""

    resident: bool
    size_bytes: int | None = None
    size_vram_bytes: int | None = None
    gpu_fraction: float | None = None
    context_length: int | None = None
    expires_at: str | None = None


def read_residency(tag: str, host: str = DEFAULT_HOST) -> ResidencyObservation:
    try:
        models = _get_json(f"{host}/api/ps").get("models", [])
    except Exception:
        return ResidencyObservation(False)
    e = next((m for m in models if m.get("name") == tag or m.get("model") == tag), None)
    if e is None:
        return ResidencyObservation(False)
    size, vram = e.get("size"), e.get("size_vram")
    return ResidencyObservation(
        True, size, vram, round(vram / size, 4) if size and vram else None,
        e.get("context_length"), e.get("expires_at"),
    )


@dataclass(frozen=True)
class RuntimeIdentity:
    """Everything the amendment requires, per invocation."""

    runtime_identity_version: str
    server: ServerEnvironment
    gpu: GpuIdentity
    model: ModelIdentity
    num_ctx_requested: int
    max_output_tokens: int
    benchmark_condition: str          # "true-cold" | "warm-resident"
    disk_cache_condition: str         # stated honestly by the driver
    load: LoadObservation | None
    residency_after: ResidencyObservation
    prompt_eval_count: int | None     # actual input tokens counted by server
    eval_count: int | None            # actual output tokens

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
