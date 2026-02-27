# Director E2E (interactive, vNext)

This is an **interactive** end-to-end test that exercises the protocol in a real Codex session (as the Director).

It is intentionally separate from `dev/multi-agent/e2e/run_smoke.py`, which validates schemas + fixtures without spawning agents.

## Goals

- Verify the Director routing gate (the 90-second rule) is applied consistently.
- Verify the max_depth=1 broker topology and spawn allowlists are respected in practice.
- Verify the Director uses windowed scheduling (`functions.wait`) and closes completed children.
- Verify optional Auditor review works (recommended for write/mixed).

## Preconditions

- Runtime config:
  - `max_depth = 1`
  - `max_threads` is non-trivial (>= 8 is usually enough for a small window).
- You can access the Codex TUI log: `~/.codex/log/codex-tui.log`.

## Test A — Routing gate (should stay single)

Goal: confirm small, clear tasks do **not** enter multi-agent mode.

1. Pick a tiny local-only task (example: rename a variable in one file, or adjust a single doc line).
2. As Director, record:
   - `t_max_s` (must be <= 90)
   - `t_why`
   - `route="single"`
3. Execute the change in `single`.

Pass criteria:

- The Director does not spawn any agents.
- The task completes with `route="single"`.

## Test B — Routing gate (must use `multi`, supervisor-first)

Goal: confirm `route="multi"` always uses supervisor-first planning and respects efficiency gate expectations.

1. Pick a task estimated > 90 seconds (or equivalent work risk) and intentionally route it as `multi`.
2. Force a simple 2-workstream shape so you can observe parallel supervision:
   - one Supervisor slice should cover area A (for example: docs/rules updates),
   - one Supervisor slice should cover area B (for example: runtime/protocol updates).
3. As Director, record:
   - `t_max_s` (> 90) and `t_why`,
   - `route="multi"`.
4. Run the protocol:
   - Director plans a slice queue.
   - Director dispatches at least two `supervisor` planning slices first (one per workstream intent).
   - Director spawns depth=1 workers (`operator`, `coder_spark`/`coder_codex`, `supervisor`) using JSON-only `task-dispatch/1`.
   - Director schedules with windowed wait-any (`functions.wait`) and replenishes as slots free up.
   - (Recommended for write/mixed) Director spawns an `auditor` to review evidence before finalizing.
   - Optional `operator` support slices should originate only after supervisor plans are available.

Simple log-check for multiple workstreams (TUI):
- Open `~/.codex/log/codex-tui.log` and confirm:
  - two supervisor plans are started before any coder slice for the same task,
  - each supervisor log entry has a distinct stream/workstream identifier,
  - each coder slice references one stream identifier from the plan it should execute.

Pass criteria:

- No non-Director spawns occur (brokered collab).
- The Director calls `functions.wait` at least once during the run.
- For `route="multi"`, supervisor planning is mandatory:
  - no coder slice is dispatched before at least one supervisor plan result exists for the same task,
  - no coder dispatch without a parsed supervisor plan in hand.
- The Director does not stop/exit while any child is still in-flight (keeps polling wait-any until all children are finished + closed, or the run is explicitly blocked).
- In `multi`, the Director does not perform repo writes (no `apply_patch`); any repo changes (including integration/merge/conflict resolution) come from `coder_*` slices and/or the Supervisor Merge slice.
- Supervisor-first is required for this test:
  - the run includes a supervisor planning slice before coder dispatch,
  - at least two supervisor planning slices are present for the 2-workstream scenario.
- The run stays within depth=1.
- Leaf slices are dispatched using JSON-only `task-dispatch/1` (`multi-agent/schemas/task-dispatch.schema.json`).
- Every leaf worker result is parseable as raw JSON (no markdown/code fences or prose around payload) and matches the expected worker-result schema.
- If any leaf returns non-JSON output, the Director must run the JSON-only remediation flow: `send_input(interrupt=true)` then `close_agent` and re-dispatch.
- Efficiency gate checks (for this test):
  - Oversized coder slices are rejected:
    - no single coder slice should claim both workstream A and B,
    - coder slice scope should stay narrowly scoped to one stream intent.
  - No confetti oversplitting:
    - task does not produce a flood of tiny coder slices when two supervisors suffice,
    - no more than two parallel coder slices per supervisor stream in the first dispatch wave.
  - Wait-any replenishment is visible:
    - log shows `functions.wait` cycles followed by new dispatches as prior slices finish.

## Test C — Supervision (stall / crash handling)

Goal: confirm the Director does not “wait forever” and can recover from stalled or failed leaf slices.

1. Pick a task with at least 2 Operator slices where one can plausibly stall (for example: a command that might hang, or a web research slice that can get stuck).
2. As Director, ensure the brokered supervision follows `multi-agent/PLAYBOOK.md`:
   - bounded `functions.wait` polling (wait-any),
   - soft timeout interruption via `send_input(interrupt=true)`,
   - hard timeout recovery (close/re-dispatch or escalate with `blocking_reason="timeout:..."`).

Pass criteria:

- The Director continues making progress while other runnable work exists (does not block on one stalled slice).
- If a slice fails or stalls beyond the hard timeout, the run either retries safely or escalates as blocked with an explicit `timeout:` reason.

## Notes

- This test intentionally relies on real runtime behavior (tool registration, depth caps, and thread scheduling).
- Use the TUI log as evidence; this doc does not prescribe an automated log verifier.
