# North Star and Development Direction — 2026-09-06

Read-only reconstruction. No repository files were modified. Legend: **[F]** fact from repository evidence; **[P]** proposal found in a draft; **[A]** my assumption.

## Conclusion

**Do not proceed yet because there is no pull request to finish or revise, and the next state transition (Phase 0 → Phase 1a admission) is a human-only §17 decision that has not been made.** The branch `claude/project-pause-status-f34b4e` carries four unpushed evidence/decision commits on top of `origin/master`. The smallest correct next action is to open that branch as a PR scoped as evidence-and-decision-record only, merge it, and then make the admission decision on the record. Nothing in the FA-on result authorizes Phase 1a implementation by itself.

## 1. The "active/open PR"

**[F] None exists.** `gh pr list --state all` on `YourBIMpossible/local-intel` returns nothing; no issues exist. `origin` has one head, `master`, at `e68d040` (2026-08-22, "Add README"). The only other branch is this worktree's `claude/project-pause-status-f34b4e`: local, unpushed, no upstream.

**[F] What that branch contains (`master..HEAD`):**

| Commit | Content | Nature |
|---|---|---|
| `cbbbd6f` | FA-on Phase 0 re-measurement: WORKLOG, `phase0_results/PHASE0_REPORT_FA-ON_2026-09-06.md`, results JSON, `run_phase0_smoke_fa.py` | Evidence |
| `b4c9f59` | `local_intel/runtime_identity.py` + `runtime-identity-amendment-2026-09-06.md`: additive, out-of-band recording of FA, keep-alive, KV type, offload, driver | Instrumentation; no §9 edit |
| `9c13ba3` | Operational batch (FA on, keep-alive 30 m): `run_phase0_operational.py`, results JSON, telemetry CSVs, server-log segments, `phase0_results/PHASE0_OPERATIONAL_REPORT_2026-09-06.md` | Evidence |
| `459d7b0` | `decisions/2026-09-06-defer-revision-warm-session-only.md`; WORKLOG and README annotations | Human decision record (§17) |

- **Tests:** `pytest -q` → 62 passed. **[F]**
- **Review comments, linked issues, acceptance criteria:** none; no PR or issue exists. **[F]**
- **Relation to the plan:** Phase 0 follow-up plus its decision record. It is not Phase 1a work and not a §18 Phase 1a prerequisite; it is the evidence base for the §6/§17 admission decision (§18 Phase 0 step 6: "Decide per the pre-committed §6 table"). **[F]**
- **Untracked, not on the branch:** `phase0-reconsideration.md`, `phase1-protocol-amendment.draft.md` (2026-09-01 drafts, untouched). **[F]**
- **Ready to merge?** On content, yes as an evidence-and-decision PR: additive files, no protocol edits, tests green, prior evidence byte-identical. **[A]** Opening and approving a PR is a human, outward action not taken here.

## 2. North Star in one sentence

**[F]** Determine, with reproducible evidence, whether a local model's triage of test logs adds measurable value to Claude Code's development loop beyond deterministic log compression alone, and if it does not, ship the compressor with no model dependency. (`NORTHSTAR.md` "Mission"; protocol §19 "Final Decision Rule".)

## 3. User and problem the Evidence Compiler solves

**[F]** Claude Code, working on this developer's builds, receives large high-entropy test logs. The Evidence Compiler produces a bounded immutable `EvidencePacket` and a deterministic worker view so Claude gets the evidence a correct answer needs with less cloud context (§1 H1; §7). Architectural law 3: the Evidence Compiler never depends on local inference availability (§2). The local model is the optional experiment layered on top, never the product. Arms: A compressor→Claude, B raw log→Claude, C/D compressor + local model→Claude (§3, §4).

## 4. Approved development plan and phases

**[F]** Protocol v3, ratified in `9e9948b` with §6 thresholds frozen (`WORKLOG.md` "2026-08-22 — Protocol ratified"):

1. **Phase 0** target-hardware smoke test against pre-committed kill thresholds (warm ≤20 s, cold ≤60 s, validity ≥3/5) → admit both / admit one / stop and defer / diagnose output constraints (§6 decision table; §18 steps 1–6).
2. **Phase 1a** offline artifact-quality + compressor primary-evidence-recall evaluation: ≥30 holdout invocations per configuration, 0 structural failures, 0 invalid citations, ≥85 % supported claims (§12; §18 steps 1–10) → ADMIT_TO_PHASE_1B / ADMIT_NARROWLY / REVISE_* / DEFER_MODEL / KILL_LOCAL_WORKER.
3. **Phase 1b** live paired B/A/C/D evaluation in flagged sessions (§13) → KEEP / NARROW_KEEP / PREFER_14B / PREFER_30B / SHIP_COMPRESSOR_ONLY / IMPROVE_EVIDENCE_PACKET / KILL_OR_DEFER.

Gates: "No implementation beyond the required phase may proceed until the preceding phase admits it" (§ "Phase structure"); every promotion is human-approved and versioned (§17 "Never automatic"; `NORTHSTAR.md` "Off-limits").

## 5. What the branch contributes

**[F]** It completes the Phase 0 evidence chain: original FA-off run (`897b5ed`, both models 7–45× over the latency gates) → root cause (`WORKLOG.md` 2026-09-05: prefill at 1.9 tok/s with flash attention off) → FA-on re-measure (`cbbbd6f`) → controlled operational batch (`9c13ba3`) → human ruling revising DEFER to warm-session-only (`459d7b0`). It also adds the serving-layer identity instrumentation §9 lacked, without editing §9.

## 6. What Phase 0 established

