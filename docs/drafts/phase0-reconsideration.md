> **Draft only — not approved policy, decision, admission, or authorization.**
>
> Filed under `docs/drafts/` on 2026-09-06 for preservation and human review.
> Non-authoritative: nothing here changes `NORTHSTAR.md`, the protocol
> (§§6/9/13), any decision record, candidate status, or Phase 1 state. Phase 1a
> and Phase 1b remain unstarted; admission is a separate, versioned human
> decision (§17). Authoritative readiness/gap record:
> `reviews/2026-09-06-phase1a-preparation-readiness.md`.

---

# Reconsidering the Local-Model Path — A Fresh Read on Phase 0

Analysis/proposal document, not a decision record. Written 2026-09-01 at
user request, read-only pass — no commands run, no files pulled, nothing
executed. Informed by the Phase 0 evidence set and by the candidate-model
research behind `phase1-protocol-amendment.draft.md`.

---

## Reframing the Phase 0 result

The DEFER decision is correct as recorded and isn't being questioned here.
But it's worth separating what Phase 0 actually demonstrated from what it's
easy to remember it as having demonstrated.

**What it's easy to remember:** "we tried local models for this and they
were too slow — the local-model path doesn't work."

**What the evidence actually shows:** two specific mid-size models, loaded
at a specific large context size, didn't fit in 16 GB of VRAM, and
inference over the CPU-spilled remainder was 7–45x too slow. Every gate that
measured the models' *output quality* — structural validity, citation
integrity — passed cleanly, at 5/5 and 7/7. Nothing in the evidence set says
local inference produces bad triage artifacts. Everything in the evidence
set says two particular models were the wrong size for this GPU at this
context length.

That's a much narrower and more fixable finding than "local doesn't work,"
and the original Phase 0 design didn't have the surface area to distinguish
between the two, because it only tested two models, both in the 14–30B
range, on one hardware profile. It tested one point on a curve and drew a
conclusion about the whole curve — appropriately, for the candidates it was
scoped to (that's exactly what pre-commitment is for), but the curve itself
turns out to have more shape to it than one point can reveal.

## The three levers Phase 0 conflated

Phase 0's failure was produced by the interaction of three independent
variables, and the original design only ever varied one of them (model
identity, across exactly two points):

1. **Model size.** Bigger models mean bigger weights *and*, for
   non-MoE-KV-shared architectures, bigger KV caches. This is the lever
   Phase 0 tested — badly, in the sense that both test points (14B, 30B‑A3B)
   sit on the same "too big for 16GB at 32K context" side of the line. There
   was no small-model test point to triangulate against.
2. **Context/KV-cache footprint.** At `num_ctx=32768`, KV cache was ~6.7 GB
   for the 14B model alone — nearly as much memory as the model's own
   quantized weights. This is a function of the frozen 24K-token worker view
   (rightly untouchable — §6 pre-commitment is doing its job by refusing to
   let this get tuned away) *and* of serving-layer choices like KV-cache
   quantization, which Phase 0 never varied at all.
3. **Hardware.** Fixed at one workstation, 16 GB VRAM. Reasonable to hold
   fixed for a "does this work on my actual machine" experiment, but worth
   naming as a variable rather than a given, since it's the least flexible
   of the three and the other two exist specifically to work around its
   limit.

Phase 0 varied only #1, and only across two points that both landed on the
same side of the failure line. That's not a design flaw in Phase 0 — the
protocol pre-committed to exactly two named candidates on purpose, to avoid
the trap of tuning candidates until one passes. But it does mean "neither
candidate fits" is a true and honest statement about a 2-point sample, not
proof that no point on the curve fits.

## Three paths, ranked by how much they disturb what's already settled

**Path A — smaller models (cheapest, least disruptive).** Test whether a
9B-class model (`qwen3.5:9b`, 6.6 GB weights vs. 9.0 GB / 18.5 GB for the
original candidates) clears the *same, unmoved* §6 kill thresholds. This
doesn't touch the thresholds, doesn't touch the worker-view size, doesn't
touch anything except which model tag is loaded. It's the most surgical way
to re-test the hypothesis without reopening anything that was actually
contentious in the original design. See the amendment draft for what
formal protocol change this would require.

**Path B — KV-cache quantization on the existing candidates (orthogonal,
untested).** Never varied in Phase 0 at all. If `OLLAMA_KV_CACHE_TYPE=q8_0`
shrinks the 14B model's ~6.7 GB KV overhead enough to get it fully
GPU-resident, the *original* candidate could pass without adding anything
new to the roster. This is worth testing independently of Path A — a
serving-layer question, not a model-choice question, and answering it
doesn't require the arm-restructuring decisions Path A does. It does raise
its own open question (does this count as a new configuration under §9, or
as a hardware/serving parameter under §14) that a human still needs to rule
on before it's tested for real.

**Path C — different/bigger hardware (most disruptive, weakest fit to the
mission).** Would isolate "is this a hardware ceiling or a bad-fit
candidate" cleanly, but the mission is specifically framed around local
inference *on this workstation* via Ollama — cloud or bigger-GPU inference
changes the economics (cost, latency profile, offline availability) that
the whole point of "local" was buying. Worth naming as an option, not
worth prioritizing unless A and B both fail again.

## Suggested sequencing (not a decision — a recommendation)

Test cheaply before formalizing expensively. A and B are both answerable
with a non-binding residency/telemetry probe — the same low-stakes
"pull it, load it, check `ollama ps`, don't submit evidence packets" pattern
Phase 0 step 4 already used for the original two candidates and explicitly
did *not* treat as a protocol violation. Running that probe for `qwen3.5:9b`
and for `OLLAMA_KV_CACHE_TYPE=q8_0` on the existing 14B candidate would tell
you, within a few minutes, which of A/B/neither is worth the amendment
paperwork — before any dated, versioned protocol edit gets drafted for real.

If neither A nor B produces a candidate that's even in the residency
ballpark, that's a much stronger and more complete basis for confirming
DEFER than the original 2-point sample was — not because the original
decision was wrong, but because it would now be closing off a properly
explored space instead of a narrow slice of it.

## What this document is not

It is not a re-vote on `DEFER_LOCAL_MODEL_PATH`. It is not an instruction to
run anything. It is not a claim that Path A or B will succeed — `qwen3.5:9b`
has not been residency-tested, and KV-cache quantization has a real quality
cost (lower-precision KV cache can degrade long-context recall/citation
accuracy — exactly the property Phase 0's citation-integrity gate measures,
so it isn't a free lunch). It's a map of the option space that Phase 0's
necessarily narrow, pre-committed design didn't have room to explore, laid
out so the next decision — if there is one — is made with the full
picture rather than the 2-point one.
