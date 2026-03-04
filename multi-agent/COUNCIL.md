# Multi-Agent Council (Default Protocol)

When `route="multi"`, the skill uses a **Council-by-default** planning pattern: one parallel bootstrap wave to reduce linear setup and lock in safe split quality before work starts.

## 1) Council bootstrap wave

The council wave is a read-focused plan set that should be dispatched before any write worker by default:

- `2 x supervisor` (`agent_type=supervisor`, `slice_kind="work"`) for alternative decomposition paths.
- `1 x operator` (`agent_type=operator`, `slice_kind="work"`) to build dependency graph and ownership risk map.
- `1 x auditor` (`agent_type=auditor`, `slice_kind="review"`) for pre-mortem policy check (optional but default for new/complex tasks).

Each council member returns:

- `dispatch_plan` candidate or explicit constraints for the main wave.
- disjoint `ownership_paths` recommendations, dependency ordering, and failure-handling assumptions.
- concise evidence that each suggested branch can proceed independently.

## 2) Council merge behavior

- Accept or reconcile at most one council plan as the canonical seed.
- Reject duplicate/conflicting plans by explicit `next_actions` in the Director response and request a reduced plan before dispatch.
- Keep split depth low: if plans agree on 2–4 high-confidence lanes, proceed; if they diverge heavily, request one replan with smaller task boundary.

## 3) Dual-window protocol (read/write separation)

- `window_read`: in-flight read lane cap (operators/probes/read-only validation).
- `window_write`: in-flight write lane cap (coders + supervisor merge).
- Default policy for `max_threads=48`:
  - `window_read <= 16`
  - `window_write <= 8`
  - `reserve_threads = 4` (director, optional auditor, headroom)
- Write-capable slices:
  - `agent_type in ("coder_spark", "coder_codex")`
  - `agent_type = "supervisor"` and `slice_kind = "merge"`
- Never exceed ownership overlap limits between write slices.

## 4) Templates

- Bootstrap planner template:

```json
{
  "schema": "task-dispatch/1",
  "ssot_id": "scenario-hash",
  "task_id": "example-task",
  "slice_id": "wsN--council-operator-mapper",
  "agent_type": "operator",
  "slice_kind": "work",
  "timebox_minutes": 6,
  "allowed_paths": [],
  "ownership_paths": [],
  "dependencies": [],
  "task_contract": {
    "goal": "Map dependency graph and suggested split boundaries.",
    "acceptance": ["Boundary map is complete", "Constraints and risks are explicit"]
  },
  "evidence_requirements": ["commands", "files_read"]
}
```

- Canonical work template:

```json
{
  "schema": "task-dispatch/1",
  "ssot_id": "scenario-hash",
  "task_id": "example-task",
  "slice_id": "wsN--coder-docs",
  "agent_type": "coder_spark",
  "slice_kind": "work",
  "timebox_minutes": 12,
  "allowed_paths": ["multi-agent/"],
  "ownership_paths": ["multi-agent/PLAYBOOK.md"],
  "dependencies": [],
  "task_contract": {
    "goal": "Make scoped changes and keep write ownership disjoint.",
    "acceptance": ["Diff is scoped", "No overlap with sibling coder paths"]
  },
  "evidence_requirements": ["diff"]
}
```

## 5) Governance reminders

- Director dispatches remain non-overlapping in write ownership.
- `slice_kind` for supervisor planning remains `work` (no work should wait on `supervisor` only paths as `probe` unless explicitly diagnostic).
- All dispatches still must validate against `schemas/task-dispatch.schema.json`.
- For quick reuse of council skeletons in this workspace, use:

```bash
python3 multi-agent/tools/make_council_bootstrap.py <scenario> --task-id <task-id> --format array
```
