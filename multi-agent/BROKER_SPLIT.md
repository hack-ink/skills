# Broker Split Protocol (Two-State)

Use this when `route="multi"` and you need to turn current understanding into a runnable ticket board. If boundaries are already clear, go straight to Builder packages. If boundaries are unclear, emit a scout-first board that discovers them safely.

Goal: produce a **runnable ticket board** (not a linear plan) with parallelism that is safe under ownership locks.

## Split ladder (quick checklist)

Split when any applies:

- disjoint `ownership_paths` exist
- dependency graph has independent branches
- blocking I/O (build/test/search) can overlap with independent edits
- a single coherent write likely exceeds ~12 minutes

Prefer sequential when none apply:

- tightly coupled edits requiring continuous shared context
- tasks that should stay scout-first until the Broker has enough evidence
- one-pass mechanical transformations where a single Builder package is cleaner than fanout

## Work packages (default)

Use Builder work packages as the primary split unit.

- A work package is one Builder ticket that bundles a coherent ownership-scoped implementation sequence (implement + verify + report).
- Micro follow-ups (effective work under ~3 minutes) should be merged into an existing package when ownership and constraints stay compatible.
- Cap initial Builder package fan-out at 4; expand only after evidence from the first wave.
- Keep `handoff_requests` budget at 3 or fewer per worker; if above budget, propose merged packages instead of more slices.

## Scout-first board pattern

When boundaries are not yet credible, start `multi` with a low-fanout board:

- `1 x runner` to map ownership, dependencies, or blocking I/O
- optional `1 x inspector` to identify safety/evidence risks
- no Builder tickets until the Broker has enough evidence to assign owned paths confidently

Serial scout-first execution is still a valid `multi` run.

## Dedup fingerprint hygiene

- Keep `slice_id` unique per ticket board entry; do not emit duplicate `slice_id` values for retried or alternative drafts.
- When proposing near-duplicate handoff tickets, assume Broker dedup compares normalized execution scope (`schema`, `ssot_id`, `task_id`, `agent_type`, `slice_kind`, sorted dependencies, normalized path lists).
- If the intended work is distinct, make that distinction explicit in dependencies, paths, or `task_contract` constraints instead of changing only `slice_id`.

## Dispatch templates (schema-valid)

Boundary map (Runner):

```json
{
  "schema": "task-dispatch/1",
  "ssot_id": "scenario-hash-5277daf391c2",
  "task_id": "example-task",
  "slice_id": "split--runner-boundary-map",
  "agent_type": "runner",
  "slice_kind": "work",
  "timebox_minutes": 6,
  "dependencies": [],
  "task_contract": {
    "goal": "Map repo boundaries and dependencies to enable parallel scheduling under disjoint ownership locks.",
    "acceptance": [
      "Return a proposed partition of ownership paths for safe parallel Builder tickets.",
      "Return a dependency DAG between tickets (what must be done first, what can run in parallel).",
      "List any lock-collision risks and how to avoid them.",
      "Propose package-sized Builder tickets (up to 4 initial packages) with merged micro follow-ups."
    ],
    "constraints": [
      "Read-only investigation only.",
      "Do not write repo content.",
      "Prefer concrete file and command evidence."
    ]
  },
  "evidence_requirements": [
    "commands",
    "files_read"
  ]
}
```

Write wave (Builder):

```json
{
  "schema": "task-dispatch/1",
  "ssot_id": "scenario-hash-5277daf391c2",
  "task_id": "example-task",
  "slice_id": "wave1--builder-ownership-A",
  "agent_type": "builder",
  "slice_kind": "work",
  "timebox_minutes": 12,
  "work_package_id": "pkg-ownership-A",
  "ownership_paths": [
    "<SET_ME_disjoint_ownership_paths>"
  ],
  "dependencies": [],
  "task_contract": {
    "goal": "Implement the scoped change set strictly within the owned paths, with verification evidence.",
    "acceptance": [
      "Package checklist: implement scoped edits within ownership paths.",
      "Package checklist: run relevant verification for this package.",
      "Package checklist: report diff summary + verification evidence in one result.",
      "All edits stay within ownership paths (or return a split handoff request if cross-cutting work is required)."
    ],
    "constraints": [
      "Write only within ownership paths.",
      "If new work is discovered, return schema-valid handoff requests instead of expanding scope.",
      "Do not emit micro follow-up handoffs when ownership remains the same; merge into this package."
    ]
  },
  "evidence_requirements": [
    "git_diff",
    "verification"
  ]
}
```

Pre-mortem (Inspector):

```json
{
  "schema": "task-dispatch/1",
  "ssot_id": "scenario-hash-5277daf391c2",
  "task_id": "example-task",
  "slice_id": "split--inspector-pre-mortem",
  "agent_type": "inspector",
  "slice_kind": "review",
  "timebox_minutes": 8,
  "dependencies": [],
  "task_contract": {
    "goal": "Identify safety, sequencing, and evidence risks before parallel Builder tickets are scheduled.",
    "acceptance": [
      "List the highest-risk failure modes (locks, missing tests, unclear acceptance).",
      "Specify required evidence gates before closeout."
    ],
    "constraints": [
      "Review-only output.",
      "No repo writes."
    ]
  },
  "evidence_requirements": [
    "review_notes"
  ]
}
```
