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

**2026-08-22 — Phase 0 decision: `DEFER_LOCAL_MODEL_PATH`.** *(Revised
2026-09-06 to warm-session-only — see
`decisions/2026-09-06-defer-revision-warm-session-only.md`; text below
preserved as originally recorded.)* Human call,
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

**2026-09-06 — Flash attention made permanent; FA-on Phase 0 re-measure
executed.** At user request. (1) `OLLAMA_FLASH_ATTENTION=1` set in the
Windows User environment (persistent) and Ollama restarted;
`server.log` confirms `OLLAMA_FLASH_ATTENTION:true`; large-prompt prefill on
the main instance verified at 6,335 tok/s (was ~1.9 tok/s FA-off). (2) Both
original candidates re-measured through the frozen harness with only the FA
flag changed — new driver [`run_phase0_smoke_fa.py`](run_phase0_smoke_fa.py),
results [`phase0_results/phase0_smoke_workstation-zeria-01_fa-on_2026-09-06.json`](phase0_results/phase0_smoke_workstation-zeria-01_fa-on_2026-09-06.json),
report [`phase0_results/PHASE0_REPORT_FA-ON_2026-09-06.md`](phase0_results/PHASE0_REPORT_FA-ON_2026-09-06.md).
The canonical FA-off DEFER evidence was preserved byte-for-byte.

Outcome (medians): **both models now PASS the warm latency gate**
(14B 17,449 ms, 30B 15,579 ms; gate 20,000 ms) — previously missed by
8–17×. Warm end-to-end fell 19× / 11×, driven by a 14–28× prefill speedup.
Structural validity 5/5 and citation integrity 10/10 for both (quality was
never the issue). **Both still FAIL the cold gate**, but the cause changed
entirely: FA-on cold *inference* is healthy (~23–25 s); the cold failure is
now **model load time** (56 s / 75 s), which alone exceeds the 60 s gate.
`meets_all_thresholds` remains `false` for both. This run **measures**; it
does not reverse DEFER or admit any model — those remain human §17 acts.

---

**2026-09-06 — Phase 0 operational follow-up (FA on, server keep-alive 30 m,
requests sent keep_alive=10m — see correction below):
both candidates pass every §6 gate on 5-run medians; cold gate passes.** One unattended
batch, 30 requests (3 models × cold/warm × 5 fixtures), 17 min, no stop
condition, 0 flagged Windows events, no runner-crash markers. 14B: cold
median 23.8 s / warm 18.0 s, 5/5 valid; 30B-A3B: cold 25.1 s / warm 16.4 s,
5/5 valid. `qwen3.5:9b` control: fastest (warm 8.4 s) but 0/5 valid because
the harness recorded `unparseable` responses (thinking-field explanation
unverified; no committed diagnostic). Cold is process-cold, not
disk-cold. Report: `phase0_results/PHASE0_OPERATIONAL_REPORT_2026-09-06.md`;
results JSON, telemetry CSVs, and server-log segments alongside. Persistent
`OLLAMA_KEEP_ALIVE=30m` set and verified from the server banner; runtime
identity amendment committed (`b4c9f59`). DEFER, §6/§9/§13 untouched.

**2026-09-06 — Corrective commit after `/review-all` (evidence-and-decision
PR prep).** Corrections: the batch ran with per-request `keep_alive=10m`
(overrides the 30 m server env; effective window 10 min, `ps_after.expires_at`
confirms); the 14B warm margin was overstated — genuine warm runs (excluding
the f01 prompt-cache hit) 20,336 / 21,175 / 17,977 / 16,364 ms, median
19,157 ms, 2 of 4 over the gate; the `qwen3.5:9b` thinking-field explanation
is unverified (no committed diagnostic). Runner hardened: partial results and
in-flight sampler CSV preserved on exception/Ctrl-C with abort reason,
None-safe formatting on timeout, per-batch run id with overwrite guards,
`request_keep_alive` in `RuntimeIdentity` (2026-09-06.2), `<HOME>` redaction
of committed server-log segments/JSON/report. 20 new focused tests
(`tests/test_operational_runner.py`, `tests/test_redact_paths.py`); 82 pass.
No benchmark rerun. NORTHSTAR, §6/§9/§13, candidates, and the admission
decision untouched. **No Phase 1a admission has been made.**

