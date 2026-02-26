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

## Test B — Routing gate (should escalate to multi)

Goal: confirm uncertain or >90s work escalates to multi-agent and follows the protocol.

1. Pick a task that is either:
   - uncertain (requires research / evidence), **or**
   - estimated > 90 seconds, **or**
   - multi-file / risky coordination.
2. As Director, record:
   - `t_max_s` (> 90) and `t_why`, **or** explicitly note uncertainty.
   - `route="multi"`
3. Run the protocol:
   - Director plans a slice queue.
   - Director spawns depth=1 workers (`operator`, `coder_spark`/`coder_codex`) using JSON-only `task-dispatch/1`.
   - Director schedules with windowed wait-any (`functions.wait`) and replenishes as slots free up.
   - (Recommended for write/mixed) Director spawns an `auditor` to review evidence before finalizing.

Pass criteria:

- No non-Director spawns occur (brokered collab).
- The Director calls `functions.wait` at least once during the run.
- The Director does not stop/exit while any child is still in-flight (keeps polling wait-any until all children are finished + closed, or the run is explicitly blocked).
- In `multi`, the Director does not perform repo writes (no `apply_patch`); any repo changes (including integration/merge/conflict resolution) come from Coder slices only.
- The run stays within depth=1.
- Leaf slices are dispatched using JSON-only `task-dispatch/1` (`multi-agent/schemas/task-dispatch.schema.json`).

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
