# AGENTS.md — codex-multi-agent-protocol

This directory packages the multi-agent protocol skill (schemas, fixtures, and operational workflow rules).

## Non-negotiable workflow rules

- Spawn topology (depth=2):
  - Director (main) spawns `auditor` and `orchestrator` as peers.
  - Orchestrator spawns leaf agents (`operator`, `coder_*`, optional `awaiter` for waiting only).
  - Auditor spawns no agents (gatekeeping only).
- Orchestrator deliverables must be reviewed by Auditor before the Director presents a final conclusion.
- Auditor contract:
  - Timebox: <= 120 seconds.
  - Always set `verdict = PASS | BLOCK | NEEDS_EVIDENCE`.
  - If `NEEDS_EVIDENCE`, include `required_evidence` (minimum needed to proceed).
- Evidence-first:
  - Coder returns `verification_steps`.
  - Operator returns `actions` with evidence.
  - Orchestrator returns integration evidence (for write workflows) and an Auditor-ready summary.
- Close completed leaf agents to avoid thread starvation.

## References

- Operational playbook: `references/WORKFLOWS.md`
- Role templates/checklists: `references/ROLE_TEMPLATES.md`
- Testing and fixtures: `references/PROTOCOL_TESTING.md`, `references/e2e/`

## Research slices

- When the task is explicitly research/comparison/design exploration, use Operator fanout and produce an evidence map with 3+ independent sources when feasible (do not include sensitive identifiers in queries).
