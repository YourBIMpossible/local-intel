# Phase 0 re-measurement — flash attention ENABLED (2026-09-06)

**Status: MEASUREMENT ONLY. This does not reverse `DEFER_LOCAL_MODEL_PATH`
and does not decide anything.** The §6 decision table is pre-committed and
any state transition is a human, versioned act (§17). This report states
which gate rows the new numbers land on and nothing more.

Raw data: [`phase0_smoke_workstation-zeria-01_fa-on_2026-09-06.json`](phase0_smoke_workstation-zeria-01_fa-on_2026-09-06.json).
FA-off evidence grounding the DEFER is untouched:
[`phase0_smoke_workstation-zeria-01.json`](phase0_smoke_workstation-zeria-01.json)
and [`PHASE0_REPORT.md`](PHASE0_REPORT.md).

## Why this run exists

The original Phase 0 pass ran with the Ollama server default
`OLLAMA_FLASH_ATTENTION=false`. A hardware diagnostic (WORKLOG 2026-09-05)
showed that flag alone throttled prompt prefill to ~1.9 tok/s on this GPU
while it sat idle — the order of magnitude behind the 335 s / 902 s
latencies the DEFER rested on. The flag is now persistently on
(`OLLAMA_FLASH_ATTENTION=1`, Windows User env; confirmed
`OLLAMA_FLASH_ATTENTION:true` in `server.log`).

This run re-measures the **same** two candidates through the **same** frozen
harness — identical §6 thresholds, identical §9 `GenerationParameters`
(greedy, `num_ctx=32768`, `max_output_tokens=1800`), identical 5 synthetic
fixtures and 24K worker view — changing nothing but the flash-attention
flag. It reuses the original harness building blocks verbatim
([`run_phase0_smoke_fa.py`](../run_phase0_smoke_fa.py) imports `run_one` /
`summarise` from `run_phase0_smoke.py`).

## Results (medians, ms)

| Model | Metric | FA-off (DEFER) | FA-on (today) | §6 gate | Verdict |
|---|---|---:|---:|---|---|
| qwen2.5-coder:14b | warm total | 335,037 | **17,449** | `warm_e2e_max_ms` 20,000 | **PASS** (was 16.8× over) |
| qwen2.5-coder:14b | cold total | 902,056¹ | 78,415 | `cold_e2e_max_ms` 60,000 | FAIL (1.31× over) |
| qwen2.5-coder:14b | warm prefill | 328,109 | 11,825 | — | 27.7× faster |
| qwen2.5-coder:14b | cold model load | 5,272 | 56,037 | — | 10.6× **slower** (see anomaly) |
| qwen2.5-coder:14b | structural validity (warm) | 5/5 | 5/5 | ≥3/5 | PASS |
| qwen2.5-coder:14b | citation integrity | 7/7 | 10/10 | — | clean |
| qwen3-coder:30b-a3b | warm total | 169,784 | **15,579** | 20,000 | **PASS** (was 8.5× over) |
| qwen3-coder:30b-a3b | cold total | 902,044¹ | 99,357 | 60,000 | FAIL (1.66× over) |
| qwen3-coder:30b-a3b | warm prefill | 154,166 | 11,239 | — | 13.7× faster |
| qwen3-coder:30b-a3b | cold model load | 10,889 | 75,030 | — | 6.9× **slower** (see anomaly) |
| qwen3-coder:30b-a3b | structural validity (warm) | 5/5 | 5/5 | ≥3/5 | PASS |
| qwen3-coder:30b-a3b | citation integrity | 7/7 | 10/10 | — | clean |

¹ FA-off cold totals hit the 900 s invocation ceiling (recorded as
`timeout`); the true durations were longer.

Residency is unchanged from step 4 (FA does not change it): 14B 92.95% on
GPU, 30B 66.16% on GPU — both still spill to CPU at 32K context.

## What the numbers say

**1. Flash attention was the dominant latency factor, exactly as
hypothesised.** Inference latency collapsed: warm end-to-end dropped 19.2×
(14B) and 10.9× (30B), driven by a 14–28× prefill speedup. Both models now
**clear the warm latency gate they previously missed by 8–17×.**

**2. Output quality was never the problem, and still isn't.** Structural
validity 5/5 warm for both; citation integrity 10/10 for both. Consistent
with the original run, which also passed these cleanly.

**3. The cold gate still fails — but the cause has completely changed.**
Under FA-off, cold runs failed on catastrophic *prefill* (154–326 s). Under
FA-on, cold *inference* is healthy (~23–25 s of prefill+generation, which
would itself pass a 60 s gate). The cold failure is now **entirely model
load time**: 56 s (14B) and 75 s (30B), which alone exceed the 60 s cold
gate before a single token is processed.

## The cold-load anomaly (flagged, not resolved)

This is the one metric that got *worse*, and flash attention cannot explain
it — FA does not touch weight loading. In the **original FA-off** run these
same cold loads were 5.3 s (14B) and 10.9 s (30B) — NVMe-plausible on the
recorded store (Samsung 9100 PRO 4TB, `C:\Users\Zeria\.ollama\models`). In
this run they were 10× that.

Most likely environmental, specific to how this run was staged, not a
property of the models:

- The Ollama service was **freshly restarted** immediately before this run
  (to pick up the FA env var), so the OS file cache was cold; the original
  run's fast loads were very likely served from a warm cache.
- The harness unloads and **fully reloads** each model before every cold
  fixture. With `mmap` disabled on Windows+CUDA (server default here), each
  reload is a full read of 9–18 GB, and five back-to-back reloads per model
  can saturate/contend the store — cold prefill was also ~50% slower than
  warm in this run (18 s vs 12 s), consistent with I/O contention during the
  cold pass rather than a compute change.

A clean cold-gate verdict therefore needs this load path understood (re-run
with a warm cache; or measure the mmap-disabled load path directly). In
production the model is kept resident (`keep_alive`), so the warm numbers —
which now pass — are the operationally relevant ones. Whether the cold gate
should be measured under sustained-warm operation is a protocol question,
not a call this report makes.

## What this does and does not establish

- It **does** show the DEFER's headline latencies were dominated by a
  disabled serving-layer flag, not by model viability or VRAM spill: with
  the flag corrected, warm latency and all quality gates pass for both
  candidates.
- It **does not** clear both §6 gates: the cold gate fails on load time, so
  `meets_all_thresholds` is still `false` for both models.
- It **does not** reverse `DEFER_LOCAL_MODEL_PATH`, formalize flash
  attention into §9/§14 configuration identity, or admit any model to
  Phase 1a. Those are human, versioned acts (§17). The
  `invocation_configuration_id` in protocol v3 does **not** encode the FA
  flag, so these FA-on runs share a config-id with the FA-off runs; the FA
  distinction is recorded out-of-band in the result document.

See WORKLOG "Needs your call" (2026-09-06) for the open decisions this
raises.
