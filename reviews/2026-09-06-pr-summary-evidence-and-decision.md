# PR-ready summary — local-intel evidence-and-decision branch

Branch: `claude/project-pause-status-f34b4e` → `master`
State: committed locally only. **Not pushed. No PR opened. Nothing merged.**

## PR title

`Phase 0 evidence: FA-on re-measure, operational batch, DEFER revision to warm-session-only (+ post-review corrections)`

## PR description

This is an **evidence-and-decision PR**. It adds the Phase 0 flash-attention re-measurement, the operational follow-up batch with telemetry and server-log segments, a dated additive runtime-identity amendment, the human ruling revising `DEFER_LOCAL_MODEL_PATH` to warm-session-only, and one corrective commit that fixes the findings of a converged branch review.

It does **not** begin Phase 1a. It does not modify `NORTHSTAR.md`, the frozen §6 / §9 / §13 protocol text or thresholds, the candidate model set, or the Phase 0 / Phase 1a admission decision. **No Phase 1a admission has been made.**

### Commits

| SHA | Kind | Content |
|---|---|---|
| `cbbbd6f` | evidence | FA-on re-measurement (`run_phase0_smoke_fa.py`, `phase0_smoke_*_fa-on_2026-09-06.json`, `PHASE0_REPORT_FA-ON_2026-09-06.md`) |
| `b4c9f59` | evidence | dated runtime-identity amendment (additive, out-of-band of §9 config id) |
| `9c13ba3` | evidence | operational batch: 30 requests, 3 models × cold/warm × 5 fixtures, per-run telemetry CSVs, 18 server-log segments, `PHASE0_OPERATIONAL_REPORT_2026-09-06.md` |
| `459d7b0` | decision (human ruling, §17) | `decisions/2026-09-06-defer-revision-warm-session-only.md` |
| `7681d4c` | **corrective** | see below |

### Corrective commit `7681d4c`

**Redaction / machine fingerprint**
- 18 server-log segments, both 2026-09-06 results JSON files, and the FA-on report: local account paths replaced bytewise with `<HOME>` (line-only diff: 132/132 in the log segments; CR/CRLF bytes preserved).
- New `local_intel/redact_paths.py`; all three drivers redact on write.
- Hardware specs (GPU, VRAM, CPU, RAM, driver, Ollama version) are intentionally kept: they are the §6 hardware-profile content.

**Operational runner `run_phase0_operational.py`**
- Partial results written after every run; abort kind, reason, run index and traceback recorded in `document["aborted"]` on exception, Ctrl-C (exit 130) or stop condition (exit 3). Non-StopBatch exceptions re-raised after persisting.
- Sampler stopped and CSV flushed in `finally` with bounded join; a join timeout is itself a recorded stop condition; in-flight telemetry summary attached on abort.
- `_ms()` None-safe formatting: timeout / transport failures are recorded (`failure=timeout`, `invocation_failures` counted) instead of crashing during print.
- Per-batch run id (UTC start) in every artifact path; startup refuses to run if the document, telemetry dir or log-segment dir already exists.
- `RuntimeIdentity` 2026-09-06.2 records `request_keep_alive` separately from `server.keep_alive`.
- Warm f01 runs tagged with `prompt_cache_note`.

**Factual corrections (measurements unchanged)**
- Keep-alive: every request in the batch carried `keep_alive=10m` (overrides the server env `OLLAMA_KEEP_ALIVE=30m0s`; all six `ps_after.expires_at` = condition end + ~10 min). No 30-minute client operating condition was measured. Corrected in the operational report (§1, §3, §8, §9, new §10), WORKLOG, README, runtime-identity amendment.
- 14B warm margin: "2–4 s under the gate" was computed on 5-run medians including the warm f01 prompt-cache hit (prefill 71 ms). Genuine warm runs: 14B 20,336 / 21,175 / 17,977 / 16,364 ms (median 19,157 ms, 2 of 4 over 20,000 ms); 30B-A3B 17,086 / 16,369 / 19,567 / 14,915 ms (median 16,728 ms, 0 over). The margin claim is removed.
- `qwen3.5:9b` 0/5 validity: the thinking-field explanation and the `think:false` diagnostic are not in committed evidence and are now marked **unverified**. Not treated as a model failure and not as a pass.
- Decision record: human ruling text left as written; a corrective note is appended recording both corrections for the decision-maker to adopt or reword.

### Diff summary (`git diff --stat master...HEAD`)

63 files changed, 15,573 insertions, 5 deletions.

