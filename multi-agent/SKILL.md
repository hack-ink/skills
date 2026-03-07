---
name: multi-agent
description: Use when a task benefits from two-state routing into Broker-only multi-agent execution (`single` or `multi`), schema-validated messages, and explicit ownership locks.
---

# Multi-Agent (Two-State)

## Path conventions

All paths in this skill are relative to the **skill root** (the directory that contains this `SKILL.md`).

In Codex, locate the skill root using the runtime skills list (it provides the absolute path to this `SKILL.md`), then open `PLAYBOOK.md` in the same directory.

## Objective

Provide a reliable, auditable two-state workflow: stay in one thread only for tiny, clear, low-risk tasks, and use brokered multi-agent execution for everything else. In `multi`, scout-first execution is valid until the Broker has enough evidence to launch owned work packages.

## Role terminology

Concept roles are used for protocol clarity:

- **Broker**: the main thread.
- **Runner**: command and investigation worker (`agent_type="runner"`).
- **Builder**: write-capable worker (`agent_type="builder"`).
- **Inspector**: review worker (`agent_type="inspector"`).

## When to use

- The task is not tiny, clear, and low-risk enough to stay in `single`, even if useful parallelism is not proven yet.
- You need strict spawn topology guarantees and schema-validated messages once `route="multi"` is chosen.
- The Broker needs wait-any replenishment, ownership locks, or scout-first boundary discovery.

## Inputs

- Task goal, scope, and constraints (including no-go areas).
- Routing decision: `single` or `multi`.
- `t_max_s` and `t_why`.
- Whether the task is tiny, clear, and low-risk enough to stay in `single`.
- Ownership scopes for write slices (must be disjoint in-flight).
- Minimum verification evidence expected before closeout.

## Hard gates (non-negotiable)

- Short-circuit unless `route="multi"` (no spawns in `single`).
- `single` is reserved for tiny, clear, low-risk tasks that clearly fit the fast path.
- Route everything else to `multi`: long tasks, uncertain tasks, risky tasks, or work that needs scout-first boundary discovery.
- `multi` may begin with a single scout lane; do not wait for proven decomposability before escalating.
- There is no mandatory planning gate or workstream-first ordering.
- Enforce brokered spawning (`max_depth=1`): only the Broker uses collab tools (`spawn_agent`, `wait`, `send_input`, `close_agent`).
- In `multi`, Broker never writes repo content (`apply_patch` or direct edits are prohibited).
- All repo writes are delegated to `agent_type="builder"` slices.
- Enforce ownership locks for write slices (no overlapping `ownership_paths` in-flight).
- Enforce wait-any replenishment (no spawn-wave + wait-all scheduling).
- Keep workers warm and reuse via `send_input` with JSON-only `task-dispatch/1`; close only on rotation, failure recovery, or end-of-run cleanup.

## How to use

Read `PLAYBOOK.md` and follow it literally for ticket-board lifecycle, lane caps, and handoff handling.

If `route="single"`, stay in the main thread and do not spawn.

If `route="multi"`, start with either direct runnable tickets or a low-fanout scout wave:

- Open `COUNCIL.md` when boundary mapping or risk checks would help before write tickets.
- Open `BROKER_SPLIT.md` before scheduling the first write wave.
- Apply `WORKER_PROTOCOL.md` when drafting dispatch contracts and evaluating handoff requests.
- Use `FAILURE_MODES.md` when stalls, schema-invalid output, deadlocks, or over-splitting occur.

## Outputs

- Schema-valid worker results (`runner`, `builder`, `inspector`) using JSON-only payloads.

## Notes

- This skill uses a two-state protocol: `single` for the tiny fast path, `multi` for every other task shape.
- In `multi`, scout-first runs may stay on one Builder work package until the Broker has enough evidence to split safely.
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
- Keeping a non-tiny or uncertain task in `single` just because useful parallelism is not proven yet.
- Assuming `multi` must immediately fan out into multiple active lanes.
- Dispatch payload not being JSON-only `task-dispatch/1`.
- Worker outputs in markdown/code fences; all worker outputs and dispatches must be raw JSON-only.
- Wait-all behavior instead of wait-any replenishment.
- Returning while any child remains in-flight.
- Closing workers too early, causing avoidable cold-start latency for follow-up slices.
- Over-splitting into micro-slices where coordination dominates useful work.
