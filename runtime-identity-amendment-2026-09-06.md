# Runtime identity amendment — 2026-09-06 (additive)

**Scope.** Additive only. Does not modify §6 kill thresholds, §9
`GenerationParameters` / `InvocationConfiguration`, §13 pairing discipline,
or any `invocation_configuration_id`. It adds an out-of-band record,
captured per invocation, of the serving-layer facts §9 does not encode.

**Why.** The Phase 0 FA-off run (DEFER basis) and the 2026-09-06 FA-on
re-measure share an identical `invocation_configuration_id` yet differ by
10–20× in latency. The id is therefore insufficient to identify what was
measured. This amendment closes that gap without reopening the frozen id.

**Implementation.** `local_intel/runtime_identity.py`
(`RUNTIME_IDENTITY_VERSION = "2026-09-06.1"`). Every field is read, not
inferred; unreadable fields are `null`.

| Required fact | Source |
|---|---|
| Ollama version | `/api/version` |
| NVIDIA driver version | `nvidia-smi` |
| GPU model, total / used / free VRAM at run start | `nvidia-smi` |
| model tag, digest, quantization, size, family, parameter size | `/api/tags`, `/api/show` |
| context length requested (`num_ctx`) / native context | `GenerationParameters.num_ctx`; `/api/show` |
| GPU layers offloaded / total, overflowing layers | server.log load segment: `offloaded N/M layers to GPU`, `(k overflowing)` |
| `OLLAMA_FLASH_ATTENTION` effective | server.log startup banner + `flash_attn = …` in load segment |
| `OLLAMA_KEEP_ALIVE` (server default) | server.log startup banner |
| request-level `keep_alive` (overrides the server default for the load it triggers; the effective residency window) | driver constant `REQUEST_KEEP_ALIVE`, recorded as `RuntimeIdentity.request_keep_alive` (added 2026-09-06.2) |
| KV-cache type | server.log: `K (type)`, `V (type)`; banner `OLLAMA_KV_CACHE_TYPE` |
| vision projector | `/api/show` capabilities (`vision`) + load-segment projector markers |
| benchmark condition | driver-declared `true-cold` / `warm-resident`, with `disk_cache_condition` stated in words |
| prompt tokens, output cap, actual output tokens | `prompt_eval_count`, `max_output_tokens`, `eval_count` |

**Effective values on `workstation-zeria-01` as of this amendment** (from
the running server's banner, not the shell): `OLLAMA_FLASH_ATTENTION:true`,
`OLLAMA_KEEP_ALIVE:30m0s`, `OLLAMA_KV_CACHE_TYPE:` (server default, f16).
The 2026-09-06 batches sent `keep_alive=10m` per request, so 10 m — not
30 m — was the residency window actually in force during measurement.
Both flags are also persisted as Windows User environment variables
(`setx`). Note for reproducers: a process launched from a shell opened
before `setx` inherits the stale environment — the first restart today did
exactly that and came up FA-off; verify the banner, never the shell.

**Governance.** Recorded under the north star's three-door rule as a small
change serving the active mission. Folding these fields into the §9 id
itself remains a human, dated protocol edit.
