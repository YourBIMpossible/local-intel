> **Draft only — not approved policy, decision, admission, or authorization.**
>
> Filed under `docs/drafts/` on 2026-09-06 for preservation and human review.
> Non-authoritative: nothing here changes `NORTHSTAR.md`, the protocol
> (§§6/9/13), any decision record, candidate status, or Phase 1 state. Phase 1a
> and Phase 1b remain unstarted; admission is a separate, versioned human
> decision (§17). Authoritative readiness/gap record:
> `reviews/2026-09-06-phase1a-preparation-readiness.md`.

---

# Phase 1a Admission Decision + Kickoff Plan — DRAFT

> **Status: draft for human ruling. Not a decision. Not an instruction to run
> anything.** Per protocol §17 and `NORTHSTAR.md`, admitting a configuration to
> a new phase is a human, versioned act. This document requests that ruling and
> lays out what admission would set in motion. Nothing here freezes a parameter,
> starts an implementation, edits the protocol, or authorizes any Evidence
> Compiler change.
>
> Prepared 2026-09-06 against Local Intel branch `claude/project-pause-status-f34b4e`
> (evidence tip `7681d4c`). It **relies on the corrected evidence branch** —
> see `PHASE1A-EVIDENCE-CORRECTIONS.draft.md`. Do not sign this admission until
> those corrections are applied, because the warm-latency margin and the
> keep-alive statement it rests on are exactly what those corrections fix.

---

## 0. Governing documents (read before ruling)

| Doc | Role |
|---|---|
| `NORTHSTAR.md` | Locked mission + off-limits for this repo |
| `phase1-local-intelligence-protocol-v3.md` | The governing protocol; every gate/metric/state below is quoted from it |
| `decisions/2026-09-06-defer-revision-warm-session-only.md` | The §17 ruling this admission builds on (DEFER → warm-session-only) |
| `phase0_results/PHASE0_OPERATIONAL_REPORT_2026-09-06.md` | The evidence that both candidates pass §6 warm |
| `PHASE1A-EVIDENCE-CORRECTIONS.draft.md` | Residual evidence corrections that must land first |

---

## 1. The exact decision being requested

**Requested §17 ruling:** *Narrowly admit `qwen2.5-coder:14b` and
`qwen3-coder:30b-a3b-q4_K_M` from state `paused` to state `offline` — Phase 1a
offline artifact-quality evaluation only — under the warm-resident operating
conditions measured on 2026-09-06.*

This is the Phase 0 decision-table outcome "Admit the model to Phase 1a"
(§6), now available because the 2026-09-06 operational batch showed both
candidates pass every §6 gate when warm-resident (§2 below). It is the
`paused → offline` transition, which §17 lists as **never automatic** and
requiring exactly this human decision.

### What this admission explicitly does NOT do

- It does **not** admit anything to Phase 1b (`offline → evaluation` is a
  separate later §17 decision, earned only by the Phase 1a decision in §12).
- It does **not** authorize live presentation, MCP exposure, or any automatic
  path. Phase 1a is offline evaluation only (§7, §12).
- It does **not** admit or reject `qwen3.5:9b`. The 9B is held out until its
  `think:false` diagnostic is captured as committed evidence (see corrections
  draft §E and §6 note below). Its 0/5 structural validity in the operational
  batch is a harness-output-handling limitation, not a model result.
- It does **not** claim cold-start viability. The 2026-09-06 ruling scoped the
  approval to warm sessions; true process-cold first use can still take ~1 min.
  Phase 1a latency is therefore interpreted under warm-resident state only.
- It does **not** edit any §6 kill threshold, §9 generation parameter, or §13
  pairing rule. Those remain frozen and human-only.
- It does **not** authorize any change to Evidence Compiler (see §8).

---

## 2. Evidence basis (from the corrected branch)

Operational batch, 2026-09-06, FA on + warm-resident (§6 gates: warm ≤20,000 ms,
cold ≤60,000 ms, structural validity ≥3/5). **Warm figures below are the genuine
4-run medians that exclude the f01 prompt-cache-hit run** (the 5-run median that
includes it is shown in parentheses — it is the number in the report's headline
table and it is cache-inflated):

