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

Evidence preservation (corrective revision, post-review 2026-09-06):
  * every artifact is keyed by a per-batch run id (UTC start time) and the
    driver refuses to start if any of its output paths already exist;
  * the results document is rewritten after every run and again in a
    `finally`, so a stop condition, an exception, or Ctrl-C leaves the
    completed runs, the abort reason, and the in-flight sampler CSV on disk;
  * local account paths are redacted to `<HOME>` before anything is written;
  * the per-request `keep_alive` is recorded separately from the server's
    `OLLAMA_KEEP_ALIVE`, because the request value overrides the server one.

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
import traceback
from dataclasses import dataclass
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
from local_intel.redact_paths import redact_local_paths
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
    REQUEST_KEEP_ALIVE,
    RESULTS_DIR,
    run_one,
    summarise,
)

MODELS = ["qwen2.5-coder:14b", "qwen3-coder:30b-a3b-q4_K_M", "qwen3.5:9b"]
KEEP_ALIVE_REQUIRED_PREFIX = "30m"      # server-side default required at start
RESULTS_ROOT = RESULTS_DIR              # tests point this at a temp dir
MANIFEST_PATH = Path(__file__).resolve().parent / "fixtures" / "manifest.json"
SAMPLER_JOIN_TIMEOUT_S = 15.0

# Pre-declared stop conditions (user directive 2026-09-06 §6).
STOP_MIN_AVAILABLE_RAM_MB = 4096          # sustained memory exhaustion
STOP_MAX_SAMPLER_GAP_S = 60.0             # desktop/system stall proxy
STOP_RUNNER_CRASH_MARKERS = ("exit status", "CUDA error", "panic:", "SIGSEGV",
                             "signal: ", "runner process has terminated")

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_STOP_CONDITION = 3
EXIT_INTERRUPTED = 130


@dataclass(frozen=True)
class RunPaths:
    """Every output path of one batch, keyed by its run id."""

    results_root: Path
    profile_id: str
    run_id: str

    @property
    def document(self) -> Path:
        return self.results_root / f"phase0_operational_{self.profile_id}_{self.run_id}.json"

    @property
    def telemetry_dir(self) -> Path:
        return self.results_root / "telemetry" / f"operational_{self.run_id}"

    @property
    def log_segment_dir(self) -> Path:
        return self.results_root / "server_log_segments" / f"operational_{self.run_id}"

    def existing(self) -> list[Path]:
        return [p for p in (self.document, self.telemetry_dir, self.log_segment_dir) if p.exists()]


def make_run_id(started: datetime) -> str:
    return started.strftime("%Y-%m-%dT%H%M%SZ")