| Area | Files |
|---|---|
| Code | `run_phase0_operational.py` (+582), `run_phase0_smoke_fa.py` (+196), `local_intel/runtime_identity.py` (+249), `local_intel/redact_paths.py` (+40), `run_phase0_smoke.py` (±10) |
| Tests | `tests/test_operational_runner.py` (+342), `tests/test_redact_paths.py` (+48) |
| Evidence | 2 results JSON (+5,537), 18 server-log segments (+7,372), 30 telemetry CSVs (+722) |
| Reports / decisions | operational report (+105), FA-on report (+116), decision record (+55), runtime-identity amendment (+45), WORKLOG (+157 net), README (±2) |

Untouched: `NORTHSTAR.md`, protocol §6/§9/§13, candidate list, `phase0_smoke_workstation-zeria-01.json` (FA-off DEFER evidence), the untracked drafts `phase0-reconsideration.md` and `phase1-protocol-amendment.draft.md` (input only, not staged).

### Test evidence

`python -m pytest -q` → **82 passed** (62 pre-existing + 20 new). No benchmark rerun.

New focused tests (`tests/test_operational_runner.py`, 13):
- completed batch writes document, `complete=True`, `request_keep_alive="10m"` recorded separately from server keep-alive
- timeout run with `None` durations recorded (`load=n/a`, `failure=timeout`, `invocation_failures==1`), no crash
- `_ms(None)` / `_ms(float)` formatting
- injected `RuntimeError` mid-batch: 2 completed runs persisted, `aborted.kind="exception"`, traceback recorded, exception re-raised
- `KeyboardInterrupt` → exit 130, partial document written
- sampler CSV flushed on abort, `in_flight_telemetry` attached
- stop condition (CUDA error marker in server log) → exit 3, models unloaded
- sampler join timeout recorded and treated as a stop condition
- sampler stamps elapsed before the GPU query
- refuses to start when the output document already exists
- two batches never share document / telemetry / log-segment paths
- no local account path reaches disk (`<HOME>` present in document and segments)
- redaction still applied on the abort path

`tests/test_redact_paths.py` (7): single/double-backslash/forward-slash paths, actual home dir in all spellings, hardware facts untouched, `contains_local_path`, idempotence.

Redaction verification: `git grep` for the account path over HEAD finds it only in the two master-era files listed below.

### Known limitations that remain

1. **Two master-era files still contain the account path**: `hardware_profiles/workstation-zeria-01.json` (`model_store_path`) and `phase0_results/phase0_smoke_workstation-zeria-01.json` (FA-off DEFER evidence). Not touched: the smoke JSON is the byte-preserved DEFER basis and the profile feeds `hardware_profile_hash`.
2. **`hardware_profile_hash`** in both 2026-09-06 JSON files was computed over the unredacted profile. Redacting the profile would change the hash and break the link.
3. **Warm medians in the JSON `summaries`** (14B 17,977 / 30B 16,369 / 9B 8,403 ms) still include the f01 prompt-cache-hit run. The reports now state the genuine 4-run figures; the JSON is left as measured.
4. **No committed evidence for the `qwen3.5:9b` output-handling cause.** Harness stores neither raw `response` nor a `thinking` field.
5. **No 30-minute client keep-alive condition was ever measured**; the ruling's "30 m keep-alive" refers to server policy.
6. **Two `total_layers` semantics** coexist in the residency data (Ollama `ps` vs. server-log `offloaded N/M`); documented, not reconciled.
7. Existing 2026-09-06 artifacts keep the old `RUN_DATE`-keyed naming; only future batches get run-id paths.
8. The profile id `workstation-zeria-01` (in filenames and content) is a chosen identifier, not a filesystem path, and was left as-is.

### Explicit statement

**No Phase 1a admission has been made.** This PR records evidence and a human ruling on DEFER scope; the §6 pass/fail table on 5-run medians stands as measured, with the genuine-warm caveat for 14B stated in the report.

## Remaining decision questions (yours)

1. **Redact the two master-era files?** Doing so changes `hardware_profile_hash` and touches the byte-preserved FA-off DEFER evidence. Options: leave (current), redact + recompute hash + note in report, or redact only the profile.
2. **Run and commit a single `qwen3.5:9b` `think:false` diagnostic** so the unverified explanation becomes evidence? One request, ~30 s; not a benchmark rerun.
3. **Reword ruling text 1 and the limitation paragraph** in the decision record yourself, or adopt the appended corrective note as-is (human-owned file; I did not edit the ruling body).
4. **Make 30 m an explicit client `keep_alive` going forward**, or keep 10 m and change the ruling wording to "10 m measured window"?
5. **Should the 14B genuine-warm finding (2 of 4 over the gate) change the ruling?** The ruling relies on 5-run medians that include the cache hit; §17 makes that your call.

## Not done (by instruction)

- No push, no PR opened, no merge.
- No Phase 1a implementation.
- No AUTH-INH / WP0 material searched for, edited or included.
- No full benchmark rerun.