| Model | Digest | Quant / size | Warm median (genuine / 5-run) | Cold median | Validity (cold/warm) | Citation | §6 |
|---|---|---|---|---|---|---|---|
| qwen2.5-coder:14b | 9ec8897f | Q4_K_M / 8.99 GB | **19,157** ms (17,977) | 23,768 ms | 5/5 · 5/5 | 10/10 | **PASS** |
| qwen3-coder:30b-a3b-q4_K_M | 06c1097e | Q4_K_M / 18.56 GB | **16,728** ms (16,369) | 25,126 ms | 5/5 · 5/5 | 10/10 | **PASS** |
| qwen3.5:9b (control) | 6488c96f | Q4_K_M / 6.59 GB | 8,403 ms | 16,393 ms | 0/5 · 0/5 (harness) | — | held out |

**Read the margin honestly (this is why the corrections must land first):** the
14B **genuine** warm median is 19,157 ms — **under 1 s of headroom** below the
20,000 ms gate, and **2 of its 4 genuine runs (20,336 and 21,175 ms) are over
the gate**. The comfortable-looking 17,977 ms in the report headline includes
the f01 prompt-cache hit (71 ms prefill) and overstates the margin. A worker
view longer than the frozen 24 k budget would breach the gate for 14B. The 30B
genuine warm median (16,728 ms, 0 of 4 over) has more room. Admission is
defensible, but it is admission of a **narrow, warm-only, margin-aware**
capability for 14B, not a comfortable pass. Cold worst-case for 14B was a single
58.0 s run (inside the 60 s gate by 2 s).

---

## 3. Phase 1a hypotheses, success metrics, gates, stop rules (from the protocol)

### What Phase 1a tests (§1 decomposition, §12)

> Can a local model produce **structurally valid, source-grounded, useful
> triage** over an immutable EvidencePacket worker view — **and** does the
> worker view retain the evidence a correct answer requires?

Phase 1a evaluates exactly two things (§12):

1. The C and D candidate **model** configurations (artifacts vs. labels).
2. The **compressor's** primary-evidence recall (§7) — a property of the
   worker-view builder, never charged to the model.

It does **not** prove the artifact improves Claude's real work — that is Phase
1b. Arms A and B (raw/compressed to Claude) are **not** Phase 1a arms; Phase 1a
has no consuming agent.

### Success metrics (§12)

`compressor_primary_evidence_recall` (compressor) · structural validity ·
structural rejection rate · citation integrity · citation support under the §11
rubric · primary-failure accuracy · cascade-vs-independent accuracy · correct
abstention · per-fixture self-consistency · cold/warm latency · worker-view
coverage.

### Count-based gates (§12) — verbatim

| Gate | Requirement | Charged to |
|---|---|---|
| Compressor recall | Primary-failure evidence retained in the worker view for **all** labeled holdout cases; any failure → `REVISE_WORKER_VIEW` **before** judging any model | Worker-view builder |
| Structural failure | 0 structural failures across ≥30 holdout invocations per admitted configuration (via repetitions) | Model config |
| Citation integrity | 0 invalid citation spans across the same invocation set | Model config |
| Citation support | ≥85% "supported" among non-abstaining claims, raw numerator/denominator reported | Model config |
| Abstention | No systematic failure to abstain on adjudicated insufficient/ambiguous cases | Model config |
| Stability | No unexplained high-variance behaviour across repeated invocations | Model config |

Cases failing compressor recall are **excluded** from model-quality denominators.

### Repetition discipline (§12)

k ≥ 3 repetitions per fixture per candidate configuration under the pre-committed
generation parameters. Report per-fixture consistency, cross-run structural
validity, citation stability, hypothesis stability, abstention stability.
Instability is a finding even if one run looks strong. State whether stability
is interpreted against greedy or sampled decoding (§9).

### Stop rules / decision outcomes (§12)

Phase 1a ends in exactly one pre-committed decision:
`ADMIT_TO_PHASE_1B` · `ADMIT_NARROWLY` · `REVISE_WORKER_VIEW_OR_SCHEMA` ·
`REVISE_OUTPUT_CONSTRAINTS` · `DEFER_MODEL` · `KILL_LOCAL_WORKER`.
Admission to Phase 1a permits a config to run advisory in flagged Phase 1b
sessions only **after** that decision — it does not authorize general exposure.