class Sampler:
    """1 s hardware sampler. Records max inter-sample gap as a stall proxy:
    a thread that should tick every second but is starved for >60 s is the
    only host-side evidence of an unresponsive machine this driver has.

    `elapsed_s` is stamped BEFORE the nvidia-smi query so the gap measures
    scheduler wake-up latency, not query latency; the query's own duration
    is recorded separately in `gpu_query_ms`."""

    FIELDS = ["ts", "elapsed_s", "gpu_query_ms", "gpu_util_pct", "gpu_mem_used_mib",
              "gpu_power_w", "gpu_sm_clock_mhz", "gpu_mem_clock_mhz", "gpu_temp_c",
              "cpu_util_pct", "ram_available_mb"]

    def __init__(self, path: Path, interval_s: float = 1.0):
        self.path = path
        self.interval = interval_s
        self.rows: list[dict] = []
        self.gpu_query_failures = 0
        self.join_timed_out = False
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
            tick = time.monotonic()
            ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            # Count the failure BEFORE the query so a query that never returns
            # (wedged driver) is still visible as a failure in the summary.
            self.gpu_query_failures += 1
            g = self._gpu()
            query_ms = round((time.monotonic() - tick) * 1000, 1)
            if g is None or len(g) < 6:
                g = [None] * 6
            else:
                self.gpu_query_failures -= 1
            row = {
                "ts": ts,
                "elapsed_s": round(tick - t0, 3),
                "gpu_query_ms": query_ms,
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

    @property
    def running(self) -> bool:
        return self._t.is_alive()

    def stop(self) -> dict:
        """Signal, join (bounded), persist whatever rows exist, summarise.

        Idempotent: a second call re-persists and re-summarises. The CSV is
        written even when the join times out, and the timeout is recorded."""
        self._stop.set()
        if self._t.ident is not None:
            self._t.join(timeout=SAMPLER_JOIN_TIMEOUT_S)
        self.join_timed_out = self._t.is_alive()
        rows = list(self.rows)  # snapshot; an orphaned thread may still append
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.FIELDS)
            w.writeheader()
            w.writerows(rows)
        return self.summary(rows)

    def summary(self, rows: list[dict] | None = None) -> dict:
        rows = list(self.rows) if rows is None else rows

        def col(k):
            return [r[k] for r in rows if r[k] is not None]

        gaps = [b["elapsed_s"] - a["elapsed_s"] for a, b in zip(rows, rows[1:])]

        def agg(k):
            v = col(k)
            return {"max": max(v), "mean": round(statistics.fmean(v), 1), "min": min(v)} if v else None

        return {
            "csv": str(self.path),
            "samples": len(rows),
            "max_sample_gap_s": round(max(gaps), 3) if gaps else None,
            "gpu_query_failures": self.gpu_query_failures,
            "gpu_query_ms": agg("gpu_query_ms"),
            "sampler_join_timed_out": self.join_timed_out,
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


def _ms(x) -> str:
    """None-safe millisecond formatter for progress lines."""
    return f"{x:.0f}ms" if isinstance(x, (int, float)) else "n/a"


class StopBatch(Exception):
    pass


def check_stop_conditions(sample: dict, log_segment: str, run: dict) -> None:
    if sample["gpu_query_failures"] >= 3:
        raise StopBatch(f"GPU disappeared from nvidia-smi ({sample['gpu_query_failures']} query failures)")
    if sample.get("sampler_join_timed_out"):
        raise StopBatch(f"hardware sampler did not stop within {SAMPLER_JOIN_TIMEOUT_S:.0f} s (wedged nvidia-smi?)")
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


def write_document(path: Path, document: dict) -> None:
    """Serialise, redact local account paths, replace the file in one step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = redact_local_paths(json.dumps(document, indent=2, default=str)) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_log_segment(path: Path, segment: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_local_paths(segment), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return EXIT_USAGE
    profile_id = argv[0]
    started = datetime.now(timezone.utc)
    paths = RunPaths(Path(RESULTS_ROOT), profile_id, make_run_id(started))
    clash = paths.existing()
    if clash:
        print(f"FATAL: output path(s) already exist; refusing to overwrite evidence: {clash}")
        return 1

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
    # Read the manifest up front: a missing manifest must fail before the
    # batch, not after it (it used to be read only at document-write time).
    fixture_set_version = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["fixture_set_version"]

    digests, identities = {}, {}
    for m in MODELS:
        d = get_model_digest(m)
        if d is None:
            print(f"FATAL: model {m} not installed")
            return 1
        digests[m] = d
        identities[m] = read_model_identity(m)

    # Disk-cache honesty: nothing here flushes the Windows file cache, and a
    # large RAM will hold every model file read recently. The date is the
    # run's own, not a constant; whether the files were read earlier that day
    # is NOT measured, so it is stated as uncontrolled.
    disk_cache_condition = (
        "process-cold: model verified unloaded from Ollama via /api/ps before the request; "
        "Windows file cache NOT flushed (no admin cache flush performed). Whether the model "
        f"files were already page-cached on {started.date().isoformat()} is not controlled or "
        "measured; weights may be served from RAM page cache rather than from disk. "
        "This is NOT a disk-cold measurement."
    )

    document: dict = {
        "phase": "0",
        "protocol_version": "v3",
        "run_label": ("operational validation batch (warm-resident + process-cold), FA on, "
                      f"server OLLAMA_KEEP_ALIVE {env.keep_alive}, request keep_alive {REQUEST_KEEP_ALIVE}"),
        "run_id": paths.run_id,
        "run_date": started.date().isoformat(),
        "started_utc": started.isoformat(),
        "ended_utc": None,
        "complete": False,
        "local_intel_version": __version__,
        "runtime_identity_version": RUNTIME_IDENTITY_VERSION,
        "server_environment": env.__dict__,
        "request_keep_alive": REQUEST_KEEP_ALIVE,
        "keep_alive_note": ("The request-body keep_alive overrides the server's OLLAMA_KEEP_ALIVE for the "
                            "load it triggers; the effective residency window of every measured request "
                            "is request_keep_alive, confirmable from ps_after.expires_at."),
        "gpu_at_start": gpu0.__dict__,
        "kill_thresholds": KILL_THRESHOLDS,
        "hardware_profile": profile_doc["profile"],
        "hardware_profile_hash": profile_doc["profile_hash"],
        "hardware_profile_hash_note": ("hash computed over the unredacted profile as stored in "
                                       "hardware_profiles/; the copy above has local paths redacted."),
        "fixture_set_version": fixture_set_version,
        "generation_parameters": gen.__dict__,
        "invocation_timeout_ms": INVOCATION_TIMEOUT_MS,
        "stop_conditions": {
            "min_available_ram_mb": STOP_MIN_AVAILABLE_RAM_MB,
            "max_sampler_gap_s": STOP_MAX_SAMPLER_GAP_S,
            "runner_crash_markers": STOP_RUNNER_CRASH_MARKERS,
            "sampler_join_timeout_s": SAMPLER_JOIN_TIMEOUT_S,
        },
        "aborted": None,
        "conditions": [],
        "summaries": [],
        "runs": [],
    }
    return run_batch(document, paths, profile_id, env, gen, digests, identities,
                     ollama_version, disk_cache_condition)


def run_batch(document: dict, paths: RunPaths, profile_id: str, env, gen, digests: dict,
              identities: dict, ollama_version: str, disk_cache_condition: str) -> int:
    """Execute the batch. Always leaves a results document on disk."""
    runs: list[dict] = document["runs"]
    conditions: list[dict] = document["conditions"]
    n = 0
    total = len(MODELS) * len(FIXTURE_SPECS) * 2
    active_sampler: Sampler | None = None
    exit_code = EXIT_OK
    reraise: BaseException | None = None

    def finalize() -> None:
        document["summaries"] = [summarise(runs, m) for m in MODELS]
        for s in document["summaries"]:
            s.update(_model_medians(runs, s["model"]))
        document["ended_utc"] = datetime.now(timezone.utc).isoformat()
        write_document(paths.document, document)

    try:
        for tag in MODELS:
            for state in ("cold", "warm"):
                cond = {"model": tag, "state": state, "complete": False,
                        "ps_before": ps_snapshot(), "started_utc": datetime.now(timezone.utc).isoformat()}
                conditions.append(cond)  # before the loop, so an aborting condition is recorded
                if state == "warm":
                    # Preload once (unrecorded) so the warm runs measure a resident model.
                    unload_model(tag)
                    wait_unloaded(tag)
                    off = server_log_offset()
                    run_one(FIXTURE_SPECS[0], tag, digests[tag], profile_id, ollama_version, "cold",
                            keep_alive=REQUEST_KEEP_ALIVE)
                    seg = server_log_segment(off)
                    write_log_segment(paths.log_segment_dir / f"{_slug(tag)}_warm_preload.log", seg)
                    cond["preload_load_observation"] = parse_load_segment(seg).__dict__
                    cond["preload_fixture_id"] = FIXTURE_SPECS[0].fixture_id
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
                    active_sampler = Sampler(paths.telemetry_dir / f"{rid}.csv").start()
                    t_req = time.perf_counter()
                    # run_one performs its own unload for state=="cold"; already unloaded, so it is a no-op.
                    r = run_one(spec, tag, digests[tag], profile_id, ollama_version, state,
                                keep_alive=REQUEST_KEEP_ALIVE)
                    wall_ms = (time.perf_counter() - t_req) * 1000
                    sample = active_sampler.stop()
                    active_sampler = None
                    seg = server_log_segment(off)
                    if state == "cold" or "offloaded" in seg:
                        write_log_segment(paths.log_segment_dir / f"{rid}.log", seg)
                    load_obs = parse_load_segment(seg) if "offloaded" in seg else None
                    ident = RuntimeIdentity(
                        runtime_identity_version=RUNTIME_IDENTITY_VERSION,
                        server=env, gpu=gpu_start, model=identities[tag],
                        num_ctx_requested=gen.num_ctx, max_output_tokens=gen.max_output_tokens,
                        benchmark_condition="true-cold" if state == "cold" else "warm-resident",
                        disk_cache_condition=disk_cache_condition if state == "cold" else "n/a (resident)",
                        load=load_obs, residency_after=read_residency(tag),
                        prompt_eval_count=r.get("prompt_eval_count"), eval_count=r.get("generated_output_tokens"),
                        request_keep_alive=REQUEST_KEEP_ALIVE,
                    )
                    r["runtime_identity"] = ident.to_dict()
                    r["client_wall_ms"] = round(wall_ms, 1)
                    r["telemetry"] = sample
                    r["derived"] = _derived(r)
                    r["prompt_cache_note"] = (
                        "same fixture as the unrecorded warm preload; prefill may be a prompt-cache hit"
                        if state == "warm" and spec.fixture_id == FIXTURE_SPECS[0].fixture_id else None
                    )
                    runs.append(r)
                    gpu_util = sample.get("gpu_util_pct")
                    print(f"      total={_ms(r.get('local_total_duration_ms'))} load={_ms(r.get('model_load_duration_ms'))} "
                          f"prefill={_ms(r.get('prompt_prefill_duration_ms'))} ({r['derived']['prefill_tok_s']} tok/s) "
                          f"decode={r['derived']['decode_tok_s']} tok/s valid={r.get('structurally_valid')} "
                          f"failure={r.get('invocation_failure_kind')} "
                          f"gpu_max={gpu_util['max'] if gpu_util else None}% "
                          f"gap={sample['max_sample_gap_s']}s", flush=True)
                    write_document(paths.document, document)  # partial evidence survives a hard kill
                    check_stop_conditions(sample, seg, r)
                cond["ps_after"] = ps_snapshot()
                cond["ended_utc"] = datetime.now(timezone.utc).isoformat()
                cond["complete"] = True
            unload_model(tag)
            wait_unloaded(tag)
        document["complete"] = True
    except StopBatch as e:
        document["aborted"] = _abort("stop_condition", str(e), n)
        exit_code = EXIT_STOP_CONDITION
        print(f"\nSTOP CONDITION: {e}", flush=True)
    except KeyboardInterrupt:
        document["aborted"] = _abort("keyboard_interrupt", "KeyboardInterrupt", n)
        exit_code = EXIT_INTERRUPTED
        print("\nINTERRUPTED: partial results preserved", flush=True)
    except Exception as e:  # noqa: BLE001 -- recorded, persisted, then re-raised
        document["aborted"] = _abort("exception", f"{type(e).__name__}: {e}", n,
                                     traceback="".join(traceback.format_exception(e)))
        reraise = e
        print(f"\nEXCEPTION at run {n}: {type(e).__name__}: {e} -- partial results preserved", flush=True)
    finally:
        if active_sampler is not None:
            try:
                in_flight = active_sampler.stop()
                if document["aborted"] is not None:
                    document["aborted"]["in_flight_telemetry"] = in_flight
            except Exception as e:  # noqa: BLE001 -- never let cleanup mask the batch outcome
                if document["aborted"] is not None:
                    document["aborted"]["in_flight_telemetry_error"] = f"{type(e).__name__}: {e}"
        if document["aborted"] is not None:
            for tag in MODELS:
                try:
                    unload_model(tag)
                except Exception:  # noqa: BLE001
                    pass
        finalize()

    if reraise is not None:
        raise reraise
    print(f"\nWrote {paths.document}")
    print("\n=== summary ===")
    for s in document["summaries"]:
        print(json.dumps(s, indent=2))
    return exit_code


def _abort(kind: str, reason: str, at_run: int, **extra) -> dict:
    return {"kind": kind, "reason": reason, "at_run": at_run,
            "utc": datetime.now(timezone.utc).isoformat(), **extra}


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
            v = r[sub].get(key) if sub else r.get(key)
            if v is not None:
                vals.append(v)
        return round(statistics.median(vals), 1) if vals else None

    def tel(state, key, agg):
        vals = [r["telemetry"][key][agg] for r in runs
                if r["model"] == tag and r["model_load_state"] == state and r["telemetry"].get(key)]
        return round(max(vals) if agg == "max" else statistics.median(vals), 1) if vals else None

    mine = [r for r in runs if r["model"] == tag]
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
        "max_sampler_gap_s": max((r["telemetry"]["max_sample_gap_s"] or 0 for r in mine), default=None),
        "min_ram_available_mb": min((r["telemetry"]["ram_available_mb"]["min"] for r in mine
                                     if r["telemetry"].get("ram_available_mb")), default=None),
        "invocation_failures": sum(1 for r in mine if r.get("invocation_failure_kind")),
    }


if __name__ == "__main__":
    sys.exit(main())
