---
name: multi-agent
description: Use when a task benefits from parallel workers (Operator/Coder/Supervisor) with Director-only spawning (max_depth=1) and schema-validated inputs/outputs, plus optional Auditor review.
---

# Multi-Agent (vNext)

## Path conventions

All paths in this skill are relative to the **skill root** (the directory that contains this `SKILL.md`).

In Codex, locate the skill root using the runtime’s skills list (it provides the absolute path to this `SKILL.md`), then open `PLAYBOOK.md` in the same directory.

## Objective

Provide a reliable, auditable workflow for multi-agent execution: explicit routing, explicit ownership, evidence-backed verification, and optional Auditor review.

## When to use

- The task is non-trivial and benefits from parallelizable slices (especially mixed read/write work).
- You need strict spawn topology guarantees (no same-level spawn) and schema-validated messages.
- The Director is uncertain and wants fast parallel probes with evidence.

## Inputs

- Task goal, scope, constraints (including no-go areas).
- Routing decision: `single` or `multi` (90s rule).
- Slice ownership scopes (write slices must be disjoint).
- Minimum acceptable verification evidence.

## Hard gates (non-negotiable)

- Short-circuit unless `route="multi"` (no spawns in `single`).
- Director must not write repo content in `multi` (no `apply_patch`, no file edits). All repo writes — including “integration/merge/conflict resolution” — must be delegated to a `coder_*` slice or the Supervisor Integrate slice.
- Enforce brokered spawning (requires runtime `max_depth=1`):
  - Director is the only role that uses collab tools (`spawn_agent`, `wait`, `send_input`, `close_agent`).
  - Director spawns depth=1 children only: `operator`, `coder_spark` (fallback `coder_codex`), optional `auditor`, and `agent_type="supervisor"`.
  - No same-level or cross-level spawn is possible under this topology.
- Enforce the repo-write gate: only `coder_*` and Supervisor Integrate (`agent_type="supervisor"`) implement repo changes.
- Enforce ownership locks for write slices (no overlapping `ownership_paths` in-flight).
- Close completed children to avoid thread starvation.

## How to use

Read `PLAYBOOK.md` and follow it literally.

## Outputs

- Schema-valid worker results (`operator`, `coder`, `supervisor`) and optional Auditor review.

## Notes

- This skill intentionally removes the Orchestrator role. The Director plans + schedules directly.
- Schemas are structural; invariants live in the playbook.

## Quick reference

- Playbook: `PLAYBOOK.md`
- Dispatch schema: `schemas/task-dispatch.schema.json` (`schema="task-dispatch/1"`, JSON-only `spawn_agent.message`)
- Worker result schemas:
  - `schemas/worker-result.operator.schema.json` (`schema="worker-result.operator/1"`)
  - `schemas/worker-result.coder.schema.json` (`schema="worker-result.coder/1"`)
- `supervisor` schema:
  - `schemas/worker-result.supervisor.schema.json` (`schema="worker-result.supervisor/1"`)
- Auditor schema: `schemas/review-result.auditor.schema.json` (`schema="review-result.auditor/1"`)
- `ssot_id` generator: `tools/make_ssot_id.py`
- Dev-only smoke (skills repo only): `python3 dev/multi-agent/e2e/run_smoke.py`

## Common mistakes

- Non-Director spawning (impossible under `max_depth=1`, but still a common prompt mistake).
- Dispatch message not being JSON-only `task-dispatch/1`.
- Worker outputs in markdown/code fences are invalid; all worker results and dispatches must be raw JSON-only (no surrounding ``` fences).
- “Wait-all” behavior: spawn a wave then idle-wait instead of wait-any replenishment.
- “Spawn-then-stop” behavior: returning/exiting while any child is still in-flight (must keep polling `functions.wait` until children are finished + closed, or explicitly mark blocked).
- Forgetting to `close_agent` for completed children.
- Over-splitting (coordination overhead > work).
