---
name: plan-writing
description: Use when the user asks for a plan, when a multi-step or risky task should be decomposed before implementation, or when the runtime is in Plan mode. Produces or revises the persisted machine-first `plan/1` contract at `docs/plans/YYYY-MM-DD_<feature-slug>.json`, where the date is followed by one underscore and the feature slug itself is kebab-case, owning strategy, task graph, defaults, and replanning policy before implementation begins.
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
- Persist the plan under `docs/plans/YYYY-MM-DD_<feature-slug>.json`.
- Use exactly one underscore between the date and the feature slug.
- Write the feature slug in kebab-case, for example `docs/plans/2026-03-20_plan-slug-guidance.json`.
- The saved file itself is the authoritative `plan/1` JSON contract.
- Do not wrap the contract in markdown fences or append prose to the saved artifact.
- Do not rely on chat summaries, `<proposed_plan>` output, or prior conversational context as execution authority once the saved file exists.

## Contract shape

The saved `plan/1` JSON must decode to this top-level shape:

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
  - create the saved `plan/1` JSON artifact
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
- Treat `state.phase = "done"` as plan-local completion only. It means this saved plan's task graph is terminal; it does not by itself certify downstream review, merge, `delivery-closeout`, or workspace cleanup unless those lifecycle stages are explicit tasks in the same saved plan.

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
6. Save the file as raw `plan/1` JSON.
7. Normalize and validate the result before reporting it.

## Helper commands

Set the skill root from the runtime skill list before running helpers:

- `PLAN_WRITING_HOME=<skill root containing this SKILL.md>`
- Create a new saved contract from raw JSON:
  - `printf '%s' "$PLAN_CONTRACT" | python3 "$PLAN_WRITING_HOME/scripts/format_plan_contract.py" > docs/plans/YYYY-MM-DD_<feature-slug>.json`
- Normalize a raw or existing contract into canonical JSON on stdout:
  - `python3 "$PLAN_WRITING_HOME/scripts/format_plan_contract.py" --path docs/plans/YYYY-MM-DD_<feature-slug>.json`
- Overwrite an existing saved file with the normalized form:
  - `tmpfile="$(mktemp)" && python3 "$PLAN_WRITING_HOME/scripts/format_plan_contract.py" --path docs/plans/YYYY-MM-DD_<feature-slug>.json > "$tmpfile" && mv "$tmpfile" docs/plans/YYYY-MM-DD_<feature-slug>.json`
- Validate a saved plan file:
  - `python3 "$PLAN_WRITING_HOME/scripts/validate_plan_contract.py" --path docs/plans/YYYY-MM-DD_<feature-slug>.json`
- Validate raw JSON before saving:
  - `printf '%s' "$PLAN_CONTRACT" | python3 "$PLAN_WRITING_HOME/scripts/validate_plan_contract.py"`

## Red flags

- Treating markdown wrappers or prose as part of the saved authority
- Leaving strategy decisions in chat instead of in `spec`
- Creating a saved plan file that is not raw JSON
- Replanning by discarding prior `state.evidence`
- Handing execution a contract that still needs human interpretation
