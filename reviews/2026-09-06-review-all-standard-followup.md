# /review-all (standard) — follow-up pass on the post-review delta

**Date:** 2026-09-06
**Mode:** standard, read-only. **Invocation:** `/review-all` (no `--range`).
**Range reviewed:** `f54804f..HEAD` (= `3583cba`) — the two commits added *after*
the last committed review record (`f54804f`, `reviews/2026-09-06-review-all-standard.md`),
namely `e4efc6d` (final corrections: master-era redaction, committed 9B `think:false`
diagnostic, ruling amendment) and `3583cba` (keep-alive correction sidecar).

> **Why this range.** The branch `claude/project-pause-status-f34b4e` is now merged
> into `master` (PRs #1 and #2). Every standard diff resolution is therefore empty:
> `@{upstream}...HEAD`, `master...HEAD`, and the working tree all resolve to nothing
> (HEAD is an ancestor of `master`; no `main` exists). The only genuinely un-reviewed
> delta is what landed after the prior committed `/review-all`. The pre-`f54804f`
> history (`cbbbd6f`…`7681d4c`) was already reviewed and is merged/settled — not
> re-litigated here.

## Delta contents
- **Code (only executable file):** `run_diagnostic_think_false.py` (new, 216 lines) —
  one-shot `think:false` diagnostic for `qwen3.5:9b`. Explicitly not a Phase 0 run;
  feeds no §6 decision; candidate list unchanged.
- **Data:** `phase0_results/diagnostics/2026-09-06_qwen3.5-9b_think-false.json` (new
  artifact), redaction edits to `hardware_profiles/workstation-zeria-01.json` and
  `phase0_results/phase0_smoke_workstation-zeria-01.json`.
- **Docs:** WORKLOG, decision record, operational report §10.1, PR summary,
  keep-alive correction sidecar.

## Lenses run
Non-BIM Python repo, no `.claude/review-profile.yaml` → fallback heuristics.
- `code-review` — always on.
- `security-diff` — always on (`security-engineer` agent).
- `bim-code-review` / `revit-lifecycle` — **inert** (no BIM signals: no `revit-relay/`,
  no `.rvt`/`.rfa`, no `Autodesk`/`RevitAPI`, non-BIM remote).
- `concurrency` — **not triggered** (`run_diagnostic_think_false.py` is single-threaded
  synchronous; no async/queue/worker/thread paths in the delta).

Blind parallel fan-out; convergence below.

## Converged decision list (1 retained)

### LOW — Transport/timeout failure is written as a stub artifact *and* exits 0, poisoning the same-day retry slot
- **Location:** `run_diagnostic_think_false.py:127-128` (error caught, `response` stays
  `None`) → `:203` (unconditional write) → `:212` (lone `return 0`); interacts with
  `:64` (date-only filename) and `:65-67` (overwrite refusal).
- **Raised by:** code-review (high confidence). security-diff: no overlap.
- **Why retained:** Confirmed reachable in source. On `TimeoutError`/`URLError`/`OSError`
  the diagnostic falls through to the unconditional `out.write_text(...)` and the single
  `return 0`; there is no `if error:` guard and no non-zero exit after the request begins.
  The written stub is honest (`transport_error` set, `structurally_valid=False`), but:
  (1) the process exits **0**, so any `&&` chain / CI step / `$?` check reads a transient
  failure as success; (2) the output path is date-only and `:65-67` refuses to overwrite,
  so the same-day retry of a script explicitly built to be re-runnable ("commit that
  evidence, one way or the other") is blocked until the operator manually deletes the stub.
- **Failure path:** Run while the Ollama server is down/restarting, or when the single
  generate call exceeds `INVOCATION_TIMEOUT_MS` (900 s). `urlopen` raises → caught at
  `:127` → failure stub written, exit 0. Re-run same day → `out.exists()` at `:65` → exit 1.
- **Consequence:** A recoverable-by-hand operational footgun that defeats the script's own
  re-runnability guard and misreports success. Low severity: single-operator local script,
  honest stub content, easy manual recovery.
- **Action (not applied — read-only pass):** On transport/timeout error, either skip the
  write and `return 1`, or write to a distinct failure path; return non-zero whenever
  `transport_error` is set (optionally also when `structurally_valid` is False), so the
  daily slot is reserved for a genuine result and the exit code reflects whether a signal
  was obtained.

## NOT RETAINED
- **`redact_local_paths` is case-sensitive** (regex requires capital `Users`; `_home_spellings`
  uses `Path.home()` canonical case) — a lowercase `c:\users\…` spelling would slip through.
  *Reason:* pre-existing code (not in this delta) with **no reachable trigger here** — the only
  free-text fields (`raw_response` over synthetic fixtures; `transport_error` from network
  exceptions) cannot introduce a differently-cased home path, and `profile_id` is an
  operator-chosen identifier. Worth a one-line hardening (`re.IGNORECASE` + `os.path.normcase`)
  as defense-in-depth, but not a finding against this diff.
- **`FIXTURE_SPECS[0]` positional index** — a future reorder would mislabel the filename but
  the artifact records `fixture_id = spec.fixture_id`, so recorded evidence stays correct.
  Below the retention bar.
- **`prompt_eval_count`/`eval_count` nested under the `timing_ms` key** — cosmetic, not a defect.

## Cleared with no finding (checked)
- Payload shape matches `local_intel.ollama_client.invoke` (same `options`, `format`,
  `keep_alive`, `stream`, `seed`-if-not-None); `difference_from_batch_request` is accurate.
- ns→ms math (`_ns`, /1e6) correct and applied only to durations; counts fetched raw.
- Empty/None/non-dict/parse-failure response all handled without crashing; `structurally_valid`
  resolves correctly in every branch. `unload_model` symmetric (no residency leak).
- **Privacy/redaction (this repo's real threat model): clean.** `:203` redacts the *entire*
  serialized document, so no field bypasses redaction; the committed diagnostic JSON and both
  redacted data files contain no raw account/home path (repo-wide grep finds only tests
  asserting its absence). No SSRF/path-traversal from argv — URL is the hardcoded
  `DEFAULT_HOST` (`http://localhost:11434`), output filename is fixed under `RESULTS_DIR`.
  Transport timeout bounded; parsing is `json.loads` only. Hash provenance self-consistent
  (`legacy_…` ≠ `sanitized_…`, i.e. redaction actually changed content).

## Status
Report-only (no `--fix`). Nothing committed, staged, or pushed. No Phase 1a work; NORTHSTAR.md,
protocol §6/§9/§13, candidate list, harness, and the protected untracked drafts untouched.
This file is written **untracked** — the lane branch is merged, so it is not committed here;
landing it (and any fix for the LOW finding) into `master` is a separate human-approved step.

---

## Fix applied — `fix/diagnostic-failure-retry-safety` (2026-09-06)

The retained LOW finding above was fixed on branch `fix/diagnostic-failure-retry-safety`
(off `origin/master`), then re-reviewed with the same two lenses on the fix diff.

### Change
- `run_diagnostic_think_false.py`: on a transport / timeout / malformed-response
  failure the diagnostic now returns a **non-zero** exit, writes **no** success
  artifact at the date-only path, and instead persists a sanitized failure artifact
  at a **distinct** run-id path (`{ISO-second}-{microsecond}_qwen3.5-9b_think-false.FAILED.json`)
  recording `failure_kind`, `failure_reason`, the pre-failure runtime identity, and
  `started_utc`/`failed_utc`. A failure therefore no longer occupies the success slot,
  so a later same-day success proceeds with no manual cleanup; both attempts are kept.
  Success behavior (normal artifact, whole-document redaction, exit 0) is unchanged.
- `tests/test_diagnostic_think_false.py` (new, 13 tests): success→redacted artifact→exit 0;
  transport failure→exit 1, no success artifact; timeout classification; malformed
  envelope; distinct+redacted+self-describing failure artifact; failure-then-same-day-
  success needs no deletion; genuine-success overwrite still refused; bad argv; model-
  not-installed; plus the second-pass cases below.

### Second-pass review (blind, on the fix diff)
- **security-diff:** empty. Whole-document redaction confirmed on the new failure
  artifact (argv-sourced `hardware_profile_id`, `failure_reason`, `request_shape` all
  inside the redacted string); filename/URL take no untrusted input; the reachable
  exception set on this HTTP-only path carries no filesystem paths. The `redact_local_paths`
  case-sensitivity caveat was again dropped (pre-existing, no reachable trigger here).
- **code-review:** 3 findings, **all fixed and test-covered**:
  1. *MEDIUM* — `resp.read()`/`.decode("utf-8")` could raise `http.client.IncompleteRead`
     or `UnicodeDecodeError`, neither an `OSError`, so a dropped/garbled body escaped the
     except net → an unredacted traceback and no failure artifact. Fixed: the
     malformed-response clause now also catches `UnicodeDecodeError` and
     `http.client.HTTPException`. Tests: `test_incomplete_read_is_malformed_failure`,
     `test_non_utf8_body_is_malformed_failure`.
  2. *LOW* — URLError timeout classification was narrower than the production sibling
     `local_intel.ollama_client.invoke`. Fixed: mirror invoke's
     `isinstance(reason, TimeoutError) or "timed out" in str(exc).lower()`. Test:
     `test_urlerror_timed_out_string_is_classified_timeout`.
  3. *LOW* — a truthy non-dict JSON envelope (list/scalar) would hit `(response or {}).get`
     and crash. Fixed: a post-decode `not isinstance(response, dict)` guard routes it
     through the failure branch as `malformed_response`. Test:
     `test_non_dict_envelope_is_malformed_failure`.

### Validation
`python -m pytest -q` → **95 passed** (82 pre-existing + 13 new). No benchmark rerun;
no network; no Phase 0 evidence, protocol, candidate, NORTHSTAR, or Evidence Compiler
change; protected drafts untouched.