**2026-09-06 — Final evidence-branch corrections (human decision recorded;
stop for PR review).** Decision record amended verbatim: batch measured
server keep-alive 30 m / request keep_alive 10 m; approved policy going
forward is explicit client 30 m + server 30 m; the 2026-09-06 batch proves
the 10 m window only; `qwen3-coder:30b-a3b` eligible for a future Phase 1a
admission decision; `qwen2.5-coder:14b` not admitted pending a
cache-controlled rerun (2 of 4 genuine warm runs > 20 s); `qwen3.5:9b`
unresolved pending the committed diagnostic. Diagnostic committed:
`phase0_results/diagnostics/2026-09-06_qwen3.5-9b_think-false.json` — `think:false` → structurally valid
artifact, no `thinking` field, 19.8 s cold-of-model. Master-era files
redacted (`hardware_profiles/workstation-zeria-01.json`,
`phase0_results/phase0_smoke_workstation-zeria-01.json`): home path only;
legacy hash `b725633194a7…` → sanitized `b0ee67f45e81…`, both recorded
with a dated note. Harness `REQUEST_KEEP_ALIVE` still `10m` (policy change
needs a dated pre-batch edit). 82 tests pass. Not pushed. **No Phase 1a
admission has been made.**

**2026-09-06 — DEFER revised to warm-session-only (human ruling, §17).**
Recommendation B accepted. Local models approved for normal active use with
flash attention on and 30-minute server keep-alive (measured with 10 m
request keep_alive — see corrective note in the decision record); cold/process-cold first use
can still take up to ~1 minute, so cold-start responsiveness is not
guaranteed and stays deferred. `qwen3.5:9b` 0/5 recorded as a
benchmark-output-handling limitation (thinking-field explanation unverified),
not a model failure; retest requires top-level
`think: false` or dual-field validation. No further tests or hardware/driver
investigation opened. Record:
`decisions/2026-09-06-defer-revision-warm-session-only.md`.

**2026-09-06 — Evidence-and-decision PR merged; local master synced.** PR #1
(`Phase 0 evidence: FA-on re-measure, operational batch, DEFER revision to
warm-session-only, post-review corrections and final ruling amendment`) was
merged into `master` by the human owner after review, via merge commit
`c182aa3` (merge-commit method, so the full evidence trail is preserved and
every branch SHA `cbbbd6f`…`3583cba` stays reachable). Local `master` was
fast-forwarded `e68d040` → `c182aa3` and is in sync with `origin/master`
(0 ahead / 0 behind). The lane branch `claude/project-pause-status-f34b4e`
is preserved on the remote at `3583cba` (not deleted). No Phase 1a work was
begun; `NORTHSTAR.md`, protocol §6/§9/§13, and the candidate list are
untouched; the two protected untracked Phase 1a drafts were never staged.

**2026-09-06 — Draft disposition: four untracked drafts resolved.** All four
untracked draft files (two per worktree) were dispositioned so neither worktree
carries an ambiguous untracked draft. Three carried unique but **unapproved**
planning/analysis material and were filed, verbatim, under the new
non-authoritative `docs/drafts/` folder (each with an explicit "Draft only — not
approved policy, decision, admission, or authorization" header and a folder
`README`): `docs/drafts/phase0-reconsideration.md`,
`docs/drafts/phase1-protocol-amendment.draft.md`, and
`docs/drafts/PHASE1A-ADMISSION-KICKOFF.draft.md` (the last *requests* a §17
admission ruling; it is not a decision). The fourth,
`PHASE1A-EVIDENCE-CORRECTIONS.draft.md`, was **fully superseded** by merged
records — its item 2/4 were already done, item 3 redaction is applied on `master`
(both profile JSONs now `<HOME>` with a `publication_redaction_note`), item 5's
`think:false` diagnostic is committed at
`phase0_results/diagnostics/2026-09-06_qwen3.5-9b_think-false.json`, and item 1's
keep-alive nuance is captured in the decision record and the readiness assessment
§1.4 — so it was archived outside the repo and its untracked copy deleted (it also
carried a local username path, so it was never committed). A repo-wide
sensitive-data scan before push is clean: no user-path leak in tracked files;
only the self-chosen `workstation-zeria-01` machine handle remains (accepted).
No model admitted; Phase 1a/1b remain unstarted; `NORTHSTAR.md`, the protocol,
`decisions/`, and candidate status are untouched. Earlier references above to
`phase0-reconsideration.md` / `phase1-protocol-amendment.draft.md` now resolve
under `docs/drafts/`.

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

