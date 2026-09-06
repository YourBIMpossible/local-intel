"""Phase 0 operational validation batch -- 2026-09-06.

    python run_phase0_operational.py <machine_profile_id>

Bounded, unattended. Answers two questions against the frozen §6 gates:
  A. warm-resident: is the local path viable for an active work session?
  B. true-cold (process-cold): does it meet the cold-start requirement?

Candidates: the two original Phase 0 models plus qwen3.5:9b as a
fully-GPU-resident control. Same fixtures, same `run_one`, same
`GenerationParameters`, same `summarise` as the original harness. Per
invocation it additionally records the 2026-09-06 runtime identity, a
timestamped 1 s hardware sampler, the server-log segment written during
the load, and `/api/ps` before/after each condition.

This script MEASURES and stops on the pre-declared stop conditions. It
does not decide anything (§17).
"""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

from local_intel import __version__
from local_intel.config_identity import GenerationParameters
from local_intel.hardware import load_profile
from local_intel.ollama_client import (
    get_loaded_models,
    get_model_digest,
    get_ollama_version,
    unload_model,
)
from local_intel.runtime_identity import (
    RUNTIME_IDENTITY_VERSION,
    RuntimeIdentity,
    parse_load_segment,
    read_gpu_identity,
    read_model_identity,
    read_residency,
    read_server_environment,
    server_log_offset,
    server_log_segment,
)
from fixtures.templates import FIXTURE_SPECS
from run_phase0_smoke import (
    INVOCATION_TIMEOUT_MS,
    KILL_THRESHOLDS,
    RESULTS_DIR,
    run_one,
    summarise,
)

RUN_DATE = "2026-09-06"
MODELS = ["qwen2.5-coder:14b", "qwen3-coder:30b-a3b-q4_K_M", "qwen3.5:9b"]
KEEP_ALIVE_REQUIRED_PREFIX = "30m"
TELEMETRY_DIR = RESULTS_DIR / "telemetry" / f"operational_{RUN_DATE}"
LOG_SEG_DIR = RESULTS_DIR / "server_log_segments" / f"operational_{RUN_DATE}"

# Pre-declared stop conditions (user directive 2026-09-06 §6).
STOP_MIN_AVAILABLE_RAM_MB = 4096          # sustained memory exhaustion
STOP_MAX_SAMPLER_GAP_S = 60.0             # desktop/system stall proxy
STOP_RUNNER_CRASH_MARKERS = ("exit status", "CUDA error", "panic:", "SIGSEGV",
                             "signal: ", "runner process has terminated")


class Sampler:
    """1 s hardware sampler. Records max inter-sample gap as a stall proxy:
    a thread that should tick every second but is starved for >60 s is the
    only host-side evidence of an unresponsive machine this driver has."""

    FIELDS = ["ts", "elapsed_s", "gpu_util_pct", "gpu_mem_used_mib", "gpu_power_w",
              "gpu_sm_clock_mhz", "gpu_mem_clock_mhz", "gpu_temp_c",
              "cpu_util_pct", "ram_available_mb"]

    def __init__(self, path: Path, interval_s: float = 1.0):
        self.path = path
        self.interval = interval_s
        self.rows: list[dict] = []
        self.gpu_query_failures = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _gpu(self) -> list[str] | None:
        try:
            out = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=utilization.gpu,memory.used,power.draw,clocks.sm,clocks.mem,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=True,
            ).stdout.strip()
            return [p.strip() for p in out.split(",")]
        except (OSError, subprocess.SubprocessError):
            return None

    def _loop(self) -> None:
        t0 = time.monotonic()
        psutil.cpu_percent(interval=None)
        while not self._stop.is_set():
            g = self._gpu()
            if g is None or len(g) < 6:
                self.gpu_query_failures += 1
                g = [None] * 6
            row = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "elapsed_s": round(time.monotonic() - t0, 3),
                "gpu_util_pct": _f(g[0]), "gpu_mem_used_mib": _f(g[1]), "gpu_power_w": _f(g[2]),
                "gpu_sm_clock_mhz": _f(g[3]), "gpu_mem_clock_mhz": _f(g[4]), "gpu_temp_c": _f(g[5]),
                "cpu_util_pct": psutil.cpu_percent(interval=None),
                "ram_available_mb": round(psutil.virtual_memory().available / 2**20),
            }
            self.rows.append(row)
            self._stop.wait(self.interval)

    def start(self) -> "Sampler":
        self._t.start()
        return self

    def stop(self) -> dict:
        self._stop.set()
        self._t.join(timeout=15)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.FIELDS)
            w.writeheader()
            w.writerows(self.rows)
        return self.summary()

    def summary(self) -> dict:
        def col(k):
            return [r[k] for r in self.rows if r[k] is not None]
        gaps = [b["elapsed_s"] - a["elapsed_s"] for a, b in zip(self.rows, self.rows[1:])]
        def agg(k):
            v = col(k)
            return {"max": max(v), "mean": round(statistics.fmean(v), 1), "min": min(v)} if v else None
        return {
            "csv": str(self.path),
            "samples": len(self.rows),
            "max_sample_gap_s": round(max(gaps), 3) if gaps else None,
            "gpu_query_failures": self.gpu_query_failures,
            "gpu_util_pct": agg("gpu_util_pct"),
            "gpu_mem_used_mib": agg("gpu_mem_used_mib"),
            "gpu_power_w": agg("gpu_power_w"),
            "gpu_sm_clock_mhz": agg("gpu_sm_clock_mhz"),
            "gpu_temp_c": agg("gpu_temp_c"),
            "cpu_util_pct": agg("cpu_util_pct"),
            "ram_available_mb": agg("ram_available_mb"),
        }


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class StopBatch(Exception):
    pass


