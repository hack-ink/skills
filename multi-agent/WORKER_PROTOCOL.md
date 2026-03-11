# Worker Protocol (Two-State Multi)

This document defines how depth-1 workers behave once the Broker has already escalated into `route="multi"`.

Hard constraints:

- Workers never spawn.
- Runner and Inspector never write repo content.
- Workers never reroute.
- Worker outputs are raw JSON only.
- Worker outputs must validate against `ticket-result/1`.

## Shared worker defaults

- Treat the Broker dispatch as the complete task contract.
- Use the provided `context` instead of reconstructing intent from broad rereads.
- Treat `authorized_skills` as relevant only when `child-skill-policy.toml` explicitly marks a known local skill `dispatch-authorized`.
- If the manual policy omits a skill, treat it as allowed by default.
- Never treat `authorized_skills` as permission to bypass a manual `main-thread-only` restriction.
- Stay inside the assigned scope.
- Report only the completed work, concrete findings, changed paths, verification commands, and unblock conditions.
- Do not generate follow-up tickets. The Broker owns decomposition.
- Do not return partial progress payloads. Use `status="blocked"` if the ticket cannot finish cleanly.

## Runner checklist

- Gather evidence, boundaries, risks, and file-level observations.
- Prefer concise `findings`.
- Use `status="blocked"` only when the Broker must choose the next action or provide missing context.

Runner example:

```json
{
  "schema": "ticket-result/1",
  "run_id": "runtime-reset",
  "ticket_id": "runner-inventory",
  "role": "runner",
  "status": "done",
  "summary": "Found all installable and dev fixtures that still depended on the legacy wire shape.",
  "findings": [
    "The installable skill still referenced the old schema file names.",
    "The dev harness still expected worker-generated follow-up tickets."
  ]
}
```

## Builder checklist

- Stay strictly inside `write_scope`.
- Return `changed_paths` when `status="done"`.
- Include any verification you already ran.
- If the ticket cannot finish cleanly, return `status="blocked"` with the narrowest possible `unblock` list.
- If local files may already have changed before the block, mention that in the summary or findings; the Broker will inspect the workspace directly.

Builder blocked example:

```json
{
  "schema": "ticket-result/1",
  "run_id": "runtime-reset",
  "ticket_id": "builder-salvage",
  "role": "builder",
  "status": "blocked",
  "summary": "The worker timed out after writing part of the owned scope; the Broker must inspect local diffs before deciding whether to salvage or reroute.",
  "changed_paths": [
    "dev/multi-agent/backtests/broker_sim.py"
  ],
  "unblock": [
    "Close the timed-out worker.",
    "Inspect the owned diff locally.",
    "Decide whether to adopt the landed edits or dispatch a narrow follow-up."
  ]
}
```

## Inspector checklist

- Review only the requested gate.
- Keep findings short and decisive.
- Always return a `verdict`.

Inspector example:

```json
{
  "schema": "ticket-result/1",
  "run_id": "runtime-reset",
  "ticket_id": "inspector-closeout",
  "role": "inspector",
  "status": "done",
  "summary": "The rewritten protocol is coherent and no legacy helper entrypoints remain.",
  "verdict": "pass",
  "findings": [
    "The installable docs and dev harness both point at the same two-schema contract."
  ]
}
```
