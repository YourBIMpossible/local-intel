# local-intel

Repo: https://github.com/YourBIMpossible/local-intel

Phase 1 Local Intelligence Experiment: does local model triage of test logs
(via `local-intel` + Ollama) add measurable system value to Claude Code's
development loop beyond deterministic log compression alone?

- Mission and constraints: [NORTHSTAR.md](NORTHSTAR.md)
- Governing protocol: [phase1-local-intelligence-protocol-v3.md](phase1-local-intelligence-protocol-v3.md)
- Running record of work and decisions: [WORKLOG.md](WORKLOG.md)
- Phase 0 results and report: [phase0_results/](phase0_results/)

**Status:** Phase 0 complete — `DEFER_LOCAL_MODEL_PATH`, revised 2026-09-06 to warm-session-only (local models approved for active use with flash attention on; 30 m is the server keep-alive policy, the batch itself ran with 10 m request keep_alive; cold start not guaranteed). See `decisions/2026-09-06-defer-revision-warm-session-only.md` and `WORKLOG.md`.
