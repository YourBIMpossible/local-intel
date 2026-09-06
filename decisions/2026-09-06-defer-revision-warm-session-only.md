# Decision record: `DEFER_LOCAL_MODEL_PATH` revised to warm-session-only

- **Date:** 2026-09-06
- **Authority:** human ruling (protocol §17), accepting recommendation B of
  `phase0_results/PHASE0_OPERATIONAL_REPORT_2026-09-06.md`.
- **Supersedes in part:** the 2026-08-22 `DEFER_LOCAL_MODEL_PATH` record in
  `WORKLOG.md` (commit `f151327`). That record and its evidence set are
  preserved unchanged; this record narrows it.

## Ruling

1. **Local models are approved for normal active use** under the operating
   conditions measured on 2026-09-06: Ollama with `OLLAMA_FLASH_ATTENTION=1`
   and `OLLAMA_KEEP_ALIVE=30m` in effect (verified from the server banner),
   candidates `qwen2.5-coder:14b` and `qwen3-coder:30b-a3b-q4_K_M`, the
   frozen §9 parameters (`num_ctx` 32768, output cap 1800).
2. **The DEFER now applies only to cold start.** True or process-cold first
   use can still take up to about one minute (worst observed single cold
   request 58.0 s; first-load-of-model 16–22 s even with a warm page cache;
   no disk-cold measurement exists). Cold-start responsiveness is therefore
   **not guaranteed** and is not part of the approval.
3. **No further cold-start, driver, iGPU, BIOS, registry, or hardware
   investigation** is opened by this ruling.

## Benchmark-output-handling limitation (recorded, not a model failure)

`qwen3.5:9b` scored 0/5 structural validity in the operational batch because
it is a thinking model: its generated tokens were written to the top-level
`thinking` field while the harness validated only the visible `response`
field, which was empty. The model is **not classified as failed**; its
latency data stands (warm median 8.4 s, cold 16.4 s). If it is tested again,
the request must set the top-level `think: false` option, or the validator
must check both fields explicitly. A one-request post-batch diagnostic
confirmed `think: false` yields valid schema-conforming JSON.

## Evidence (unchanged)

- Original Phase 0 (FA off): `phase0_results/phase0_smoke_workstation-zeria-01.json`, `phase0_results/PHASE0_REPORT.md`, commits `9e9948b`…`897b5ed`, decision `f151327`.
- FA-on re-measure: `phase0_results/PHASE0_REPORT_FA-ON_2026-09-06.md`, commit `cbbbd6f`.
- Runtime identity amendment: `local_intel/runtime_identity.py`, `runtime-identity-amendment-2026-09-06.md`, commit `b4c9f59`.
- Operational batch: `phase0_results/PHASE0_OPERATIONAL_REPORT_2026-09-06.md`, results JSON, telemetry, server-log segments, commit `9c13ba3`.

## Not decided here

Admission to Phase 1a, candidate selection, and any §6/§9/§13 edit remain
separate, versioned human decisions.

## Corrective note (2026-09-06, post-review; added by the corrective commit, ruling text above left as written)

Two statements in the ruling and limitation paragraphs above are not supported by the committed evidence as written. The ruling text is human-owned and is left unedited; the corrections are recorded here for the human decision-maker to adopt or reword.

1. Ruling 1 says `OLLAMA_KEEP_ALIVE=30m` was "in effect (verified from the server banner)". The server environment did carry 30m0s, but every measured request sent `keep_alive=10m` in its body, which overrides the server value; the effective residency window during the batch was 10 minutes (every condition's `ps_after.expires_at` = end + ~10 min). A 30-minute client operating condition was not measured. "30 m keep-alive" should be read as configured server policy, not as a measured condition.
2. The thinking-field explanation for `qwen3.5:9b` (tokens written to a top-level `thinking` field; `think: false` diagnostic "confirmed") has no committed evidence: the harness recorded only the JSON-decode error, and the diagnostic was not saved. The explanation is unverified. The classification "not a model failure" is retained as a non-classification; it is not evidence of a pass.

Neither correction changes the measured latencies, the §6 pass/fail table for the two candidates, or the scope of this ruling. No Phase 1a admission is made by this note or by the corrective commit.

## Final ruling amendment (2026-09-06, human decision, §17)

The following replaces the affected statements in the Ruling and Limitation sections above. It is the human decision-maker's text, recorded verbatim by the final corrections commit.

1. The operational batch measured server `OLLAMA_KEEP_ALIVE=30m` but `request_keep_alive=10m`.
2. Going forward, the approved active-session operating policy is explicit client `request_keep_alive=30m` and server `OLLAMA_KEEP_ALIVE=30m`.
3. The September 6 batch does not itself prove a 30-minute client window; it proves the 10-minute measured window.
4. `qwen3-coder:30b-a3b` is eligible for a future Phase 1a admission decision.
5. `qwen2.5-coder:14b` is borderline: two of four genuine warm runs exceeded 20 seconds, so it is not admitted pending a cache-controlled rerun.
6. `qwen3.5:9b` remains unresolved pending the committed diagnostic.

Facts of record accompanying this amendment (not decisions):

- The committed diagnostic for item 6 is `phase0_results/diagnostics/2026-09-06_qwen3.5-9b_think-false.json`: one request, fixture f01, cold-of-model: `think:false` returned a 1,684-char `response` that passed all §8 checks (structurally valid), no `thinking` field in the response body, `done_reason` stop, total 19,820 ms of which load 9,094 ms, prefill 5,417 ms (27,336 tokens), generation 5,227 ms (434 tokens). It shows what `think:false` produces; the batch's failing raw responses were not captured, so it does not by itself show what the batch produced. Resolution of item 6 on that evidence is a separate human act.
- The harness constant `REQUEST_KEEP_ALIVE` in `run_phase0_smoke.py` still reads `10m` as of this commit. Item 2 is policy; the harness change that implements it must be a dated edit made before the next measured batch (§9/§14 discipline), not part of this evidence PR.
- "Eligible for a future Phase 1a admission decision" (item 4) is not an admission. **No Phase 1a admission has been made.** Candidate list unchanged. NORTHSTAR.md, §6, §9, §13 unchanged.
- Publication redaction of the two remaining master-era files (`hardware_profiles/workstation-zeria-01.json`, `phase0_results/phase0_smoke_workstation-zeria-01.json`): only the local home path in `model_store_path` changed; measurements unchanged. Legacy unredacted profile hash `b725633194a7841906100e3c7529dec0f5873531b10785659a4e28b8fc8c9ebf`; sanitized profile hash `b0ee67f45e8165d56bb0741e34b60dfd4c3aac6b05b427c8e870c01a5e7f78b0`. Every `hardware_profile_hash` recorded in `phase0_results/*.json` equals the legacy value and is left as recorded.
