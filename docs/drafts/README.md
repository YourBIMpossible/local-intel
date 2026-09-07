# docs/drafts — non-authoritative drafts

**Everything in this folder is a draft only — not approved policy, decision,
admission, or authorization.** These files are preserved here for human review
and historical traceability. None of them changes `NORTHSTAR.md`, the protocol
(`phase1-local-intelligence-protocol-v3.md`, incl. §§6/9/13), any record under
`decisions/`, the model candidate status, or the Phase 1 state.

**Phase 1a and Phase 1b are unstarted.** Admitting a configuration to a new
phase is a separate, versioned human decision (§17). The authoritative
readiness/gap/governance record is
[`reviews/2026-09-06-phase1a-preparation-readiness.md`](../../reviews/2026-09-06-phase1a-preparation-readiness.md).

## Contents

| File | What it is |
|---|---|
| [`phase0-reconsideration.md`](phase0-reconsideration.md) | Analysis reframing the Phase 0 result (residency-bound, not model-quality-bound) and mapping the option space (smaller model / KV-cache quantization / hardware). Not a decision. |
| [`phase1-protocol-amendment.draft.md`](phase1-protocol-amendment.draft.md) | Paper proposal for the protocol edits that reopening the local-model path (adding `qwen3.5:9b` and/or a KV-cache-quantization lever) would require. Not ratified. |
| [`PHASE1A-ADMISSION-KICKOFF.draft.md`](PHASE1A-ADMISSION-KICKOFF.draft.md) | A draft admission-decision + kickoff plan that *requests* a §17 human ruling to admit `qwen2.5-coder:14b` + `qwen3-coder:30b-a3b-q4_K_M` to Phase 1a offline evaluation. It is a request, not a signed decision. |

To act on any of these, a human makes the corresponding dated, versioned
decision (a new record under `decisions/`, or a versioned protocol edit) — the
draft itself authorizes nothing.