- **[F] 2026-08-22:** both candidates passed structural validity (5/5) and citation integrity; both missed both latency gates by 7–45× → `DEFER_LOCAL_MODEL_PATH`, human call per §17 (`f151327`; `WORKLOG.md` "Phase 0 decision").
- **[F] 2026-09-05/06:** the latency failure was dominated by `OLLAMA_FLASH_ATTENTION` being off (server default), not by VRAM spill alone (`WORKLOG.md` 2026-09-05; `PHASE0_REPORT_FA-ON_2026-09-06.md`).
- **[F] 2026-09-06 operational batch** (`PHASE0_OPERATIONAL_REPORT_2026-09-06.md` §2): with FA on and keep-alive 30 m, `qwen2.5-coder:14b` warm median 17,977 ms / cold 23,768 ms, 5/5 valid; `qwen3-coder:30b-a3b` warm 16,369 ms / cold 25,126 ms, 5/5 valid. Both pass every §6 gate. Cold is process-cold, not disk-cold; worst single cold request 58 s. Zero flagged Windows events; no runner-crash markers.
- **[F] Decision on record:** DEFER revised to warm-session-only; local models approved for active use with FA on + 30 m keep-alive; cold start up to ~1 min not guaranteed; `qwen3.5:9b` 0/5 recorded as a benchmark-output-handling limitation (thinking field), not a model failure (`decisions/2026-09-06-defer-revision-warm-session-only.md`).

## 7. What the FA-on result changes, and what it does not

**Changes [F]:**
- The factual basis of DEFER: both frozen candidates meet the frozen §6 thresholds under a stated operating condition. The §6 row "Model meets warm and cold thresholds and structural-validity minimum → Admit the model to Phase 1a" is now satisfiable on evidence for both models.
- Serving-layer settings (FA, keep-alive, KV type, offload) are now recorded per run, out-of-band.

**Does not change [F]:**
- No admission has been made. The decision record states: "Admission to Phase 1a, candidate selection, and any §6/§9/§13 edit remain separate, versioned human decisions."
- §6 thresholds, §9 parameters, §13 discipline, the §3 candidate list, and the arm structure are unchanged.
- Phase 0 fixtures are synthetic (`WORKLOG.md` step-5 flag). A result near the gate has less safety margin than the original 7–45× miss; warm medians sit 2–4 s under the 20 s gate at ~27k prompt tokens (`PHASE0_OPERATIONAL_REPORT` §3). The amendment draft raises the same fixture-realism point **[P]**.
- It says nothing about artifact usefulness (Phase 1a) or system value (Phase 1b) (§1 "Important decomposition").
- It does not open the `qwen3.5:9b` line or KV-cache quantization; both remain proposals **[P]** in the 2026-09-01 drafts, and `WORKLOG.md` "Needs your call" 2026-09-01 and item (a) of 2026-09-05 are still unresolved.
- It authorizes no new worker, feature, or architecture change (§17 "Never automatic": worker addition, new model approval, prompt/schema/validator change).

## 8. Next 1–3 milestones, in priority order

1. **Land the evidence and decision on master.** Push the branch, open a PR scoped "Phase 0 evidence + DEFER revision record", merge. Until then master (`e68d040`) still records an unqualified DEFER. **[A]** master is the record of truth for §17 decisions.
2. **Make the §6/§17 admission decision explicitly.** One human-approved, versioned record choosing a §6 table row (admit both / admit one / stop and defer) on the 2026-09-06 evidence, naming the operating condition (warm session) and the synthetic-fixture caveat, and closing or deferring the open 2026-09-01 and 2026-09-05 "Needs your call" items. Prerequisite for any Phase 1a step (§17; `NORTHSTAR.md` "Off-limits"). **[F]**
3. **Only if admitted: Phase 1a steps 1–2** (§18): freeze the small contracts; §9 parameters are already frozen. Fold the runtime-identity amendment into §9/§14 by a dated protocol edit before Phase 1a data is collected (open item (a), `WORKLOG.md` 2026-09-05). **[A]** that FA/keep-alive should become formal configuration identity rather than stay out-of-band.

## 9. Smallest recommended next action

**Create a narrowly scoped follow-up: a PR of the existing branch, evidence and decision record only.** Not "finish the PR" (none exists), not "revise" (nothing to revise), not "stop" (the mission is live and the next gate is a decision, not more work). Acceptance criteria I would attach **[A]**: additive files only; no edits to `NORTHSTAR.md`, protocol v3, or §6/§9/§13; prior Phase 0 results byte-identical; tests green; the two 2026-09-01 drafts excluded.

Explicitly not recommended now, per your instruction and §17 **[F]**: any Phase 1a implementation, a local-worker feature, architecture change, candidate change, or further cold-start/driver/hardware work.

## Evidence index

- `NORTHSTAR.md`: Mission / What done looks like / Off-limits
- `phase1-local-intelligence-protocol-v3.md`: Status, Phase structure, §1, §2, §3, §6, §12, §17, §18, §19
- `README.md`: Status line (`e68d040` vs `459d7b0`)
- `WORKLOG.md`: Done (2026-08-22 ratification, Phase 0 steps, DEFER; 2026-09-06 entries), Roadmap, Needs your call (2026-09-01, 2026-09-05, 2026-09-06)
- `decisions/2026-09-06-defer-revision-warm-session-only.md`
- `phase0_results/PHASE0_REPORT.md`, `PHASE0_REPORT_FA-ON_2026-09-06.md`, `PHASE0_OPERATIONAL_REPORT_2026-09-06.md`
- `phase0-reconsideration.md`, `phase1-protocol-amendment.draft.md`: proposals only
- Commits `9e9948b`, `897b5ed`, `f151327`, `e68d040`, `cbbbd6f`, `b4c9f59`, `9c13ba3`, `459d7b0`
- `gh pr list` / `gh issue list` on `YourBIMpossible/local-intel`: empty; `git ls-remote --heads origin`: master only