Hard stops during Phase 1a: a compressor-recall failure halts model judging
until the worker view is revised; a structural-contract failure auto-pauses the
configuration (§17).

---

## 4. Contracts and inference parameters to FREEZE before any data collection

Freezing is a prerequisite to collection (§9, §18 Phase 1a steps 1–2). Nothing
below is frozen by this draft — freezing is part of the admitted work, done as a
versioned commit before the first labeled invocation.

### 4a. Small contracts to freeze (§18.1)

`EvidencePacket`, `SourceSpan`, `DerivedArtifact`, `InvocationConfiguration`.
(Phase 0 already produced working versions of the packet, worker-view, and
artifact/validator — freeze = pin their schema + version, not necessarily
rewrite.)

### 4b. Generation parameters to freeze (§9) — one candidate configuration each

| Parameter | Value to freeze | Source |
|---|---|---|
| temperature / top_p / top_k / seed | the committed `GenerationParameters` defaults | `local_intel/config_identity.py` |
| num_ctx | 32768 | §9, load segments |
| max output tokens | 1800 | §9 |
| timeout | `INVOCATION_TIMEOUT_MS` | `run_phase0_smoke.py` |
| **request** keep_alive | **10 m** (the value the benchmark requests used) | corrections draft §A |
| server keep_alive | 30 m (env; overridden per request) | server banner |

State the greedy-vs-sampled interpretation explicitly (§9): repetitions at
temperature 0 measure runtime nondeterminism only; under sampling they measure
model stability.

### 4c. Serving / runtime identity to record and pin (§9, §14, 2026-09-06 conditions)

`OLLAMA_FLASH_ATTENTION=1` (server, verified from banner) · server
`OLLAMA_KEEP_ALIVE=30m` · **request keep_alive 10m** · model tag + digest +
quant (14B `9ec8897f` Q4_K_M; 30B `06c1097e` Q4_K_M) · layer offload / residency
(record actual GPU/CPU split; the operational run had 14B at 47/49 with ~4.7 GB
VRAM held by other apps) · Ollama version (0.32.14) · hardware profile id +
hash · benchmark condition (warm-resident) · disk-cache condition (process-cold
≠ disk-cold — state as uncontrolled).

### 4d. Output validation to freeze (§8)

The hard validator's 8 checks (schema validity, provenance/config identity,
source-ID membership, span in-range, worker-view membership, budget fit, no
forbidden field/tool/side-effect/authority content, correct derived-authority
class). Phase 0 step 3 already implements all 8 — freeze its version.

### 4e. Explicitly OPEN, not frozen here (route to a human decision)

- **KV cache type.** Operational run used server default f16/f16. Whether
  `OLLAMA_KV_CACHE_TYPE=q8_0` is (a) a new §9 candidate configuration or (b) a
  §14 serving parameter is **undecided** and must be ruled before it is tested.
  It also has a real quality cost (lower-precision KV can degrade long-context
  citation recall — the very thing the citation gate measures). Do not enable it
  inside this admission.
- **qwen3.5:9b candidacy.** Out until the `think:false` diagnostic is committed
  evidence (§6 note, corrections §E).

---

## 5. Real-fixture collection plan (§11)

Phase 0 ran on **synthetic** fixtures (`fixture_provenance: SYNTHETIC`). Phase 1a
requires **redacted real** test logs — this is the largest single piece of the
Phase 1a lift and it needs the maintainer to seed real logs.

### 5a. Corpus (§11)

30–50 redacted real test-log cases from actual BIMpossible test/CI runs,
stratified across: easy · realistic/cascade-heavy · multiple-independent-
failures · parallel/interleaved · environment/infrastructure · insufficient/
malformed evidence · adversarial prompt-injection-bearing.

### 5b. Redaction as reproducibility (§11)

Record `redaction_policy_version`, `redaction_tool_version`,
`redaction_input_hash`, `redaction_output_hash`. Same source under the same
config → same redacted fixture. A redaction change creates a new fixture version
and batch boundary. (Reuse/extend the existing `local_intel/redaction.py` /
`redact_paths.py`; version them.)

### 5c. Splits (§11)

Development · Validation · **Protected holdout** (never used for prompt,
worker-view, schema, or threshold tuning) · Adversarial.

### 5d. Labels (§11) — the part that needs a second human

