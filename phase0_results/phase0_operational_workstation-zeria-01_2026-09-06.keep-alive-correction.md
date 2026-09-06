# Evidence-provenance correction: request keep-alive in the 2026-09-06 operational batch

- **Date:** 2026-09-06
- **Kind:** additive sidecar. The results JSON it annotates is not modified, rewritten, regenerated, or rerun.
- **Applies to:** `phase0_results/phase0_operational_workstation-zeria-01_2026-09-06.json`
  - SHA-256 of the committed content (git blob `70584a05b162874510f9d0fc608de1deb1360284`, LF line endings): `531838391d93c336b154440a67653db9de5ac83020f0b235bdea7eae087154aa`
  - Note: a Windows checkout under `core.autocrlf=true` materialises the file with CRLF endings and hashes to `019f0aeeb34ecd66df8bf3ae09b5c5d7d7fa5709a3e23c939ba5af029102c711`. The committed bytes are the LF form above.
  - Last commit touching the file before this sidecar: `7681d4c` (home-path redaction only; measurements unchanged since `9c13ba3`).

## Statement

1. **Server keep-alive.** The Ollama server banner recorded `OLLAMA_KEEP_ALIVE:30m0s`. The JSON stores this as `server_environment.keep_alive = "30m0s"` (read from `server.log` banner line 1, `server_environment.log_banner_line_no = 1`) and echoes it as `runtime_identity.server.keep_alive` on every run.
2. **Request keep-alive.** Every benchmark request in this batch explicitly sent `keep_alive="10m"` in the request body. The JSON does not record this value: its `runtime_identity_version` is `2026-09-06.1`, which had no request-level field, and the string `10m` does not occur in the file.
3. **Precedence.** A request-level `keep_alive` overrides the server default for the model load it triggers.
4. **What was measured.** The batch therefore measured a **10-minute request-residency condition**, not a 30-minute client-residency condition. The `run_label` text "keep_alive 30m" refers to the server environment, not to the request value in force.
5. **What does not change.** No latency, quality, structural-validity, citation-integrity, telemetry, sampler, or §6 pass/fail result changes. Every number in the JSON, the telemetry CSVs, and the server-log segments stands as measured.
6. **Preservation.** The original JSON remains byte-for-byte preserved at the SHA-256 above.

## Evidence

- **Harness source (value sent):** `run_phase0_smoke.py:78` defines `REQUEST_KEEP_ALIVE = "10m"`. `run_phase0_smoke.run_one` (`run_phase0_smoke.py:81-98`) passes it as `keep_alive=` to `local_intel.triage.triage_log` (`local_intel/triage.py:109`, `:121`), which passes it to `local_intel.ollama_client.invoke`, where it is placed in the request body as `"keep_alive": keep_alive` (`local_intel/ollama_client.py:196`). The operational driver calls `run_one` for the preload and every measured run (`run_phase0_operational.py:423`, `:442`).
- **Observed residency expiry (`ps_after.expires_at`):** each of the six conditions in `conditions[]` shows the model's `expires_at` 9.90 minutes after that condition's `ended_utc`, consistent with a 10-minute request keep-alive counted from the last request and inconsistent with 30 minutes.

| model | state | `ended_utc` | `ps_after[0].expires_at` | delta |
|---|---|---|---|---|
| qwen2.5-coder:14b | cold | 2026-09-06T18:09:31Z | 2026-09-06T11:19:25.776-07:00 | 9.90 min |
| qwen2.5-coder:14b | warm | 2026-09-06T18:12:03Z | 2026-09-06T11:21:56.900-07:00 | 9.90 min |
| qwen3-coder:30b-a3b-q4_K_M | cold | 2026-09-06T18:15:30Z | 2026-09-06T11:25:24.637-07:00 | 9.90 min |
| qwen3-coder:30b-a3b-q4_K_M | warm | 2026-09-06T18:18:00Z | 2026-09-06T11:27:53.871-07:00 | 9.90 min |
| qwen3.5:9b | cold | 2026-09-06T18:20:47Z | 2026-09-06T11:30:41.578-07:00 | 9.90 min |
| qwen3.5:9b | warm | 2026-09-06T18:22:42Z | 2026-09-06T11:32:36.309-07:00 | 9.90 min |

## Going forward

Output produced after commit `7681d4c` records the request value directly: `RuntimeIdentity` version `2026-09-06.2` carries `request_keep_alive` (`local_intel/runtime_identity.py:246`) alongside `server.keep_alive`, and the operational document stores it at top level as `request_keep_alive`. This sidecar is the record for the one batch that predates that field.

Related: `phase0_results/PHASE0_OPERATIONAL_REPORT_2026-09-06.md` §10 and §10.1; `decisions/2026-09-06-defer-revision-warm-session-only.md`, corrective note and final ruling amendment. No Phase 1a admission is made by this file.