**2026-09-01 — Reopen local-model path with new/smaller candidates?** Two
documents drafted at your request, read-only pass, nothing executed:
`phase1-protocol-amendment.draft.md` (proposed protocol changes to add
`qwen3.5:9b` — 6.6 GB weights, ~13GB smaller than the 14B candidate — and/or
KV-cache quantization as a new lever) and `phase0-reconsideration.md` (fresh
read on the Phase 0 result: the failure was VRAM residency at 32K context,
not model output quality — structural validity and citation integrity both
passed cleanly for both original candidates). `DEFER_LOCAL_MODEL_PATH`
stands unchanged; nothing here reverses it. Needs a ruling on whether to
run the suggested non-binding residency probe, and if so which candidate(s)
to formalize into a dated protocol amendment.

**2026-09-05 — Flash attention was OFF during Phase 0; it accounts for most
of the measured latency.** Non-binding hardware diagnostic (no evidence
packets, no protocol action), run at user request while chasing a reported
system freeze. Findings on `workstation-zeria-01` with `qwen3.5:9b`
(6.6 GB, Q4_K_M) at `num_ctx=32768`, **fully GPU-resident** (34/34 layers,
6.58 GB VRAM, no spill):

- Ollama's server default is `OLLAMA_FLASH_ATTENTION:false`. With it off,
  **prompt-eval (prefill) ran at 1.9 tok/s**; token *generation* was fine at
  109 tok/s. The GPU sat at 2–31% util / 36–49 W during prefill — stalling on
  a slow path, not computing.
- With `OLLAMA_FLASH_ATTENTION=1` (isolated test server on :11435, main
  instance untouched), **prefill jumped to ~288 tok/s (≈150×)**, total
  round-trip 51.8 s → 4.4 s, and the GPU ramped to 87% util / 226 W / full
  clocks. Generation unchanged (~120 tok/s).

Why this matters for the DEFER basis: at 1.9 tok/s prefill, a 24,000-token
worker view would take ~3.5 h just to ingest — which is the order of the
335,000 ms / 902,000 ms latencies Phase 0 recorded. Phase 0 ran with flash
attention off (server default), so the recorded latencies are very likely
**dominated by a disabled serving-layer flag, not purely by VRAM spill** as
the step-4 hardware note concluded. This is a *hypothesis for the original
two candidates* — only `qwen3.5:9b` was re-measured here, not
`qwen2.5-coder:14b` / `qwen3-coder:30b`. It does not reverse DEFER.

Needs your call: (a) whether flash attention (and possibly
`OLLAMA_KV_CACHE_TYPE`) should be added to §9/§14 as part of configuration
identity before any reopened Phase 0 pass — a re-measure with FA off would
be measuring the wrong thing; (b) whether to re-measure the original two
candidates with FA on before treating DEFER as resting on a fully explored
space. Ties directly into `phase1-protocol-amendment.draft.md` (which flagged
KV-cache quantization as an untested lever but did **not** catch that flash
attention itself was off).

**2026-09-06 — FA-on re-measure is in; four decisions now sit with you.**
The re-measure requested above (item b) is done — see Done (2026-09-06) and
`phase0_results/PHASE0_REPORT_FA-ON_2026-09-06.md`. It materially changes the
DEFER picture without cleanly overturning it, so DEFER stands until you rule:

