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
