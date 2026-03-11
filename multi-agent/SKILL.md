---
name: multi-agent
description: Use when one task or one PR-sized change stream benefits from two-state routing into Broker-only multi-agent execution (`single` or `multi`), slim JSON tickets, and broker-owned scheduling state.
---

# Multi-Agent (Two-State)

## Path conventions

All paths in this skill are relative to the skill root, the directory that contains this `SKILL.md`.

## Objective

Provide a reliable two-state workflow for one task or one PR-sized change stream:

- stay in one thread only for tiny, clear, low-risk work
- use brokered multi-agent execution for everything else in that same stream
- keep worker IO machine-readable with a slim JSON contract
- keep orchestration state in the Broker instead of the wire payload

## Role terminology

- Broker: the main thread
- Runner: command and investigation worker (`role="runner"`)
- Builder: write-capable worker (`role="builder"`)
- Inspector: review worker (`role="inspector"`)

## When to use

- The task is not tiny, clear, and low-risk enough to stay in `single`.
- The work belongs to one coherent task, incident, or PR-sized change stream.
- The Broker needs wait-any scheduling, write-scope locks, or explicit review gates.
- The parent thread wants strict JSON-only dispatch and result payloads without worker-managed follow-up tickets.

Do not use this skill to coordinate unrelated branches or delivery lanes. Split those into separate worktrees first.

## Hard gates

- Short-circuit unless `route="multi"`.
- `single` is reserved for tiny, clear, low-risk tasks that clearly fit the fast path.
- Only the Broker spawns children (`max_depth=1`).
- In `multi`, Broker never writes repo content.
- All repo writes are delegated to `role="builder"` tickets.
- Workers never reroute, never spawn, and never emit orchestration topology.
- JSON-only payloads are mandatory for both dispatch and result messages.

## How to use

Read the following files and follow them literally:

- `PLAYBOOK.md` for Broker scheduling, board state, and recovery policy
- `WORKER_PROTOCOL.md` for worker behavior and JSON payload quality bar

## Outputs

- Broker dispatches use `ticket-dispatch/1`.
- Worker results use `ticket-result/1`.
- Broker uses `ticket-dispatch/1.authorized_skills` only when the manual child skill policy marks a known local skill `dispatch-authorized`.

## Notes

- The Broker owns follow-up ticket creation, parent-task bookkeeping, salvage decisions, and review-gate ordering.
- Workers report only what they did, what changed, what they verified, and what is needed to unblock.
- The protocol intentionally omits worker-generated handoffs, partial checkpoints, and nested recovery payloads.
- If the manual child policy is empty, child skill use is default-allow and `authorized_skills` is usually unnecessary.
- If a child needs a known local skill that the manual child policy marks `dispatch-authorized`, the Broker must name it in `authorized_skills`.
- The child skill policy is user-managed repo state, not broker-managed runtime state.

## Quick reference

- Playbook: `PLAYBOOK.md`
- Worker protocol: `WORKER_PROTOCOL.md`
- Dispatch schema: `schemas/ticket-dispatch.schema.json`
- Result schema: `schemas/ticket-result.schema.json`
- Dev smoke: `python3 dev/multi-agent/e2e/run_smoke.py`

## Common mistakes

- Keeping a non-tiny or uncertain task in `single`.
- Letting the Broker edit files during `multi`.
- Expecting workers to return follow-up tickets or rich checkpoint trees.
- Reusing legacy fields such as `ssot_id`, `task_id`, or `work_package_id`.
- Wrapping payloads in markdown fences or surrounding prose.
