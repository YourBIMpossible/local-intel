# Session / Batch Configuration Log

Append-only. Each entry captures the Claude Code execution context in effect
for a batch of work under the Phase 1 protocol, per §9 "Claude session
configuration" and the Phase 0 hardware-profile requirement (§6).

Record a new entry whenever the client version, model, or repo commit
context changes — a change here is a batch boundary.

---

## Entry 1 — 2026-08-22

- Claude model ID: `claude-sonnet-5`
- Claude Code client version: `2.1.178`
- Repository commit at session start: `9e9948b` (ratification commit)
- Purpose: protocol ratification, git repo bootstrap. No Phase 0 measurement
  taken in this batch.
- Hardware profile: not yet captured — required before any Phase 0 smoke-test
  run (§6), not required for ratification alone.

---

## Entry 2 — 2026-08-22 (batch boundary: Claude model change)

Per §9, "A Claude model/client/tool change creates a new batch boundary."
The operator switched models mid-session; this is that boundary.

- Claude model ID: `claude-opus-5` (was `claude-sonnet-5` in Entry 1)
- Claude Code client version: `2.1.178` (unchanged)
- Repository commit at entry: `4f4e4a0`
- Purpose: Phase 0 step 3 — minimal Ollama invocation and structured-output
  validation.
- Local environment observed: Ollama `0.32.14`; both candidate models
  installed — `qwen2.5-coder:14b`
  (digest `9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849`)
  and `qwen3-coder:30b-a3b-q4_K_M` (digest `06c1097efce0431c2045...`).
- No Phase 0 measurement taken in this batch. The one live model call made
  here was a plumbing check on a synthetic log, explicitly not one of the
  five representative real packets §6 requires.
