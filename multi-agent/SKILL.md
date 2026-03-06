---
name: multi-agent
description: Use when a task benefits from single-first escalation into Broker-only multi-agent execution (`max_depth=1`), schema-validated messages, and explicit ownership locks.
---

# Multi-Agent (Single-First)

## Path conventions

All paths in this skill are relative to the **skill root** (the directory that contains this `SKILL.md`).

In Codex, locate the skill root using the runtime skills list (it provides the absolute path to this `SKILL.md`), then open `PLAYBOOK.md` in the same directory.

## Objective

Provide a reliable, auditable single-first workflow: stay in one thread by default, escalate to brokered multi-agent execution only when the work is actually decomposable, and keep ownership plus verification explicit.

## Role terminology

Concept roles are used for protocol clarity:

- **Broker**: the main thread.
- **Runner**: command and investigation worker (`agent_type="runner"`).
- **Builder**: write-capable worker (`agent_type="builder"`).
- **Inspector**: review worker (`agent_type="inspector"`).

## When to use

- The task has evidence-backed parallelism: disjoint ownership, independent branches, or read/review work that can overlap with separate write packages.
- You need strict spawn topology guarantees and schema-validated messages once escalation to `multi` is justified.
- The Broker needs wait-any replenishment instead of a fixed linear pipeline.

## Inputs

- Task goal, scope, and constraints (including no-go areas).
- Routing decision: `single`, `single-deep`, or `multi` (single-first escalation).
- Ownership scopes for write slices (must be disjoint in-flight).
- Minimum verification evidence expected before closeout.

## Hard gates (non-negotiable)

- Short-circuit unless `route="multi"` (no spawns in `single` or `single-deep`).
- Escalate to `multi` only when the task can be split into coherent, runnable packages; uncertainty alone is not enough.
- There is no mandatory planning gate or workstream-first ordering.
- Enforce brokered spawning (`max_depth=1`): only the Broker uses collab tools (`spawn_agent`, `wait`, `send_input`, `close_agent`).
- In `multi`, Broker never writes repo content (`apply_patch` or direct edits are prohibited).
- All repo writes are delegated to `agent_type="builder"` slices.
- Enforce ownership locks for write slices (no overlapping `ownership_paths` in-flight).
- Enforce wait-any replenishment (no spawn-wave + wait-all scheduling).
- Keep workers warm and reuse via `send_input` with JSON-only `task-dispatch/1`; close only on rotation, failure recovery, or end-of-run cleanup.

## How to use

Read `PLAYBOOK.md` and follow it literally for ticket-board lifecycle, lane caps, and handoff handling.

If `route="single"` or `route="single-deep"`, stay in the main thread and do not spawn.

If `route="multi"` and the task can be decomposed into disjoint ownership packages, independent branches, or concurrent read/review plus write work:

- Open `BROKER_SPLIT.md` before scheduling the first write wave.
- Apply `WORKER_PROTOCOL.md` when drafting dispatch contracts and evaluating handoff requests.
- Use `FAILURE_MODES.md` when stalls, schema-invalid output, deadlocks, or over-splitting occur.

## Outputs

- Schema-valid worker results (`runner`, `builder`, `inspector`) using JSON-only payloads.

## Notes

- This skill uses a single-first protocol: dynamic ticket generation plus brokered handoffs only after decomposition is established.
- Council defaults are documented in [`COUNCIL.md`](COUNCIL.md) as optional bootstrap templates.
- Schemas are structural; invariants live in the playbook and e2e validator.

## Quick reference

- Playbook: `PLAYBOOK.md`
- Council protocol: `COUNCIL.md`
- Dispatch schema: `schemas/task-dispatch.schema.json` (`schema="task-dispatch/1"`, JSON-only for both `spawn_agent.message` and `send_input.message`)
- Worker result schemas:
  - `schemas/worker-result.runner.schema.json` (`schema="worker-result.runner/1"`)
  - `schemas/worker-result.builder.schema.json` (`schema="worker-result.builder/1"`)
- Inspector schema: `schemas/review-result.inspector.schema.json` (`schema="review-result.inspector/1"`)
- `ssot_id` generator: `tools/make_ssot_id.py`
- Council bootstrap helper: `tools/make_council_bootstrap.py`
- Dev-only smoke (skills repo only): `python3 dev/multi-agent/e2e/run_smoke.py`

## Common mistakes

- Non-Broker spawning (impossible under `max_depth=1`, but still a common prompt mistake).
- Escalating to `multi` just because the task is uncertain, even though the work is still one tightly coupled lane.
- Dispatch payload not being JSON-only `task-dispatch/1`.
- Worker outputs in markdown/code fences; all worker outputs and dispatches must be raw JSON-only.
- Wait-all behavior instead of wait-any replenishment.
- Returning while any child remains in-flight.
- Closing workers too early, causing avoidable cold-start latency for follow-up slices.
- Over-splitting into micro-slices where coordination dominates useful work.
