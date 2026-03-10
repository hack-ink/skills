# Worker Protocol (Two-State Multi)

This document defines how depth-1 workers should behave once the Broker has already escalated into `route="multi"`.

Hard constraints:

- Workers never spawn; only the Broker spawns (`max_depth=1`).
- `runner` and `inspector` never write repo content.
- Worker outputs must be **JSON-only** and schema-valid.
- `agent_type` is the canonical worker-result identity field. `/1` payloads may also use `role` as an identity alias only, and new outputs should emit `agent_type`.
- Using `role="builder"` does not create a separate `/1` wire-shape branch: `work_package_id` and the current evidence/recovery fields remain mandatory when applicable.

## Multi-mode defaults (all workers)

- Prefer returning **handoff requests** (new tickets) over expanding scope.
- Prefer package-sized handoffs over micro-slice follow-ups.
- Keep tickets small enough to finish inside `timebox_minutes`.
- Treat the Broker dispatch as the source of scope and intent. Do not reconstruct plan intent from broad repo rereads unless the ticket explicitly tells you to inspect those files.
- Make dependencies explicit and keep write ownership disjoint.
- If blocked, say exactly what evidence/decision is needed to unblock.
- When `status` is `blocked` or `partial`, return schema-valid structured recovery data instead of free-form prose:
  - `recovery.blocked_reason` when work is blocked
  - `recovery.required_evidence` / `recovery.required_decisions` when Broker input is needed
  - `recovery.checkpoint.state`, `last_action`, optional `resume_from`, and up to 3 `next_steps`

## Runner checklist

- Return concrete evidence under `evidence`:
  - `analysis` for summarized findings or boundary maps
  - `commands` for shell/tool proof
  - `files_read` for inspected file paths
- Propose follow-up tickets for:
  - parallelizable probes
  - disjoint write ownership partitions for Builder work packages
  - targeted Inspector reviews when risk is high
- Avoid handoffing micro follow-ups when ownership is unchanged and effective work is under ~3 minutes.
- Builder handoffs must include `work_package_id`.
- Builder handoffs must keep `ownership_paths` non-empty.
- Runner and Inspector handoffs should omit `ownership_paths` or leave it empty.

Runner example (including a handoff request):

```json
{
  "schema": "worker-result.runner/1",
  "ssot_id": "scenario-hash-5277daf391c2",
  "task_id": "example-task",
  "slice_id": "split--runner-boundary-map",
  "agent_type": "runner",
  "status": "done",
  "summary": "Identified two disjoint ownership partitions and one shared dependency gate.",
  "evidence": {
    "analysis": [
      "src/app/ and src/lib/ can proceed independently after the schema gate is updated."
    ],
    "commands": [
      {
        "cmd": "rg -n \"foo\" src/",
        "exit_code": 1
      },
      {
        "cmd": "ls -la",
        "exit_code": 0
      }
    ],
    "files_read": [
      "README.md"
    ]
  },
  "next_actions": [
    "Partition A: src/app/ (independent)",
    "Partition B: src/lib/ (independent)",
    "Dependency gate: update schema first"
  ],
  "handoff_requests": [
    {
      "schema": "task-dispatch/1",
      "ssot_id": "scenario-hash-5277daf391c2",
      "task_id": "example-task",
      "slice_id": "wave1--builder-ownership-A",
      "agent_type": "builder",
      "slice_kind": "work",
      "work_package_id": "pkg-ownership-A",
      "timebox_minutes": 12,
      "ownership_paths": [
        "src/app/"
      ],
      "dependencies": [],
      "task_contract": {
        "goal": "Implement changes for partition A only.",
        "acceptance": [
          "Edits remain within src/app/.",
          "Relevant verification evidence is provided."
        ],
        "constraints": [
          "Do not touch src/lib/."
        ]
      },
      "evidence_requirements": [
        "git_diff",
        "verification"
      ]
    }
  ]
}
```

## Builder checklist

- Stay strictly within `ownership_paths`.
- Treat each Builder ticket as one named work package.
- Prefer completing micro follow-ups inside the current package when ownership and constraints are unchanged.
- If owned edits have landed but the ticket is unlikely to finish cleanly before the timebox expires, prefer a schema-valid `partial` checkpoint over silence or a rushed `done` claim.
- Make partial checkpoints durable enough for Broker or human takeover: say what landed, what verification already ran, what must not be replayed, and the narrowest remaining work.
- Keep the same parent work and same `work_package_id` only while the owned `ownership_paths` stay unchanged; ask the Broker for a new work package when ownership changes.
- If you discover cross-cutting work:
  - stop expanding scope
  - propose schema-valid handoff requests with disjoint ownership
- Emit new Builder handoffs only when ownership must split or package scope would exceed the timebox.
- For `status="done"`, return:
  - `work_package_id`
  - `changeset`
  - `evidence.diff_summary` / `evidence.git_diff_summary` when diff-oriented evidence is required
  - `verification`
- `work_package_id` stays mandatory on every Builder `/1` result; using the `role` alias does not waive it.
- For `status="blocked"` or `status="partial"`, return the structured `recovery` object with checkpoint data instead of only a prose explanation.
- When returning `status="partial"` after landed edits, include `changeset`, set `recovery.checkpoint.resume_from` and `next_steps`, and either attach the verification already run or list `verification` in `recovery.required_evidence`.
- Broker/runtime salvage follow-ups may reuse the same `work_package_id` only when the owned `ownership_paths` stay unchanged.

## Inspector checklist

- Review for:
  - missing evidence gates
  - ownership/lock collisions across Builder tickets
  - schema-invalid outputs or non-JSON output risks
- Use `review_mode` when the dispatch carries one:
  - `spec_compliance`: check whether requested scope is complete, identify missing requirements, and flag extra/unrequested behavior.
  - `code_quality`: review the accepted scope for maintainability, safety, testing, and implementation quality.
  - `final_closeout`: review cross-slice consistency and unresolved board-level risks before closeout.
- Echo `review_mode` in the Inspector result when the ticket used one so the Broker can validate gate ordering unambiguously.
- Preserve gate ordering when multiple Inspector modes are required: `spec_compliance` first, `code_quality` second.
- When required review finds issues, make it clear that Builder follow-up plus re-review is still required before the parent task/work package can advance.
- Return `review_notes` when review evidence is requested.
- Prefer structured findings with `severity`, `message`, and optional `category`, `confidence`, `evidence`, and `paths`.
- Prefer short, decisive verdicts with explicit “what evidence would change my mind”.
