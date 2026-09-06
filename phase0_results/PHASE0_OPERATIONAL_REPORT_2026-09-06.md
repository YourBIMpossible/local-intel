# Phase 0 operational follow-up — decision report (2026-09-06)

**Question answered:** Is local Ollama viable for a normal active work session, and does it meet the cold-start requirement?

**Answer:** **LOCAL PATH WORKS for active warm-session use.**
**Cold-start gate (§6, 60,000 ms): PASS** for both candidate models (process-cold; see honesty note).
**Recommendation: B — revise `DEFER_LOCAL_MODEL_PATH` to warm-session-only.** (Human decision; nothing frozen was modified.)

Governance: §6 thresholds, §9 parameters, §13 discipline, the DEFER decision, and candidate selection are untouched. This report is evidence for a human-approved, versioned decision (§17).

## 1. Configuration identity (read live, not inferred)

| Fact | Value | Source |
|---|---|---|
| Ollama | 0.32.14 | /api/version |
| GPU / driver | NVIDIA GeForce RTX 5080, 616.56 | nvidia-smi |
| VRAM total / used / free at batch start | 16,303 / 4,715 / 11,263 MiB | nvidia-smi |
| OLLAMA_FLASH_ATTENTION effective | true (`flash_attn = enabled` in every load segment) | server.log banner + load segments |
| OLLAMA_KEEP_ALIVE effective | 30m0s | server.log banner |
| KV cache type | server default, f16/f16 in every load | load segments |
| num_ctx | 32768 requested and logged | §9 / load segments |
| Output cap | 1800 (§9) | — |
| Benchmark conditions | true-cold (process-cold) and warm-resident | driver |
| Disk-cache condition | process-cold only: verified unloaded via /api/ps; Windows page cache NOT flushed; all files read earlier today. Not disk-cold. | driver |

| Model | Digest (short) | Quant / size | Layers offloaded | Overflow to RAM | Projector | Prompt tok (median) |
|---|---|---|---|---|---|---|
| qwen2.5-coder:14b | 9ec8897f | Q4_K_M, 8.99 GB | 47/49 | 0 | no | 27,329 |
| qwen3-coder:30b-a3b-q4_K_M | 06c1097e | Q4_K_M, 18.56 GB | 49/49 | 21 layers overflowing | no | 27,308 |
| qwen3.5:9b (control) | 6488c96f | Q4_K_M, 6.59 GB | 34/34 | 0 | yes (vision) | 27,334 |

Note: 14B is not fully GPU-resident at this VRAM budget (2 layers on CPU) because ~4.7 GB of VRAM was held by other applications at start.

## 2. Pass/fail per model × condition (§6 gates: warm ≤20,000 ms, cold ≤60,000 ms, validity ≥3/5)

| Model | Cold median total | Cold gate | Warm median total | Warm gate | Validity cold / warm | Citation | All §6 |
|---|---|---|---|---|---|---|---|
| qwen2.5-coder:14b | 23,768 ms | PASS | 17,977 ms | PASS | 5/5 / 5/5 | 10/10 | **PASS** |
| qwen3-coder:30b-a3b | 25,126 ms | PASS | 16,369 ms | PASS | 5/5 / 5/5 | 10/10 | **PASS** |
| qwen3.5:9b (control) | 16,393 ms | PASS | 8,403 ms | PASS | 0/5 / 0/5 | 0/0 | FAIL (validity) |

Contrast with the earlier FA-on smoke (`PHASE0_REPORT_FA-ON_2026-09-06.md`) and the FA-off original, which both missed the gates: the difference this time is a warm server with FA confirmed on and keep-alive 30m, plus load time measured separately.

## 3. Breakdown (medians; per-run table in the JSON)

| Model | Cold load | Cold inference-only | Prefill tok/s (cold / warm) | Decode tok/s (warm) | Output tok | Peak VRAM (MiB) | Peak GPU power / temp |
|---|---|---|---|---|---|---|---|
| 14B | 4,108 ms | 19,365 ms | 2,042 / 2,143 | 30.1 | 125 | 15,837 | 336 W / 64 °C |
| 30B-A3B | 7,865 ms | 17,791 ms | 2,144 / 2,231 | 54.0 | 192 | 14,977 | 244 W / 58 °C |
| 9B control | 3,709 ms | 12,684 ms | 5,267 / 5,278 | 89.5 | 650 | 8,349 | 298 W / 60 °C |

