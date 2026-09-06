# /review-all — standard — 2026-09-06

Diff: `master...HEAD` on `claude/project-pause-status-f34b4e` (cbbbd6f, b4c9f59, 9c13ba3, 459d7b0). Lenses run blind in parallel: code-review, security-diff, concurrency (added by judgment: the diff introduces a sampler thread). BIM lenses inert (no BIM signals). Auto-gate evidence: unavailable (no gate agents in this repo; pytest 62 passed, none cover the new drivers). Read-only; nothing changed, committed, or pushed.

Convergence verified independently: `expires_at` in every condition's `ps_after` is ended_utc + ~10 min (six of six); 14B genuine warm runs 20,336 / 21,175 / 17,977 / 16,364 ms, median without the cache-hit run 19,157 ms.

## Ranked decision list

**HIGH — The batch ran under a 10-minute keep-alive, not the 30-minute one the decision record cites**
Location: [run_phase0_smoke.py:92](run_phase0_smoke.py:92) (`keep_alive="10m"` in the request body, reused by `run_one` in [run_phase0_operational.py:263](run_phase0_operational.py:263)); claimed in [PHASE0_OPERATIONAL_REPORT_2026-09-06.md](phase0_results/PHASE0_OPERATIONAL_REPORT_2026-09-06.md) §1 and [decisions/2026-09-06-defer-revision-warm-session-only.md](decisions/2026-09-06-defer-revision-warm-session-only.md) ruling 1
Raised by: code-review
Why retained: Per-request `keep_alive` overrides `OLLAMA_KEEP_ALIVE`. All six `ps_after.expires_at` values sit 10 min after the condition ended. `RuntimeIdentity` records only the server banner value. The library defaults to 5 m. The ruling's operating condition ("30-minute keep-alive, verified from the server banner") was not what was measured, and the server env alone will not deliver it in use.
Action: Record the request `keep_alive` in `RuntimeIdentity`; correct the report and decision wording to "server env 30m0s, requests sent keep_alive=10m"; make 30 m an explicit client setting. Latency numbers are unaffected. The decision text is a human-only record (§17): flag, do not self-edit.

**HIGH — Any non-StopBatch exception or Ctrl-C discards every completed run and the in-flight sampler CSV**
Location: [run_phase0_operational.py:252-357](run_phase0_operational.py:252)
Raised by: code-review, concurrency
Why retained: Only `except StopBatch` guards the loop; results JSON is written after it; no try/finally around `sampler.start()`/`stop()`; the daemon thread dies unflushed at exit. Both lenses independently traced the same path. The 900 s per-request timeout makes the exposure hours, not minutes.
Action: try/finally on the sampler; catch `BaseException`, write a partial document with `aborted={reason}`, re-raise; or write incrementally per run.

**HIGH — A timeout or transport failure crashes the print statement before the stop check runs**
Location: [run_phase0_operational.py:301-302](run_phase0_operational.py:301)
Raised by: concurrency
Why retained: On timeout `InvocationTelemetry` leaves load/prefill durations `None`; the `:.0f` format raises `TypeError`, which is not `StopBatch`, so it takes the path above. The one scenario the batch exists to capture (a model blowing the gate) destroys the evidence file.
Action: None-safe formatting or move the print after `check_stop_conditions`; combine with the fix above.

**MEDIUM — Warm f01 is a prompt-cache hit and carries the 14B warm-gate pass**
Location: [run_phase0_operational.py:259-261](run_phase0_operational.py:259) (preload uses `FIXTURE_SPECS[0]`); [PHASE0_OPERATIONAL_REPORT_2026-09-06.md](phase0_results/PHASE0_OPERATIONAL_REPORT_2026-09-06.md) §3 "Warm totals sit 2–4 s under the 20 s gate"
Raised by: code-review
Why retained: Two of four genuine 14B warm runs exceed 20,000 ms; median without the cache hit is 19,157 ms (passes by 0.8 s, not 2–4 s). Same pattern in the FA-on smoke. The §3 sentence is not supported for 14B.
Action: Preload with a fixture outside the measured set; amend the report to state 2/5 14B warm runs exceeded the gate and the margin is under 1 s.

**MEDIUM — Committed server-log segments and reports expose the local account name and machine fingerprint**
Location: [run_phase0_operational.py:264,285](run_phase0_operational.py:264); `phase0_results/server_log_segments/operational_2026-09-06/*` (18 files, commit 9c13ba3); FA-on report and JSON `flash_attention_verified_from`
Raised by: security-diff
Why retained: Segments are copied verbatim: `<HOME>\...` paths (~100 occurrences), full llama-server command line, ports, CPU/RAM/VRAM. Remote is a GitHub repo. No credentials or tokens found. Branch is unpushed, so this is fixable before publication.
Action: Redact `Path.home()` to `<HOME>` before write and in report/JSON path fields; rewrite the committed segments (or keep only `parse_load_segment` output, which is all the analysis uses).

