# Phase 1a preparation — readiness, gap analysis, and admission gate

- **Date:** 2026-09-06
- **Author:** Claude (Opus 4.8), automated preparation pass
- **Type:** readiness assessment / build specification. **Not a decision.** Nothing
  here admits a model, transitions a state, edits a frozen threshold, or begins
  Phase 1a data collection.
- **Authoritative sources:** `phase1-local-intelligence-protocol-v3.md`,
  `decisions/2026-09-06-defer-revision-warm-session-only.md`, `NORTHSTAR.md`,
  `WORKLOG.md`, the merged Phase 0 reports. Repository documents — not prior
  conversation — are treated as the source of truth throughout.

## TL;DR

A full Phase 1a preparation-and-execution pass was requested. After grounding in the
governing documents, the apparatus for Phase 1a **cannot be built-and-merged and cannot
be executed yet**, for two independent reasons, either of which is sufficient:

1. **No Phase 1a admission decision exists**, and three governing sources gate building
   the full Phase 1a harness behind that (un-made, human-only) decision (§ [Governance
   gate](#2-governance-gate--why-the-harness-is-not-built-here)).
2. **No real fixture corpus exists.** Only five *synthetic* fixtures are present; the
   protocol requires 30–50 *real* redacted logs with dual labels and primary-evidence
   line-range spans. Synthetic-as-real is explicitly disallowed
   (§ [Blocking fact](#3-blocking-fact--no-real-fixture-corpus)).

What was safely produced instead: this authoritative state-of-record, a gap analysis of
existing scaffolding vs. protocol Phase 1a requirements, a ready-to-implement build
specification (design only, no state change), and the admission-decision content the
human must supply. Post-admission, the build is fast and mostly a matter of assembling
components that already exist.

**Outcome:** *Phase 1a is fully prepared and requires this admission decision.* The
smallest human input needed is in § [The decision](#6-the-smallest-human-decision-needed).

---

## 1. State of record (from repository documents)

### 1.1 No Phase 1a admission decision exists

`decisions/` holds exactly one record: `2026-09-06-defer-revision-warm-session-only.md`.
It states, verbatim, in its **Not decided here** section: *"Admission to Phase 1a,
candidate selection, and any §6/§9/§13 edit remain separate, versioned human
decisions."* Its final amendment states: *"'Eligible for a future Phase 1a admission
decision' … is not an admission. **No Phase 1a admission has been made.**"*

### 1.2 Model candidate status (none admitted)

Per the final ruling amendment in the decision record:

| Model | Status | Blocker to admission |
|---|---|---|
| `qwen3-coder:30b-a3b-q4_K_M` | **Eligible** for a future Phase 1a admission decision | Not admitted; awaits the human admission act |
| `qwen2.5-coder:14b` | **Not admitted** | Two of four genuine warm runs exceeded 20 s; needs a cache-controlled rerun |
| `qwen3.5:9b` | **Unresolved** | `think:false` diagnostic proves it *can* emit valid structured output, but does not recreate/explain its prior 0/5 batch outcome |

The protocol §3 candidate list remains the two coder models; 9B is a draft addition
(`phase1-protocol-amendment.draft.md`) that has never been ratified into the protocol.

### 1.3 Frozen contracts and parameters (already in place — do not touch)

- **Generation parameters (§9)** are already frozen in `local_intel/config_identity.py`:
  `temperature 0.0, top_p 1.0, top_k 1, seed 0, num_ctx 32768, max_output_tokens 1800`.
  These are §9-frozen and NORTHSTAR-protected; changing them requires a dated, versioned
  protocol edit. Untouched here.
- **§6 kill thresholds** (`run_phase0_smoke.py:KILL_THRESHOLDS`) are frozen. Untouched.
- **Artifact schema / validator / worker-view / packet / prompt versions** are all `v1`
  and hashed into the invocation-configuration identity. Untouched.

### 1.4 Keep-alive policy (measured vs. approved-going-forward)

- The 2026-09-06 operational batch measured **server `OLLAMA_KEEP_ALIVE=30m`** but
  **request `keep_alive=10m`** (the request value overrides for the load it triggers).
  The measured residency window was therefore **10 minutes**, not 30.
- The approved *going-forward* active-session policy is explicit client
  `request_keep_alive=30m` **and** server `OLLAMA_KEEP_ALIVE=30m`.
- The harness constant `REQUEST_KEEP_ALIVE` in `run_phase0_smoke.py` still reads `"10m"`.
  Implementing the 30 m policy is a **dated edit that must precede the next measured
  batch** (§9/§14 discipline) — it is not made here, and no 30-minute client window has
  been measured. Future measurements must record server-level and request-level
  keep-alive **separately** (already supported by `RuntimeIdentity.request_keep_alive`,
  `RUNTIME_IDENTITY_VERSION 2026-09-06.2`).

### 1.5 Existing infrastructure inventory (Phase 0 scaffolding already built)

| Protocol Phase 1a need | Status | Where |
|---|---|---|
| `EvidencePacket` contract | **Built** | `local_intel/packet.py` (`EvidencePacket`, `content_hash()`) |
| Deterministic worker-view / compressor | **Built** | `local_intel/worker_view.py` (`build_worker_view` → `WorkerView`) |
| `DerivedArtifact` schema + spans (§8) | **Built** | `local_intel/artifact.py` (`ARTIFACT_SCHEMA`, `SPAN_SCHEMA`) |
| Hard validator (§8, 8 checks) | **Built** | `local_intel/validator.py` (`validate_artifact`) |
| Frozen worker prompt (§3/§9) | **Built** | `local_intel/prompt.py` |
| Bounded Ollama invocation + telemetry | **Built** | `local_intel/ollama_client.py` (`invoke`, `InvocationTelemetry`) |
| Invocation-configuration identity (§9) | **Built** | `local_intel/config_identity.py` |
| Runtime identity (serving-layer facts) | **Built** | `local_intel/runtime_identity.py` |
| Field-level + whole-document redaction (§11) | **Built** | `local_intel/redaction.py`, `local_intel/redact_paths.py` |
| End-to-end triage path | **Built** | `local_intel/triage.py` (`triage_log` → `TriageOutcome`) |
| Deterministic fixture generation | **Built (synthetic)** | `generate_fixtures.py`, `fixtures/` (5 fixtures) |
| **Real redacted corpus (30–50) + labels + primary-evidence spans (§11)** | **MISSING** | — |
| **Append-only SQLite Observation & Evaluation Ledger (§10)** | **MISSING** | — |
| **Repeatable offline evaluation runner (k≥3, §12)** | **MISSING** | — |
| **Scoring: citation-support rubric, primary-evidence recall, accuracy, stability (§7/§11/§12)** | **MISSING** | — |

The three MISSING code items plus the real corpus **are** "the full harness" that §6's
DEFER outcome says to stop before building (see § 2).

---

## 2. Governance gate — why the harness is not built here

Building and merging the Phase 1a evaluation harness (SQLite ledger, evaluation runner,
scoring, and a real labeled corpus) onto `master` now is blocked by three independent,
mutually reinforcing sources:

1. **Protocol §6, Phase 0 decision table.** The `defer local model path` outcome reads:
   *"Stop before building the full harness; defer local model path."* The DEFER was
   revised (2026-09-06) to *warm-session-only* and approved active use, but that revision
   **explicitly did not admit Phase 1a**. The "stop before building the full harness"
   posture for the Phase 1a evaluation apparatus was never lifted.
2. **`NORTHSTAR.md` (locked, human-only).** Off-limits: *"No implementation beyond the
   current admitted phase."* The current admitted phase is Phase 0. Phase 1a is not
   admitted.
3. **The decision record.** Admission to Phase 1a and candidate selection are named as
   *"separate, versioned human decisions"* that have not been made.

The protocol's clean mechanism to unlock the harness is exactly a **Phase 1a admission
decision** (§6 → §12 → §18) — the one human-only act the task instructs me not to
invent. Therefore the honest boundary is: prepare everything that changes no experiment
state, and stop at the admission gate. This assessment and its build spec are that
preparation; the harness build is deliberately **not** started or merged.

This is recorded as a *Needs your call* item in `WORKLOG.md` per the north-star's
three-door rule.

---

## 3. Blocking fact — no real fixture corpus

Independent of the governance gate, Phase 1a **execution** is impossible today:

- `fixtures/manifest.json` `provenance`: *"SYNTHETIC. §6 specifies five representative
  REAL test-log packets; these are deterministic synthetic logs … Recorded as a
  deviation, not as satisfying §6 verbatim."* Five fixtures exist; all synthetic.
- Protocol §11 requires **30–50 redacted real** test-log cases, stratified across seven
  strata (easy, cascade-heavy, multiple-independent, parallel/interleaved,
  environment/infra, insufficient/malformed, **adversarial prompt-injection-bearing**),
  each with **two independent labels** and **primary-failure line-range spans** (§11.7,
  enabling the §7 compressor-recall metric).
- No real corpus is present or tracked anywhere in this repository, and none was located
  in-repo. Bringing real BIMpossible test/build logs in is a **privacy/redaction and
  access decision** the task reserves to the human; synthetic-as-real is disallowed.

So even with an admission decision, the first Phase 1a step (§18 Phase 1a step 7, "Build
versioned redacted fixtures and labels") requires **real fixture input** the automated
pass cannot supply.

---

## 4. Phase 1a build specification (ready to implement on admission)

Design only — committing this doc changes no experiment state. On admission, these are
directly implementable, mostly by composing existing modules.

### 4.1 Fixture / corpus contract (extends the current manifest)

Per-fixture record must add, to the existing manifest fields, the label/eval fields the
protocol requires (task item 1; §11):

```
fixture_id                  (present)
provenance                  (real source, redacted; per-fixture, not just top-level)
redaction {policy/tool ver, input_hash, output_hash, hits}   (present)
content_hash / packet_content_hash / worker_view_hash        (present)
source_line_spans           (NEW: adjudicated primary-evidence line ranges, per source_id)
task_question               (NEW: the triage question; today it is the single global prompt)
expected_key_facts          (NEW: adjudicated facts a correct artifact must reflect)
primary_evidence_spans      (NEW: the §7 recall targets — line ranges of the primary failure)
known_uncertainty           (NEW: where the evidence does not justify a single root cause)
label_version + label_author(s)   (NEW: two independent labelers; §11.1–11.5)
split                       (NEW: development | validation | protected_holdout | adversarial)
expected_classification     (present)
```

### 4.2 Label template (§11 labeling protocol)

One label file per fixture, holdout cases requiring **two** independent labels +
adjudication history preserved:

```
{ "fixture_id", "label_version", "labeler_id", "labeler_role": "operator|independent|secondary_model",
  "classification", "primary_failure_spans": [{source_id,start,end}],
  "cascade_or_independent", "citation_support_rubric_examples",
  "correct_abstention": bool, "notes",
  "adjudication": { "final_classification", "final_spans", "resolved_by", "history": [...] } }
```

### 4.3 Observation & Evaluation Ledger (§10) — append-only SQLite

- One table `events(event_id PK, ts_utc, run_id, fixture_id, invocation_configuration_id,
  event_type, payload_json)`, event types exactly the §10 set (`invocation.created`,
  `worker_view.created`, `artifact.generated`, `artifact.validated`, `artifact.rejected`,
  … `outcome.recorded`). **Append-only**: no update/delete; no triggers; no rollups; no
  routing; offline stateless report generation only (§10 restrictions).
- A `runs` projection table is a *read model* rebuilt from events, never a mutable source
  of truth (Architectural Law 10: the ledger preserves history, never redefines it).
- Payload carries worker-view/output hashes, token counts, durations
  (load/prefill/generation/total), structural validity, citation validity, claim-support
  result, evidence-recall, failure/abstention class, artifact locations — task item 5.

### 4.4 Repeatable evaluation runner (§12 + §14) — task item 6

Reuses the Phase 0 runner discipline already proven in `run_phase0_operational.py`:
unique run IDs + isolated artifact paths; whole-document `redact_local_paths` before
every write; persist after every fixture/run; partial-result preservation on
interrupt/timeout/exception (with explicit abort reason); sampler cleanup/flush in
`finally`; never overwrite prior runs; record prompt-cache/disk-cache condition in words;
record **server and request keep-alive separately**; **k ≥ 3** repetitions per
fixture×model×config; no disk-cold claim unless disk-cache state is controlled.

### 4.5 Scoring (§7, §11, §12) — task item 4/eval

- `compressor_primary_evidence_recall` (charged to the worker-view builder; recall
  failures exclude a case from model denominators and force `REVISE_WORKER_VIEW` before
  judging any model).
- Structural validity + structural rejection rate; citation integrity (already computed
  structurally by the validator); **citation support** under the §11 rubric
  (Supported/Partially/Unsupported/Contradicted/Indeterminate — report the distribution,
  not just a binary); primary-failure accuracy; cascade-vs-independent accuracy; correct
  abstention; per-fixture self-consistency; cold/warm latency; worker-view coverage.
- Count-based gates (§12): 0 structural failures across ≥30 holdout invocations per
  config; 0 invalid citations; ≥85% supported ratings among non-abstaining claims (report
  numerator/denominator); abstention correctness; stability.

### 4.6 Tests (task item 7)

Unit/integration for: the extended fixture contract; label-file schema; source-span &
citation validation (extend existing validator tests); ledger append-only invariants
(no update/delete; read-model rebuild); runner timeout/transport failure; interruption &
partial-result preservation; non-overwrite; runtime-identity capture; **server-level vs
request-level keep-alive recorded separately**; error classification & recovery.

---

## 5. What a Phase 1a admission decision must contain

For the human to make efficiently (a new dated record under `decisions/`, §17). **Note:**
a protected draft `PHASE1A-ADMISSION-KICKOFF.draft.md` already exists in the main
checkout; it has been deliberately left untouched and not duplicated. This checklist is
provided so it can be folded into that draft rather than competing with it.

1. **Which configuration(s) are admitted** to Phase 1a offline evaluation — from
   {`qwen3-coder:30b-a3b-q4_K_M` (eligible), `qwen2.5-coder:14b` (needs cache-controlled
   rerun first), `qwen3.5:9b` (needs resolution + a §3/§9 amendment to add it as a
   candidate and to set `think:false`)}. Per §3 the standing candidate set is the two
   coder models.
2. **Keep-alive policy for measured batches**: ratify request `keep_alive=30m` + server
   `30m`, and authorize the dated `REQUEST_KEEP_ALIVE` harness edit *before* collection.
3. **Corpus authorization**: whether real redacted BIMpossible logs may be sourced, under
   which approved redaction rules, and where they live (they must not enter git
   unredacted). Absent this, Phase 1a cannot collect data.
4. **Any §6/§9/§13 amendment** required by the above (e.g., adding 9B, or the FA/keep-alive
   config-identity formalization already flagged in `WORKLOG.md`) — dated and versioned
   *before* the phase it gates.

Admission authorizes the *offline* `evaluation` posture only (advisory in flagged Phase
1b sessions is a **later** Phase 1b decision; general MCP exposure is later still — §17).

---

## 6. The smallest human decision needed

> **Make (or decline) a dated, versioned Phase 1a admission decision naming the admitted
> configuration(s), the measured-batch keep-alive policy, and whether/how real redacted
> fixtures may be sourced.**

With that decision in hand, the build spec in § 4 is implementable in a single
subsequent pass — up to, but not including, real-fixture data collection, which still
depends on item 3 (real, safely-redactable logs). Until then, no harness is built or
merged, no model is admitted, and no evaluation data is collected.
