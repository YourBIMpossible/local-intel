> **Draft only — not approved policy, decision, admission, or authorization.**
>
> Filed under `docs/drafts/` on 2026-09-06 for preservation and human review.
> Non-authoritative: nothing here changes `NORTHSTAR.md`, the protocol
> (§§6/9/13), any decision record, candidate status, or Phase 1 state. Phase 1a
> and Phase 1b remain unstarted; admission is a separate, versioned human
> decision (§17). Authoritative readiness/gap record:
> `reviews/2026-09-06-phase1a-preparation-readiness.md`.

---

# Draft Amendment to Phase 1 Local Intelligence Protocol v3

**Status: DRAFT — NOT RATIFIED.** This is a proposal for human review, not an
edit to `phase1-local-intelligence-protocol-v3.md`. Per that document's own
rule (§6, §9), candidate identity and kill thresholds may only change via a
versioned protocol edit dated *before* the Phase 0 execution it governs.
Nothing in this file is authorized until a human renames/merges it into the
ratified protocol with a version bump.

Drafted: 2026-09-01. Author: Claude, at user request. No commands were run
to produce this file — it is a paper proposal only. No residency probe, no
`ollama pull`, no Phase 0 re-execution has occurred.

---

## 1. Why reopen

`DEFER_LOCAL_MODEL_PATH` (WORKLOG.md, 2026-08-22) closed the local-model path
**for one specific candidate configuration**: `qwen2.5-coder:14b` and
`qwen3-coder:30b-a3b-q4_K_M`, at the frozen `num_ctx=32768` implied by the
frozen `representative_view_size_tokens: 24000`, on `workstation-zeria-01`
(16 GB VRAM). Both missed the latency gates by 7–45x.

The failure mode was not model capability. Structural validity was 5/5 warm
for both models; citation integrity was clean on every run that produced an
artifact. The failure was VRAM residency: at Q4_K_M, the 14B model's weights
alone are 9.0 GB, and the KV cache at 32K context added another ~6.7 GB,
landing at 15.7 GB total against a 15.9 GB card (93% GPU-resident, rest
spilled to CPU — see `hardware_profiles/workstation-zeria-01.json`). The
30B‑A3B MoE model was worse: 18.5 GB of weights before any KV cache.

This closes a narrower question than "can local models do this job at all."
It closes "can these two specific mid-size models, at this context size, fit
on this card." Those are different questions, and the second one has more
unexplored answer space than Phase 0 tested.

## 2. What's new since the decision

`qwen3.5:9b` — an official Ollama library release (`ollama.com/library/qwen3.5:9b`,
confirmed via Ollama's own announcement) — did not exist as an evaluated
option in this protocol's original candidate list. At Q4_K_M it is **6.6 GB**
of weights, roughly a third the size of the 14B candidate and a third the
size of the 30B‑A3B candidate's weights alone. Smaller-still siblings
(`qwen3.5:4b`, `qwen3.5:2b`, `qwen3.5:0.8b`) also exist if 9B still doesn't
clear the bar.

This has **not been verified to fit** at `num_ctx=32768` on this hardware —
no residency probe has been run. The weight-size gap is large enough to be
worth testing cheaply (mirroring the non-binding hardware-profile probe done
in Phase 0 step 4) before spending any more protocol process on it.

A second, independent lever also surfaced during this review and was never
represented in the original protocol: **KV-cache quantization**
(`OLLAMA_KV_CACHE_TYPE=q8_0`/`q4_0`, with flash attention enabled). This is a
serving-layer setting, not a model swap — it could shrink the ~6.7 GB KV
overhead that was the actual proximate cause of the 14B model's shortfall,
independent of which model is loaded. Whether this counts as a new
"candidate configuration" under §9, or as hardware/serving telemetry that
belongs in §14's resource policy instead, is an open question this amendment
does not resolve — it needs a human ruling either way, since §9 currently
has no field for it.

## 3. Proposed protocol changes (open questions, not decisions)

If ratified, this amendment would need to touch:

**§3 Scope — candidate list.** Add `qwen3.5:9b` (and optionally the smaller
siblings) as additional candidates. Open question: added as a *third* arm
alongside the existing two, or substituted for one that already failed
(most plausibly replacing the 14B "fast local" slot, since 9B occupies
similar positioning)? This changes §4's Evaluation Arms table and its
comparator rules, so it isn't a one-line edit — it needs a human call on
arm structure.

**§6 Kill thresholds.** Recommend leaving `warm_e2e_max_ms`, `cold_e2e_max_ms`,
and `structural_validity_min` numerically unchanged — the point of adding a
smaller candidate is to see if it can clear the *existing* bar, not to move
the bar. But re-running Phase 0 at all still requires this section to be
re-dated under the "versioned protocol edit... before execution" rule, even
if the numbers themselves don't move.

**§6 Procedure — fixture realism.** The original Phase 0 pass used synthetic
fixtures (flagged as a caveat in WORKLOG.md), justified there because the
margin of failure (7–45x) was too large for the synthetic-vs-real gap to
matter. A smaller model landing *closer* to the gates would not have that
same safety margin — worth deciding whether a reopened Phase 0 pass must use
real fixtures from the start rather than synthetic ones.

**§9 Configuration identity.** New `model tag`/`model digest` for whichever
candidate(s) are added. If the KV-cache-quantization lever is pursued, §9 or
§14 needs a new field for it (e.g. `kv_cache_quantization`), since no field
currently exists to record it as part of invocation identity.

**§14 Resource policy / hardware telemetry.** If KV-cache quantization is
tested, the hardware profile capture (currently `hardware_profiles/*.json`)
would need a residency probe re-run with that setting active, analogous to
step 4's original probe.

## 4. What this amendment does not do

It does not reopen or reverse `DEFER_LOCAL_MODEL_PATH` for the original two
candidates — that decision stands as recorded. It does not pre-judge which
candidate(s) to add, how arms should be restructured, or whether KV-cache
quantization is in-scope as a serving parameter versus a new candidate
configuration. Those are exactly the questions a human needs to answer
before this draft could be dated, versioned, and merged into the ratified
protocol.

## 5. Suggested next step, not taken here

A cheap, non-binding residency probe (`ollama pull qwen3.5:9b`, load at
`num_ctx=32768`, check `ollama ps` GPU fraction — no evidence packets, not a
Phase 0 measurement, same posture as the original step 4 probe) would answer
the "does this even fit" question before any of the paperwork above is worth
finalizing. Not run in this pass per instruction to stay read-only.