Observations:
- **Prefill dominates.** At ~27k prompt tokens, prefill is 10–14 s for both candidates. Warm totals sit 2–4 s under the 20 s gate; a longer worker view would breach it.
- **First cold load of each model is 2–4× the later ones** (14B 22.0 s, 30B 16.6 s, 9B 17.8 s) even with the page cache warm. Worst single cold total: 58.0 s (14B, run 1), inside but close to the 60 s gate.
- **Warm f01 runs prefilled in 32–71 ms** — a prompt-cache hit from the unrecorded preload (same fixture). Excluded from nothing, but the warm medians are driven by f02–f05.
- **9B control:** latency fine; 0/5 validity is a harness incompatibility, not a model failure. `qwen3.5` is a thinking model; with no `think` flag the tokens land in the `thinking` field and `response` is empty → `unparseable`. A one-request diagnostic after the batch confirmed `think:false` returns valid JSON. The harness passes no think flag (§9 doesn't define one), so this was run as-is per the directive.
- **Classification accuracy** (not a §6 gate): 14B 8/10 on expected class (misses f01 both times), 30B 8/10 (misses f02 both times).

## 4. Telemetry and system-event findings

- Sampler: 1 s cadence, 30 CSVs in `phase0_results/telemetry/operational_2026-09-06/`. Max inter-sample gap 2.1 s (14B cold run 1); all others ≤1.45 s. No stall proxy fired (threshold 60 s).
- Min available RAM during batch: 38.7 GB. No memory-pressure stop.
- GPU query failures: 0. No crash markers in server.log (`exit status`, `CUDA error`, `panic:`, `SIGSEGV`, runner terminated): none in the batch window.
- Windows event log, window 18:05:33Z–18:22:47Z (+2 min): 3 events total, **0 flagged** (no nvlddmkm, display-driver, 4101/TDR, WHEA, Kernel-Power, BugCheck, Kernel-PnP).
- `ollama ps` before/after each condition recorded in `conditions[]`; models were verified absent before each cold pass.
- Conclusion wording per directive: **no driver-crash evidence observed** during 30 completed requests. This does not establish that no system issue exists.

## 5. Stop conditions

None triggered. Batch ran 18:05:33Z → 18:22:46Z (17 min 13 s), exit 0, Ollama returned to idle.

## 6. Honesty notes / limits

- Cold = process-cold, not disk-cold. A true first-of-day load from NVMe will be slower than the 3.7–7.9 s medians; the 16–22 s first-load values are the closer proxy.
- ~4.7 GB VRAM held by other apps; a cleaner GPU would offload 14B fully and likely improve it slightly.
- Desktop responsiveness measured only by the sampler-gap proxy, not by an interactive probe.
- Five fixtures per condition; medians over five are coarse.
- Driver reads 616.56 today (earlier notes said 610.88); recorded as read.

## 7. Artifacts

- Results: `phase0_results/phase0_operational_workstation-zeria-01_2026-09-06.json`
- Telemetry CSVs: `phase0_results/telemetry/operational_2026-09-06/`
- Server-log load segments: `phase0_results/server_log_segments/operational_2026-09-06/`
- Driver: `run_phase0_operational.py`; identity module: `local_intel/runtime_identity.py` (commit b4c9f59)
- Prior evidence: commit cbbbd6f (FA-on remeasurement)

## 8. Recommendation (exactly one)

**B — revise DEFER to warm-session-only.** Both candidates pass every §6 gate under FA-on + 30 m keep-alive when resident; cold also passes but with 20–60 s first-load exposure and no disk-cold measurement, so the local path should be scoped to sessions where the model is kept warm. Reopening candidate selection (C) is not needed on this evidence; keeping DEFER unchanged (A) would ignore a clean pass.

## 9. Disposition (added 2026-09-06, after human ruling)

Recommendation B accepted. See `decisions/2026-09-06-defer-revision-warm-session-only.md`. The `qwen3.5:9b` 0/5 validity is recorded there as a benchmark-output-handling limitation (thinking output in the `thinking` field, harness validated `response`), not a model failure.
