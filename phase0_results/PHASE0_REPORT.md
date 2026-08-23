# Phase 0 Smoke Test — Report

Run: `workstation-zeria-01`, 2026-08-22. Full data: `phase0_smoke_workstation-zeria-01.json`.
20/20 invocations completed (5 fixtures × 2 models × cold/warm).

## §6 summary (as computed by `run_phase0_smoke.py`)

| Model | Warm median (ms) | Cold median (ms) | Warm struct. validity | Citation integrity | Gate: warm | Gate: cold | Gate: struct | Meets all |
|---|---|---|---|---|---|---|---|---|
| qwen2.5-coder:14b | 335,223 | 335,223* | 5/5 | 7/7** | **FAIL** (≤20,000) | **FAIL** (≤60,000) | PASS (≥3/5) | **FAIL** |
| qwen3-coder:30b-a3b-q4_K_M | 164,290 | 902,059 | 5/5 | 7/7** | **FAIL** | **FAIL** | PASS | **FAIL** |

\* 14b cold median is dominated by three ~902,05x ms timeout ceilings (see below); the reported cold median in the script's own summary reflects this.
\*\* Citation integrity denominator excludes runs with no artifact (timeouts produced no artifact to check).

Both models miss both latency gates by a wide margin even after excluding the known measurement artifacts below. Both pass structural validity and citation integrity cleanly.

## Full per-run table

| Model | State | Fixture | Total ms | Valid | Cite OK | Classification |
|---|---|---|---|---|---|---|
| 14b | cold | f01_repeated_assertion | 902,056 | False | — | none (timeout) |
| 14b | cold | f02_compiler_type | 902,057 | False | — | none (timeout) |
| 14b | cold | f03_cascade_root_cause | 902,062 | False | — | none (timeout) |
| 14b | cold | f04_multiple_independent | 373,705 | True | True | multiple_independent_failures |
| 14b | cold | f05_environment_failure | 301,872 | True | True | environment_or_infrastructure_failure |
| 14b | warm | f01_repeated_assertion | 5,631 | True | True | multiple_independent_failures *(cache-primed, flag 1)* |
| 14b | warm | f02_compiler_type | 380,539 | True | True | multiple_independent_failures |
| 14b | warm | f03_cascade_root_cause | 359,989 | True | True | cascade_from_single_root_cause |
| 14b | warm | f04_multiple_independent | 335,037 | True | True | multiple_independent_failures |
| 14b | warm | f05_environment_failure | 285,631 | True | True | environment_or_infrastructure_failure |
| 30b | cold | f01_repeated_assertion | 201,753 | True | True | cascade_from_single_root_cause |
| 30b | cold | f02_compiler_type | 902,044 | False | — | none (timeout) |
| 30b | cold | f03_cascade_root_cause | 902,046 | False | — | none (timeout) |
| 30b | cold | f04_multiple_independent | 902,058 | False | — | none (timeout) |
| 30b | cold | f05_environment_failure | 158,725 | True | True | environment_or_infrastructure_failure |
| 30b | warm | f01_repeated_assertion | 10,565 | True | True | cascade_from_single_root_cause *(cache-primed, flag 1)* |
| 30b | warm | f02_compiler_type | 185,348 | True | True | cascade_from_single_root_cause **(misclassified, flag 4)** |
| 30b | warm | f03_cascade_root_cause | 172,828 | True | True | cascade_from_single_root_cause |
| 30b | warm | f04_multiple_independent | 169,784 | True | True | multiple_independent_failures |
| 30b | warm | f05_environment_failure | 143,232 | True | True | environment_or_infrastructure_failure |

Timeout rows (902,05x ms) hit `INVOCATION_TIMEOUT_MS = 900,000` — a deliberate ceiling set far above the 60s cold gate so real durations aren't clipped. GPU telemetry was checked live during one such run (99% util, 88W draw) confirming genuine inference, not a hang.

## Flags

**1. f01-warm cache-contamination artifact (methodology defect in `run_phase0_smoke.py`, not a model property).**
`main()` primes each model's warm state with an unrecorded invocation of `FIXTURE_SPECS[0]` (= f01) before the recorded warm loop begins. The next recorded call is also f01 with an identical prompt, so Ollama reuses cached prompt/KV state and returns in 5.6s (14b) / 10.6s (30b) — 50–70x faster than the model's other warm runs (285–380s / 143–185s). This is a measurement artifact, not evidence either model is fast when warm. It does not change any gate verdict: `statistics.median` of 5 values is unaffected by the single low outlier, and even excluding it entirely both models still miss `warm_e2e_max_ms` by 7–19x.

**2. Fixtures are synthetic, not real.** §6 kill thresholds are meant to be evaluated "at real worker-view sizes" against representative real test-log packets. The five fixtures used here are deterministic synthetic generations (`fixture_provenance: "SYNTHETIC"` in both the JSON output and `fixtures/manifest.json`), sized to hit the 24,000-token worker-view target but not drawn from an actual BIMpossible test run. This is a legitimate reason a human may want a second Phase 0 pass against real logs before treating this as final, even though the margin of failure here (7–45x over both gates) is large enough that real fixtures are unlikely to change the outcome.

**4. 30B misclassified f02 (compiler/type fixture) as `cascade_from_single_root_cause`** instead of the expected `multiple_independent_failures`, in both a passing structural-validity and citation-integrity run. Not a §6 gate (§6 doesn't grade classification accuracy), but worth carrying into Phase 1a's rubric design if the local path is ever revisited.

**5. Root cause, not a tuning problem.** As already recorded in `WORKLOG.md` at step 4: neither model fits fully in VRAM at `num_ctx=32768` (14b: 93% GPU; 30b: 66% GPU) on this 16GB RTX 5080. CPU spill is the most likely driver of these latencies. Lowering `num_ctx` to fit would create a different candidate configuration under §9, not a faster version of this one — not done.

## §6 decision

Per the pre-committed decision table:

> Neither model meets the thresholds at real worker-view sizes → **Stop before building the full harness; defer local model path.**

Both candidates fail their warm and cold latency gates, by 7–45x depending on the run, on synthetic fixtures at the frozen 24,000-token target. Structural validity and citation integrity are not the blocker — both are clean. This is a **recommendation**, not a self-executed decision: per north-star §17, admitting/deferring is a human, versioned act. Recorded here for your call in `WORKLOG.md`.