def check_stop_conditions(sample: dict, log_segment: str, run: dict) -> None:
    if sample["gpu_query_failures"] >= 3:
        raise StopBatch(f"GPU disappeared from nvidia-smi ({sample['gpu_query_failures']} query failures)")
    if sample["max_sample_gap_s"] is not None and sample["max_sample_gap_s"] > STOP_MAX_SAMPLER_GAP_S:
        raise StopBatch(f"system stall proxy: sampler starved for {sample['max_sample_gap_s']} s")
    ram = sample["ram_available_mb"]
    if ram and ram["min"] < STOP_MIN_AVAILABLE_RAM_MB:
        raise StopBatch(f"memory exhaustion: available RAM fell to {ram['min']} MB")
    for m in STOP_RUNNER_CRASH_MARKERS:
        if m in log_segment:
            raise StopBatch(f"Ollama runner crash marker in server.log: {m!r}")
    kind = run.get("invocation_failure_kind")
    if kind and kind not in ("timeout", "unparseable"):  # unavailable/transport = server or runner gone
        raise StopBatch(f"invocation failure kind {kind!r}: {run.get('error')}")


def wait_unloaded(tag: str, timeout_s: float = 60) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        if not any(m.get("name") == tag for m in get_loaded_models()):
            return True
        time.sleep(0.5)
    return False