**MEDIUM — FA-on driver checks the no-overwrite guard after a ~1 h run**
Location: [run_phase0_smoke_fa.py:180-183](run_phase0_smoke_fa.py:180)
Raised by: code-review
Why retained: `out.exists()` is evaluated after all runs; a same-day re-run exits 1 with no artifact. The operational driver already does this check first.
Action: Move the check to the top of `main()`.

**MEDIUM — Sampler join timeout is never checked; orphan thread and lost rows on a driver hang**
Location: [run_phase0_operational.py:93-103,128-141](run_phase0_operational.py:93)
Raised by: concurrency
Why retained: `join(timeout=15)` with no `is_alive()` check; a wedged nvidia-smi holds the thread, `stop()` returns, CSV is closed, the next run starts a second sampler. `gpu_query_failures` increments only after the subprocess returns, so the ≥3-failure stop condition can be missed on the very run where the GPU disappeared.
Action: Treat `is_alive()` after join as a stop condition and record it; count the failure before spawning nvidia-smi.

**LOW — Partial-run telemetry CSVs and log segments are silently overwritten on same-day re-run**
Location: [run_phase0_operational.py:132,264,276,285](run_phase0_operational.py:132) vs the JSON guard at 223-226
Raised by: security-diff
Why retained: Keyed by constant `RUN_DATE`, written before the JSON exists, no existence check. A later successful JSON can reference telemetry that belongs to a different attempt.
Action: Guard the directories at startup or suffix them with the batch start timestamp.

**LOW — `max_sample_gap_s` includes nvidia-smi latency, not just host starvation**
Location: [run_phase0_operational.py:109-122](run_phase0_operational.py:109)
Raised by: concurrency
Why retained: `elapsed_s` is stamped after `_gpu()` returns (up to 5 s timeout). The report labels the metric a host-stall proxy. Cannot cause a false abort at the 60 s threshold.
Action: Stamp before launching nvidia-smi; record nvidia-smi duration in its own column.

**LOW — Two `total_layers` fields with different semantics in one identity record**
Location: [local_intel/runtime_identity.py:113](local_intel/runtime_identity.py:113) vs [:147](local_intel/runtime_identity.py:147)
Raised by: code-review
Why retained: `/api/show` block_count (48) vs llama.cpp offload denominator (49, includes output layer); same name in the JSON.
Action: Rename one and document the +1.

**LOW — The qwen3.5:9b "thinking field" explanation is not in the committed evidence**
Location: [decisions/2026-09-06-defer-revision-warm-session-only.md](decisions/2026-09-06-defer-revision-warm-session-only.md) limitation paragraph; JSON records only the JSON-decode error
Raised by: code-review
Why retained: The post-batch `think:false` diagnostic was run but not committed; the harness captures neither raw `response` nor `thinking`. The ruling is human-made and stands; the gap is that its cited basis is unrecorded.
Action: Commit the diagnostic request/response or add raw-field capture, and reference it from the record.

**LOW — Date-specific disk-cache claim hardcoded in the driver**
Location: [run_phase0_operational.py:238-243](run_phase0_operational.py:238)
Raised by: code-review
Why retained: Constant string asserts files were read "earlier on 2026-09-06"; any other day emits a false provenance fact, contradicting the module's "nothing here is inferred".
Action: Derive from `RUN_DATE` or word as "not controlled".

**INFO — Aborting condition's record is dropped on StopBatch**
Location: [run_phase0_operational.py:303-309](run_phase0_operational.py:303)
Raised by: code-review
Action: Append `cond` before the fixture loop; fill `ps_after`/`ended_utc` in a finally.

## NOT RETAINED

- "`self.rows` appended cross-thread without a lock" (concurrency, info). Reason: the lens itself states no defect exists while the join completes; folded into the join-timeout finding above.
- `ruff` E702 multiple-statements-on-one-line (code-review). Reason: style only.
- Path traversal via model tag in `_slug`, argv `profile_id` in filenames, nvidia-smi invocation, log injection into stop conditions (security-diff, checked and cleared). Reason: `MODELS` is a constant, argv is operator-local, argv list has no shell, server.log never carries fixture text.

## Verified consistent (no finding)
All report medians, ratios, residency fractions, citation counts, offload counts, KV type, n_ctx, worst cold, min RAM, max gap, and cited commit hashes match the JSON. Log regexes match real llama.cpp lines.

## Consequence for the branch
The latency evidence and pass/fail table stand. Two documents overstate their own operating condition: the decision record's keep-alive claim and the report's warm-margin sentence. Both are human-owned text; the corrections belong in the same PR before the branch is pushed, alongside the redaction of committed log segments.
