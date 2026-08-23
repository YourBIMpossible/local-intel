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

**2026-08-22 — Phase 0 step 5: smoke test executed, both models miss both
latency gates.** Full report: `phase0_results/PHASE0_REPORT.md`; raw data:
`phase0_results/phase0_smoke_workstation-zeria-01.json`. 20/20 invocations
completed (5 fixtures × 2 models × cold/warm) against the frozen 24,000-token
worker view.

`qwen2.5-coder:14b`: warm median 335,223 ms, cold median dominated by three
~902,057 ms timeout ceilings. `qwen3-coder:30b-a3b-q4_K_M`: warm median
169,784 ms, cold median 902,046 ms (3 of 5 cold runs hit the timeout
ceiling). Both blow past
`warm_e2e_max_ms: 20000` and `cold_e2e_max_ms: 60000` by 7–45x. Both pass
`structural_validity_min: 3/5` cleanly (5/5 warm each) and citation
integrity is clean on every run that produced an artifact (7/7 each).
Confirmed via live `nvidia-smi` during one timeout run (99% util, 88 W) that
the GPU was genuinely computing, not hung — these are real durations under
the VRAM-spill condition recorded at step 4, not a client defect.

Two flags on the data: (1) each model's first recorded warm run (f01) is an
artifact of the script's own unrecorded warm-priming call reusing an
identical prompt — 5.6 s / 10.6 s vs. 143–380 s for the model's other warm
runs. Does not change any gate verdict. (2) fixtures are synthetic
(`fixture_provenance: SYNTHETIC`), not real BIMpossible test logs, so this
is Phase 0 measured "as configured," not yet "at real worker-view sizes" in
the strictest reading of §6's decision table — see "Needs your call" below.

**2026-08-22 — Phase 0 decision: `DEFER_LOCAL_MODEL_PATH`.** Human call,
recorded per §17. Scope: the frozen 24K-worker-view / 32K-context
synchronous configuration measured in step 5, on the synthetic fixture set —
no second real-fixture Phase 0 pass, no model/context tuning of this
candidate. Both models missed both latency gates by 7–45x; the margin is
large enough that the synthetic-vs-real fixture question does not change
the outcome. Local model triage inference is closed for this candidate
configuration.

Evidence set preserved as-is, nothing further to add to it: raw results
(`phase0_results/phase0_smoke_workstation-zeria-01.json`), report with its
exclusions (`phase0_results/PHASE0_REPORT.md`), hardware profile
(`hardware_profiles/workstation-zeria-01.json`), fixture provenance
(`fixtures/manifest.json`), and commits `9e9948b`…`897b5ed`.

A distinct future candidate — deterministic compressor-only evaluation
(Arm A: worker-view compression, Arm B: raw log) with no local model
inference in scope — is out of scope for this mission and not opened here;
it needs its own north-star record if pursued.

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

*(nothing outstanding — Phase 0 decision recorded above)*
