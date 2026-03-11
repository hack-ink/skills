# Multi-Agent Playbook (Two-State)

Hard constraint: runtime `max_depth = 1`.

The Broker is the scheduler. Workers are leaf executors.

## 0) Routing gate

- Always record `t_max_s` and `t_why`.
- Stay in `single` only if the task is tiny, clear, low-risk, and clearly fits the fast path.
- Route everything else to `multi`.
- Once in `multi`, keep routing and topology decisions in the Broker.

## 1) Ticket model

Every scheduled unit is a `ticket-dispatch/1`.

Required dispatch fields:

- `schema`
- `run_id`
- `ticket_id`
- `role`
- `objective`
- `acceptance`
- `timebox_minutes`

Optional dispatch fields:

- `constraints`
- `context`
- `depends_on`
- `authorized_skills`
- `write_scope`
- `review_mode`

Role rules:

- `write_scope` is required only for Builder tickets.
- `review_mode` is allowed only for Inspector tickets.
- Runner and Inspector tickets carry no write lock.
- `authorized_skills` is only relevant when the manual child skill policy marks a known local skill `dispatch-authorized`; omit it or send `[]` when none are authorized.
- If the manual policy omits a skill, the child may use it without listing it in `authorized_skills`.

Dispatch example:

```json
{
  "schema": "ticket-dispatch/1",
  "run_id": "runtime-reset",
  "ticket_id": "runner-inventory",
  "role": "runner",
  "objective": "Inspect the current protocol surface and list stale helper entrypoints.",
  "acceptance": [
    "Identify every installable doc, schema, and helper file that still depends on the legacy wire contract."
  ],
  "timebox_minutes": 8,
  "constraints": [
    "Read-only."
  ],
  "context": [
    "The new design keeps only ticket-dispatch/1 and ticket-result/1."
  ],
  "depends_on": []
}
```

## 2) Result model

Every worker completion is a `ticket-result/1`.

Required result fields:

- `schema`
- `run_id`
- `ticket_id`
- `role`
- `status`
- `summary`

Optional result fields:

- `findings`
- `changed_paths`
- `verification`
- `unblock`
- `verdict`

Result rules:

- `status` is only `done` or `blocked`.
- Builder `done` results must include `changed_paths`.
- Inspector results must include `verdict`.
- Any `blocked` result must include `unblock`.

Builder result example:

```json
{
  "schema": "ticket-result/1",
  "run_id": "runtime-reset",
  "ticket_id": "builder-schemas",
  "role": "builder",
  "status": "done",
  "summary": "Replaced the legacy schema files with the new two-file contract.",
  "changed_paths": [
    "multi-agent/schemas/ticket-dispatch.schema.json",
    "multi-agent/schemas/ticket-result.schema.json"
  ],
  "verification": [
    {
      "cmd": "python3 dev/multi-agent/e2e/validate_payloads.py",
      "exit_code": 0
    }
  ]
}
```

## 3) Broker-local state

The Broker, not the worker payload, owns:

- parent-task and board bookkeeping
- follow-up ticket creation
- write-scope lock management
- review-gate ordering
- salvage and adoption decisions
- interrupt and close policy

Workers never emit handoff tickets, partial checkpoints, or nested recovery trees.

## 4) Scheduling loop

- Build a runnable set from pending tickets whose dependencies are satisfied.
- Respect lane caps by role.
- Enforce write locks with `write_scope`; never run overlapping Builder tickets at the same time.
- Prefer reusing warm workers with `send_input`.
- Use wait-any replenishment. Do not use wait-all waves.
- Keep polling while tickets remain runnable or in flight.

## 5) Recovery

If a worker returns valid JSON with `status="blocked"`:

- record the summary
- use `unblock` to decide the next Broker action
- create the next ticket or mark the parent task blocked

If a worker returns invalid output or no valid output after one bounded interrupt:

- close the worker
- inspect local evidence directly if the worker may have changed files
- decide locally whether to salvage or redispatch

The protocol does not rely on a worker-provided checkpoint payload.

## 6) Inspector policy

- Use Inspector for explicit review gates and final closeout checks.
- Keep review ordering in the Broker:
  - `spec_compliance`
  - `code_quality`
  - `final_closeout`
- If Inspector returns `verdict="block"` or `verdict="needs_evidence"`, the Broker must route follow-up work before closeout.

## 7) Closeout

Close the run only after:

- no runnable or inflight tickets remain
- required Inspector gates have passed
- local verification evidence is complete
- no stalled child remains an implicit dependency