1. **Does this revise the basis of `DEFER_LOCAL_MODEL_PATH`?** The DEFER
   record attributes the failure to latency under VRAM spill. The evidence
   now shows the *warm* latency failure was dominated by a disabled
   serving-layer flag: with FA on, both candidates pass the warm gate and
   all quality gates. DEFER is not automatically wrong — the cold gate still
   fails — but its stated rationale is no longer the whole story. Whether to
   annotate/supersede the DEFER record is your call (§17), not mine.

2. **The cold gate now fails on a model-load anomaly, not inference.** Cold
   load was 56 s / 75 s in this run vs 5 s / 11 s in the original FA-off run
   — 10× worse, and FA cannot cause that (it does not touch weight loading).
   Likely environmental (cold OS cache after the Ollama restart + five
   back-to-back full reloads per model under mmap-disabled Windows+CUDA).
   Options: re-run the cold pass against a warm OS cache; investigate the
   mmap-disabled load path; or decide the cold gate should be measured under
   sustained-warm (`keep_alive`) operation, which is how the tool would
   actually run. Each is a distinct choice; none taken.

3. **Formalize flash attention (± `OLLAMA_KV_CACHE_TYPE`) into §9/§14
   configuration identity.** Still open from 2026-09-05, now with force: the
   FA-on and FA-off runs currently share an `invocation_configuration_id`
   because v3 does not encode the flag. A dated, versioned protocol edit
   (human-only) would close this before any reopened Phase 0 pass.

4. **If you reopen Phase 0, which candidate set?** The `qwen3.5:9b` line
   from `phase1-protocol-amendment.draft.md` is still on the table and, being
   fully GPU-resident, would likely dodge both the spill and the cold-load
   penalty. No amendment drafted into protocol form; the draft remains a
   draft.

**2026-09-06 — Ruling on `DEFER_LOCAL_MODEL_PATH` after the operational
batch.** *(RESOLVED 2026-09-06: B accepted — see Done.)* Evidence says LOCAL PATH WORKS for active warm-session use and the
cold-start gate passes (process-cold). Recommendation: **B — revise DEFER
to warm-session-only.** Runners-up: A keep DEFER (ignores a clean pass),
C reopen candidate selection (not needed; the 9B control only fails on a
harness think-flag gap, which would itself need a §9 edit). Human-only
decision (§17); nothing modified. If B: it needs a dated, versioned decision
record before any Phase 1a work.

**2026-09-06 — Phase 1a is prepared and needs the admission decision.** A full
Phase 1a preparation pass was requested. Grounding in the governing documents,
the Phase 1a evaluation harness cannot be built-and-merged or run yet, for two
independent reasons: (1) no Phase 1a admission decision exists, and three
sources gate the full harness behind that human-only act — §6's DEFER outcome
("stop before building the full harness"), `NORTHSTAR.md` ("no implementation
beyond the current admitted phase"), and the decision record ("Admission to
Phase 1a … remain separate, versioned human decisions"); (2) no real fixture
corpus exists — only 5 synthetic fixtures, where §11 requires 30–50 real
redacted logs with dual labels and primary-evidence spans, and synthetic-as-real
is disallowed. Prepared instead (no state change): a readiness/gap/governance
assessment plus a ready-to-implement build spec —
`reviews/2026-09-06-phase1a-preparation-readiness.md`. Needs your call: **a
dated, versioned Phase 1a admission decision** naming the admitted
configuration(s) (30B eligible; 14B needs a cache-controlled rerun; 9B needs
resolution + a §3/§9 amendment), the measured-batch keep-alive policy (ratify
request+server `30m` and authorize the dated `REQUEST_KEEP_ALIVE` harness edit
before collection), and whether/how real redacted fixtures may be sourced. The
protected `PHASE1A-ADMISSION-KICKOFF.draft.md` was left untouched; § 5 of the
assessment is a checklist to fold into it. Nothing modified in NORTHSTAR.md,
§§6/9/13, the candidate list, or any historical decision language.
