---
name: plan-writing
description: Use when the user asks for a plan, when a multi-step or risky task should be decomposed before implementation, or when the runtime is in Plan mode. Produces or revises the persisted machine-first `plan/1` contract at `docs/plans/YYYY-MM-DD_<feature-name>.md`, owning strategy, task graph, defaults, and replanning policy before implementation begins.
---

# Plan Writing

## Scope

- This skill is the producer stage of the shared `plan/1` contract.
- It owns the stable execution intent in `spec`.
- It may initialize or reset the mutable runtime `state`.
- It is the only skill allowed to change strategy, task graph, defaults, or replanning policy.

Typical triggers:

- The user explicitly asks for a plan, design, or implementation breakdown
- The task is large enough that coding immediately would be sloppy or risky
- The runtime is already in a dedicated Plan mode
- The next step should be a persisted execution contract before work starts

## Authoritative artifact

- Stay in planning scope. Do not start implementation unless the user explicitly asks to execute now.
- Ground the plan in current repo evidence. Read enough code, docs, and instructions to avoid placeholder guidance.
- Persist the plan under `docs/plans/YYYY-MM-DD_<feature-name>.md`.
- The first top-level artifact in that file must be a fenced JSON block containing the authoritative `plan/1` contract.
- Anything below that first fenced block is optional context only. It is non-authoritative and must never override the contract.
- Do not rely on chat summaries, `<proposed_plan>` output, or prior conversational context as execution authority once the saved file exists.

## Contract shape

The `plan/1` block must decode to this top-level shape:

```json
{
  "spec": {
    "schema": "plan/1",
    "plan_id": "example-plan",
    "goal": "Non-empty string",
    "success_criteria": ["Non-empty strings"],
    "constraints": ["Optional non-empty strings"],
    "defaults": {},
    "tasks": [
      {
        "id": "task-1",
        "title": "Non-empty string",
        "status": "pending|in_progress|blocked|done|cancelled",
        "objective": "Non-empty string",
        "inputs": ["Optional non-empty strings"],
        "outputs": ["Optional non-empty strings"],
        "verification": ["Non-empty strings"],
        "depends_on": ["Existing task ids"]
      }
    ],
    "replan_policy": {
      "owner": "plan-writing",
      "triggers": ["Non-empty strings"]
    }
  },
  "state": {
    "phase": "planning|ready|executing|blocked|needs_replan|done",
    "current_task_id": null,
    "next_task_id": "task-1",
    "blockers": [],
    "evidence": [],
    "last_updated": "2026-03-13T00:00:00Z",
    "replan_reason": null,
    "context_snapshot": {}
  }
}
```

## Producer rules

- `spec` is stable intent. `plan-execution` must not rewrite it.
- `state` is mutable runtime state. `plan-writing` may initialize it for a new plan or reset it after replanning.
- For new plans:
  - create the first fenced `plan/1` block
  - populate `spec`
  - set `state.phase = "ready"`
  - set `state.next_task_id` deterministically
  - leave `state.evidence = []`
- For replans after drift or blockage:
  - load the existing saved file
  - preserve existing `state.evidence`
  - rewrite only the parts of `spec` that truly changed
  - clear `needs_replan` by producing a consistent `ready` state
- Treat missing saved files and legacy prose-only plans as authoring work, not as execution authority.

## Determinism rules

- Use exactly one active task at a time. The contract must never contain multiple `in_progress` tasks.
- Express task order only through `depends_on`. Do not rely on prose ordering.
- In `ready`, `state.next_task_id` must point to an executable pending task whose dependencies are already satisfied.
- Treat `state.current_task_id`, `state.next_task_id`, and task statuses as machine-facing runtime signals, not as explanatory prose.
- Do not leave contradictory states in the file. If the plan is mid-rewrite and not yet coherent, keep editing until it validates.

## Planning workflow

1. Read the request, issue, spec, or surrounding instructions.
2. Inspect enough repository context to fill `goal`, `success_criteria`, `constraints`, `defaults`, `tasks`, and `replan_policy` without placeholders.
3. Build a task graph with stable ids and explicit `depends_on`.
4. Choose one deterministic entrypoint task and set `state.next_task_id` to that id.
   - The entrypoint task must already be executable from the task graph, not merely pending.
5. Initialize `state` so the contract is valid and ready for execution.
6. Save the file with the fenced `plan/1` block first.
7. Normalize and validate the result before reporting it.

## Helper commands

Set the skill root from the runtime skill list before running helpers:

- `PLAN_WRITING_HOME=<skill root containing this SKILL.md>`
- Create a new saved contract from raw JSON:
  - `printf '%s' "$PLAN_CONTRACT" | python3 "$PLAN_WRITING_HOME/scripts/format_plan_contract.py" > docs/plans/YYYY-MM-DD_<feature-name>.md`
- Normalize a raw or existing contract into canonical fenced markdown on stdout:
  - `python3 "$PLAN_WRITING_HOME/scripts/format_plan_contract.py" --path docs/plans/YYYY-MM-DD_<feature-name>.md`
- Overwrite an existing saved file with the normalized form:
  - `tmpfile="$(mktemp)" && python3 "$PLAN_WRITING_HOME/scripts/format_plan_contract.py" --path docs/plans/YYYY-MM-DD_<feature-name>.md > "$tmpfile" && mv "$tmpfile" docs/plans/YYYY-MM-DD_<feature-name>.md`
- Validate a saved plan file:
  - `python3 "$PLAN_WRITING_HOME/scripts/validate_plan_contract.py" --path docs/plans/YYYY-MM-DD_<feature-name>.md`
- Validate raw JSON before saving:
  - `printf '%s' "$PLAN_CONTRACT" | python3 "$PLAN_WRITING_HOME/scripts/validate_plan_contract.py"`

## Red flags

- Treating prose below the fence as authoritative
- Leaving strategy decisions in chat instead of in `spec`
- Creating a saved plan file without a valid fenced `plan/1` block
- Replanning by discarding prior `state.evidence`
- Handing execution a contract that still needs human interpretation