def ps_snapshot() -> list[dict]:
    return [{k: m.get(k) for k in ("name", "size", "size_vram", "context_length", "expires_at")}
            for m in get_loaded_models()]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    profile_id = sys.argv[1]
    started = datetime.now(timezone.utc)

    env = read_server_environment()
    if env.flash_attention != "true":
        print(f"FATAL: server banner OLLAMA_FLASH_ATTENTION={env.flash_attention!r}, need 'true'")
        return 1
    if not (env.keep_alive or "").startswith(KEEP_ALIVE_REQUIRED_PREFIX):
        print(f"FATAL: server banner OLLAMA_KEEP_ALIVE={env.keep_alive!r}, need {KEEP_ALIVE_REQUIRED_PREFIX}")
        return 1
    gpu0 = read_gpu_identity()
    if gpu0.name is None:
        print("FATAL: nvidia-smi unavailable at start")
        return 1

    profile_doc = load_profile(profile_id)
    ollama_version = get_ollama_version() or "unknown"
    gen = GenerationParameters()
    out = RESULTS_DIR / f"phase0_operational_{profile_id}_{RUN_DATE}.json"
    if out.exists():
        print(f"FATAL: {out} exists; refusing to overwrite evidence")
        return 1

    digests, identities = {}, {}
    for m in MODELS:
        d = get_model_digest(m)
        if d is None:
            print(f"FATAL: model {m} not installed")
            return 1
        digests[m] = d
        identities[m] = read_model_identity(m)

    # Disk-cache honesty: nothing here flushes the Windows file cache and
    # 96 GB of RAM will hold every model file that has been read today.
    disk_cache_condition = (
        "process-cold: model verified unloaded from Ollama via /api/ps before the request; "
        "Windows file cache NOT flushed (no admin cache flush performed) and all three model "
        "files were read earlier on 2026-09-06, so weights are very likely served from RAM "
        "page cache, not from NVMe. This is NOT a disk-cold measurement."
    )

    runs: list[dict] = []
    conditions: list[dict] = []
    abort: dict | None = None
    n = 0
    total = len(MODELS) * len(FIXTURE_SPECS) * 2

    try:
        for tag in MODELS:
            for state in ("cold", "warm"):
                cond = {"model": tag, "state": state,
                        "ps_before": ps_snapshot(), "started_utc": datetime.now(timezone.utc).isoformat()}
                if state == "warm":
                    # Preload once (unrecorded) so the warm runs measure a resident model.
                    unload_model(tag); wait_unloaded(tag)
                    off = server_log_offset()
                    run_one(FIXTURE_SPECS[0], tag, digests[tag], profile_id, ollama_version, "cold")
                    seg = server_log_segment(off)
                    LOG_SEG_DIR.mkdir(parents=True, exist_ok=True)
                    (LOG_SEG_DIR / f"{_slug(tag)}_warm_preload.log").write_text(seg, encoding="utf-8")
                    cond["preload_load_observation"] = parse_load_segment(seg).__dict__
                for spec in FIXTURE_SPECS:
                    n += 1
                    rid = f"{_slug(tag)}_{state}_{spec.fixture_id}"
                    print(f"[{n}/{total}] {rid} ...", flush=True)
                    if state == "cold":
                        unload_model(tag)
                        if not wait_unloaded(tag):
                            raise StopBatch(f"{tag} did not unload within 60 s")
                    gpu_start = read_gpu_identity()
                    off = server_log_offset()
                    sampler = Sampler(TELEMETRY_DIR / f"{rid}.csv").start()
                    t_req = time.perf_counter()
                    # run_one performs its own unload for state=="cold"; already unloaded, so it is a no-op.
                    r = run_one(spec, tag, digests[tag], profile_id, ollama_version, state)
                    wall_ms = (time.perf_counter() - t_req) * 1000
                    sample = sampler.stop()
                    seg = server_log_segment(off)
                    if state == "cold" or "offloaded" in seg:
                        LOG_SEG_DIR.mkdir(parents=True, exist_ok=True)
                        (LOG_SEG_DIR / f"{rid}.log").write_text(seg, encoding="utf-8")
                    load_obs = parse_load_segment(seg) if "offloaded" in seg else None
                    ident = RuntimeIdentity(
                        runtime_identity_version=RUNTIME_IDENTITY_VERSION,
                        server=env, gpu=gpu_start, model=identities[tag],
                        num_ctx_requested=gen.num_ctx, max_output_tokens=gen.max_output_tokens,
                        benchmark_condition="true-cold" if state == "cold" else "warm-resident",
                        disk_cache_condition=disk_cache_condition if state == "cold" else "n/a (resident)",
                        load=load_obs, residency_after=read_residency(tag),
                        prompt_eval_count=r["prompt_eval_count"], eval_count=r["generated_output_tokens"],
                    )
                    r["runtime_identity"] = ident.to_dict()
                    r["client_wall_ms"] = round(wall_ms, 1)
                    r["telemetry"] = sample
                    r["derived"] = _derived(r)
                    runs.append(r)
                    print(f"      total={r['local_total_duration_ms']:.0f}ms load={r['model_load_duration_ms']:.0f}ms "
                          f"prefill={r['prompt_prefill_duration_ms']:.0f}ms ({r['derived']['prefill_tok_s']} tok/s) "
                          f"decode={r['derived']['decode_tok_s']} tok/s valid={r['structurally_valid']} "
                          f"gpu_max={sample['gpu_util_pct'] and sample['gpu_util_pct']['max']}% "
                          f"gap={sample['max_sample_gap_s']}s", flush=True)
                    check_stop_conditions(sample, seg, r)
                cond["ps_after"] = ps_snapshot()
                cond["ended_utc"] = datetime.now(timezone.utc).isoformat()
                conditions.append(cond)
            unload_model(tag); wait_unloaded(tag)
    except StopBatch as e:
        abort = {"reason": str(e), "at_run": n, "utc": datetime.now(timezone.utc).isoformat()}
        print(f"\nSTOP CONDITION: {e}", flush=True)
        for tag in MODELS:
            try:
                unload_model(tag)
            except Exception:
                pass

    summaries = [summarise(runs, m) for m in MODELS]
    for s in summaries:
        s.update(_model_medians(runs, s["model"]))

    document = {
        "phase": "0",
        "protocol_version": "v3",
        "run_label": "operational validation batch (warm-resident + process-cold), FA on, keep_alive 30m",
        "run_date": RUN_DATE,
        "started_utc": started.isoformat(),
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "local_intel_version": __version__,
        "runtime_identity_version": RUNTIME_IDENTITY_VERSION,
        "server_environment": env.__dict__,
        "gpu_at_start": gpu0.__dict__,
        "kill_thresholds": KILL_THRESHOLDS,
        "hardware_profile": profile_doc["profile"],
        "hardware_profile_hash": profile_doc["profile_hash"],
        "fixture_set_version": json.loads(Path("fixtures/manifest.json").read_text(encoding="utf-8"))["fixture_set_version"],
        "generation_parameters": gen.__dict__,
        "invocation_timeout_ms": INVOCATION_TIMEOUT_MS,
        "stop_conditions": {
            "min_available_ram_mb": STOP_MIN_AVAILABLE_RAM_MB,
            "max_sampler_gap_s": STOP_MAX_SAMPLER_GAP_S,
            "runner_crash_markers": STOP_RUNNER_CRASH_MARKERS,
        },
        "aborted": abort,
        "conditions": conditions,
        "summaries": summaries,
        "runs": runs,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")
    print("\n=== summary ===")
    for s in summaries:
        print(json.dumps(s, indent=2))
    return 3 if abort else 0


def _slug(tag: str) -> str:
    return tag.replace(":", "_").replace("/", "_")


def _derived(r: dict) -> dict:
    pe, pd = r.get("prompt_eval_count"), r.get("prompt_prefill_duration_ms")
    ec, gd = r.get("generated_output_tokens"), r.get("generation_duration_ms")
    return {
        "prefill_tok_s": round(pe / pd * 1000, 1) if pe and pd else None,
        "decode_tok_s": round(ec / gd * 1000, 1) if ec and gd else None,
        "inference_only_ms": (round(r["local_total_duration_ms"] - (r.get("model_load_duration_ms") or 0), 1)
                              if r.get("local_total_duration_ms") is not None else None),
    }


def _model_medians(runs: list[dict], tag: str) -> dict:
    def med(state, key, sub=None):
        vals = []
        for r in runs:
            if r["model"] != tag or r["model_load_state"] != state:
                continue
            v = r[sub][key] if sub else r.get(key)
            if v is not None:
                vals.append(v)
        return round(statistics.median(vals), 1) if vals else None
    def tel(state, key, agg):
        vals = [r["telemetry"][key][agg] for r in runs
                if r["model"] == tag and r["model_load_state"] == state and r["telemetry"].get(key)]
        return round(max(vals) if agg == "max" else statistics.median(vals), 1) if vals else None
    return {
        "cold_median_load_ms": med("cold", "model_load_duration_ms"),
        "cold_median_inference_only_ms": med("cold", "inference_only_ms", "derived"),
        "cold_median_prefill_tok_s": med("cold", "prefill_tok_s", "derived"),
        "warm_median_prefill_tok_s": med("warm", "prefill_tok_s", "derived"),
        "warm_median_decode_tok_s": med("warm", "decode_tok_s", "derived"),
        "median_prompt_tokens": med("warm", "prompt_eval_count"),
        "median_output_tokens": med("warm", "generated_output_tokens"),
        "warm_gpu_util_max_pct": tel("warm", "gpu_util_pct", "max"),
        "warm_gpu_mem_max_mib": tel("warm", "gpu_mem_used_mib", "max"),
        "warm_gpu_power_max_w": tel("warm", "gpu_power_w", "max"),
        "warm_gpu_temp_max_c": tel("warm", "gpu_temp_c", "max"),
        "cold_gpu_mem_max_mib": tel("cold", "gpu_mem_used_mib", "max"),
        "max_sampler_gap_s": max((r["telemetry"]["max_sample_gap_s"] or 0 for r in runs if r["model"] == tag), default=None),
        "min_ram_available_mb": min((r["telemetry"]["ram_available_mb"]["min"] for r in runs
                                     if r["model"] == tag and r["telemetry"].get("ram_available_mb")), default=None),
    }


if __name__ == "__main__":
    sys.exit(main())
