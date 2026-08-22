# Worklog

Running record for the Phase 1 Local Intelligence Experiment. Mission and
constraints live in `NORTHSTAR.md`; the governing protocol is
`phase1-local-intelligence-protocol-v3.md`.

---

## Done

**2026-08-22 — Protocol ratified.** Repo initialized; protocol committed with
the §6 kill thresholds frozen verbatim in the commit message, dated before
any Phase 0 execution (`9e9948b`). North star locked (`0ada7b2`).

**2026-08-22 — Phase 0 step 2: deterministic worker-view serialization**
(`4f4e4a0`). `EvidencePacket` + worker-view builder implementing §7 steps 1–5.

**2026-08-22 — Phase 0 step 3: Ollama invocation + structured-output
validation.** Artifact schema (§8), hard validator (all 8 §8 checks),
bounded Ollama client with §14 telemetry, complete configuration identity
(§9), frozen worker prompt, and the `triage_log` end-to-end path. 30 tests
passing. Verified end to end against `qwen2.5-coder:14b` on a synthetic log:
schema-valid, in-range citations, `presentable=True`.

**2026-08-22 — Phase 0 step 4: hardware profile captured.**
`workstation-zeria-01`, profile hash `b725633194a78419...`. All §6 fields
populated; written immutably to
`hardware_profiles/workstation-zeria-01.json`.

Material finding recorded with it: **neither candidate model fits entirely
in VRAM at the required context size.** At `num_ctx=32768` on a 16 GB
RTX 5080, `qwen2.5-coder:14b` sits 93.0% on GPU and
`qwen3-coder:30b-a3b-q4_K_M` sits 66.2% on GPU; both spill the remainder to
CPU. Cold load was 3.5 s and 11.0 s respectively.

This is not a tuning problem to be worked around. §6 pre-commits
`representative_view_size_tokens: 24000`, and 24 000 input plus reserved
output tokens forces a context of this order — so the protocol's own frozen
view size is what puts both models over this GPU's VRAM. Phase 0 will
therefore measure both models *as configured*, spill included. Lowering
`num_ctx` to make them fit would be tuning a candidate to pass its own kill
gate, which is exactly what §6's pre-commitment discipline exists to
prevent, and under §9 it would create a different candidate configuration
rather than a faster version of this one.

If both models miss the thresholds, that is a legitimate pre-committed
outcome ("defer local model path"), not a defect to engineer around.

---

## Roadmap

**Coherence between `status` and hypothesis text is unmeasured.** In the
step-3 plumbing check the model asserted a definite root cause in
`statement` while tagging it `status: "unlikely"`. Hard validation cannot
catch this — it is a semantic property, and §8 says plainly that schema
validity is not claim correctness. Phase 1a's citation-support rubric (§11)
grades spans against claims, not claims against their own stated
confidence. Worth deciding in Phase 1a whether statement/status coherence
becomes its own metric. Not acted on now: adding a metric to the Phase 1a
gate set is a protocol edit, not an implementation detail.

**Token estimation is a chars/4 placeholder.** Fine for Phase 0 sizing;
insufficient for the §12/§13 token-based economics gates, which compare
real Claude input tokens. Needs a real tokenizer before Phase 1b.

---

## Needs your call

*(nothing outstanding)*
