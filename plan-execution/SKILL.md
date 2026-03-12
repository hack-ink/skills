---
name: plan-execution
description: Use when the user wants to execute an existing implementation plan, continue from `docs/plans/*`, implement a saved plan in a separate session, or resume work after leaving Plan mode. Consumes an existing persisted `plan/1` contract, advances only runtime state, and blocks on missing or invalid saved authority instead of inferring execution intent from chat.
---

# Plan Execution

## Scope

- This skill is the consumer stage of the shared `plan/1` contract.
- It consumes a saved file under `docs/plans/YYYY-MM-DD_<feature-name>.md`.
- It owns only runtime state transitions.
- It must not repair or rewrite strategy itself.

Typical triggers:

- The user says "execute this plan" or links a plan doc
- Work should continue from `docs/plans/YYYY-MM-DD_<feature-name>.md`
- A separate session is asked to implement a saved plan
- A previously blocked contract now needs to resume from saved state

## Hard gates

- Do not infer execution authority from chat, branch names, or earlier conversational plans.
- If there is no saved file, stop and route back to `plan-writing`.
- If the saved file does not start with a valid fenced `plan/1` block, stop and report the migration error.
- If the contract is contradictory, stale, or invalid, stop and route back to `plan-writing`.
- Before any commit or push, follow the local commit/push gate.

## Consumer ownership

`plan-execution` may update only these runtime-owned fields:

- task `status` values
- `phase`
- `current_task_id`
- `next_task_id`
- `blockers`
- `evidence`
- `last_updated`
- `replan_reason`
- `context_snapshot`

It must not mutate:

- `spec.goal`
- `spec.success_criteria`
- `spec.constraints`
- `spec.defaults`
- `spec.tasks` topology or dependency graph
- `spec.replan_policy`

## Execution workflow

1. Load the saved contract and validate it before doing any implementation work.
2. Treat the normalized `plan/1` payload as the only source of truth for goal, sequencing, and next task.
3. Identify the next executable task from `state.phase`, `state.current_task_id`, `state.next_task_id`, and task statuses.
   - Treat `current_task_id` or `next_task_id` as actionable only when their dependencies are already satisfied by the task graph.
4. Re-read only the files and verification commands needed for that task.
5. Execute one coherent task or tightly related batch.
6. Update only `state` fields plus the affected task statuses in the saved file.
7. Re-read the saved file through the contract reader before reporting progress.

## Allowed state transitions

- `ready -> executing`
- `executing -> blocked`
- `executing -> done`
- `blocked -> needs_replan`

If execution needs a strategy change, stop after recording the blocker or replan reason. Do not silently rewrite `spec`.

## Blocking rules

- No saved file: block and route to `plan-writing`.
- Saved file with no fenced `plan/1` block: block with an explicit migration error.
- Legacy prose-only plan: block with an explicit migration error.
- Contradictory ids, invalid phase/task combinations, or other schema failures: block and route to `plan-writing`.
- “Use the plan we just discussed” with no materialized saved file: block and route to `plan-writing`.

## Helper command

Set the skill root from the runtime skill list before running the reader:

- `PLAN_EXECUTION_HOME=<skill root containing this SKILL.md>`
- `python3 "$PLAN_EXECUTION_HOME/scripts/read_plan_contract.py" --path docs/plans/YYYY-MM-DD_<feature-name>.md`

The reader validates the saved file, normalizes the contract, and returns machine-readable metadata plus the normalized contract payload.

## Red flags

- Executing from chat memory instead of the saved file
- Editing `spec` to “repair” a broken plan
- Continuing after the reader reports a migration or validation failure
- Leaving multiple active tasks in the contract
- Reporting progress without re-reading the updated saved file through the reader