For protected-holdout cases: two independent labels for diagnosis,
cascade/independent classification, citation support, and correct abstention.
One labeler may be the operator; **the other must be independent** (a second
frontier model may assist only if recorded as such; human adjudication is
final). Preserve both labels + adjudication history. Labels also mark the
**primary-evidence line ranges** that power the §7 compressor-recall metric.
Grade citations with the §11 five-point rubric (Supported / Partially / Unsupported
/ Contradicted / Indeterminate) and report the distribution, not just a binary.

### 5e. Practical sequence

1. Pull N raw failing test-log runs from BIMpossible CI/local runs (aim 40).
2. Redact with the versioned redactor; record the four hashes.
3. Stratify + assign splits; freeze the holdout.
4. Operator labels; independent second labeler labels; adjudicate; record.
5. Mark primary-evidence line ranges on every holdout case.

---

## 6. Smallest implementation slices (§18 Phase 1a)

Build only what Phase 1a needs. Where Phase 0 already produced a component, the
slice is *freeze + extend*, not *rewrite* — assess reuse first.

| Slice | §ref | Exists from Phase 0? | Work |
|---|---|---|---|
| Deterministic worker-view builder | §7 | Yes (`local_intel/worker_view.py`, v1) | Freeze version; add the §7 compressor-recall instrumentation (does the primary-evidence span survive truncation?) |
| Hard artifact validator | §8 | Yes (`local_intel/validator.py`, 8 checks) | Freeze version; confirm all 8 checks against the frozen schema |
| Append-only SQLite ledger | §10 | **No** | New: the §10 event set, append-only, no triggers/rollups/routing; offline stateless report gen only |
| Repeatable evaluation runner | §12 | Partial (operational runner pattern) | New/extend: k≥3 per fixture/model/config, per-fixture consistency, holdout-only invocation accounting, rubric scorecard output |

9B note: no slice touches 9B until its diagnostic is committed evidence.

---

## 7. Work sequence, dependencies, acceptance criteria, decision points

Ordered per §18 Phase 1a, with the binding dependencies made explicit.

| # | Step | Depends on | Acceptance criterion | Decision point |
|---|---|---|---|---|
| 0 | Land evidence corrections | — | Corrections draft items A–E applied; branch push-clean | — |
| 1 | Human §17 admission ruling | 0 | This document signed; 14B + 30B admitted `paused→offline`; 9B held | **GO/NO-GO** |
| 2 | Freeze contracts + generation params + serving identity | 1 | §4 frozen as a versioned commit; config-identity hash stable across a repeat run | — |
| 3 | Build real fixture corpus + labels | 1 | §5 done: ≥30 holdout cases, dual labels, primary-evidence line ranges, four redaction hashes | — |
| 4 | Measure compressor primary-evidence recall | 2,3 | Recall computed on all holdout cases | **If any case fails → `REVISE_WORKER_VIEW`, do not judge models** |
| 5 | Build ledger + evaluation runner | 2 | §10 events append-only; runner does k≥3 and emits the §12 scorecard | — |
| 6 | Run repeated offline evaluation | 4(pass),5 | ≥30 holdout invocations/config; scorecard with raw numerators/denominators | — |
| 7 | Phase 1a decision | 6 | One of the §12 outcomes, human + versioned | **ADMIT_TO_PHASE_1B / ADMIT_NARROWLY / REVISE_* / DEFER_MODEL / KILL** |

Dependency invariants: **freeze before collect** (2 before 3's freeze-dependent
parts), **recall before model judging** (4 gates 6), **holdout never tunes**
anything (§11).

---

## 8. Authorization boundary — explicit

- **No Evidence Compiler core change is authorized by this document.** Local
  Intel is a separate repository and experiment. Nothing here modifies
  `src/evidence_compiler/`, its schema, its collectors, or its adapter.
- Any future move to wire local inference into Evidence Compiler's "Optional
  inference" candidate direction requires its **own** one-page EC phase proposal
  under EC's locked `NORTHSTAR.md` (problem from real packets, ≥3 examples,
  non-goals, measurable metric, smallest slice). Phase 1a here is upstream
  evidence for that separate future decision, not a substitute for it.
- No protocol edit (§6/§9/§13) is proposed or performed here.
- No push, PR, or merge is performed by the session preparing this draft.
