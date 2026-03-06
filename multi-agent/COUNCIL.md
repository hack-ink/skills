# Multi-Agent Council (Optional Multi Bootstrap)

When `route="multi"`, Council is an optional bootstrap pattern that improves split quality before the main write wave. It is not a mandatory gate.

## 1) Bootstrap wave (read/review only)

Default bootstrap composition:

- `1 x runner` (`agent_type="runner"`, `slice_kind="work"`) to map boundaries and dependencies.
- `1 x inspector` (`agent_type="inspector"`, `slice_kind="review"`) to run pre-mortem risk checks.

No dedicated planning slice is required for Council bootstrap.

Expected outputs:

- dependency and ownership boundary recommendations
- lock-collision risks and mitigation notes
- candidate ticket suggestions for Builder/Runner phases

## 2) Merge behavior for council findings

Broker handles council outputs as inputs, not mandates:

- accept compatible recommendations directly into pending board
- reject conflicting recommendations with explicit rationale
- request one reduced re-evaluation only if conflicts block safe scheduling

Council output should reduce ambiguity, not introduce a new linear planning bottleneck.

## 3) Window alignment

Council tickets consume only read/review lanes:

- runner tickets consume `window_runner`
- inspector tickets consume `window_inspector`
- no council ticket consumes `window_builder`

This keeps bootstrap parallel with independent read tickets and avoids starving write throughput.

## 4) Templates

Bootstrap runner template:

```json
{
  "schema": "task-dispatch/1",
  "ssot_id": "scenario-hash-5277daf391c2",
  "task_id": "example-task",
  "slice_id": "council--runner-boundary-map",
  "agent_type": "runner",
  "slice_kind": "work",
  "timebox_minutes": 6,
  "allowed_paths": [],
  "ownership_paths": [],
  "dependencies": [],
  "task_contract": {
    "goal": "Map dependency graph and write ownership boundaries for parallel scheduling.",
    "acceptance": [
      "Boundary map is complete",
      "Collision risks are explicit"
    ],
    "constraints": [
      "Read-only investigation",
      "No repo writes"
    ],
    "no_touch": []
  },
  "evidence_requirements": [
    "commands",
    "files_read"
  ]
}
```

Bootstrap inspector template:

```json
{
  "schema": "task-dispatch/1",
  "ssot_id": "scenario-hash-5277daf391c2",
  "task_id": "example-task",
  "slice_id": "council--inspector-risk-check",
  "agent_type": "inspector",
  "slice_kind": "review",
  "timebox_minutes": 8,
  "allowed_paths": [],
  "ownership_paths": [],
  "dependencies": [],
  "task_contract": {
    "goal": "Identify safety and sequencing risks before write tickets are scheduled.",
    "acceptance": [
      "High-risk collisions are identified",
      "Required evidence gates are listed"
    ],
    "constraints": [
      "Review-only output",
      "No repo writes"
    ],
    "no_touch": []
  },
  "evidence_requirements": [
    "review_notes"
  ]
}
```

## 5) Governance reminders

- Council is optional; skip it for tiny, clear tasks.
- All dispatches must validate against `schemas/task-dispatch.schema.json`.
- Keep Builder write ownership disjoint before dispatching parallel write tickets.
- For quick bootstrap skeleton generation in this workspace, use:

```bash
python3 multi-agent/tools/make_council_bootstrap.py <scenario> --task-id <task-id> --format array
```
