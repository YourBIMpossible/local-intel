# North Star (draft)

**Mission:** Run the Phase 1 Local Intelligence Experiment
(`phase1-local-intelligence-protocol-v3.md`) to determine, with reproducible
evidence, whether local model triage of test logs (via `local-intel` +
Ollama) adds measurable system value to Claude Code's development loop
beyond deterministic log compression alone.

**What done looks like:** Phase 0 smoke test executed against the
pre-committed §6 kill thresholds, producing one of the pre-committed
decisions (admit to Phase 1a / admit one model / stop and defer). If
admitted, Phase 1a offline artifact-quality evaluation and, if that passes,
Phase 1b live paired evaluation, each ending in their protocol's own
pre-committed decision (§13: KEEP / NARROW_KEEP / PREFER_14B / PREFER_30B /
SHIP_COMPRESSOR_ONLY / IMPROVE_EVIDENCE_PACKET / KILL_OR_DEFER).

**Off-limits:** No phase may be skipped or reordered (§ "Phase structure").
No implementation beyond the current admitted phase. No autonomous
promotion between states (§17) — every state transition beyond automatic
pause requires a human-approved, versioned decision. No editing the
pre-committed §6 kill thresholds, §9 generation parameters, or §13 pairing
discipline outside of a dated, versioned protocol edit made *before* the
phase they gate.
