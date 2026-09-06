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
