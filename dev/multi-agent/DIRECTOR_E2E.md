# Director E2E (interactive)

This is an **interactive** end-to-end test that exercises the protocol in a real Codex session (as the Director).

It is intentionally separate from `dev/multi-agent/e2e/run_smoke.py`, which validates schemas + fixtures without spawning agents.

## Goals

- Verify the Director routing gate (the 90-second rule) is applied consistently.
- Verify the depth=2 spawn topology and spawn allowlists are respected in practice.
- Verify Orchestrator uses windowed scheduling (`functions.wait`) and closes completed children.
- Verify Auditor gating (spec -> quality) happens before the Director finalizes.

## Preconditions

- Runtime config:
  - `max_depth = 2`
  - `max_threads` is non-trivial (>= 8 is usually enough for a small window).
- You can access the Codex TUI log: `~/.codex/log/codex-tui.log`.

## Test A — Routing gate (should stay single_agent)

Goal: confirm small, clear tasks do **not** enter multi-agent mode.

1. Pick a tiny local-only task (example: rename a variable in one file, or adjust a single doc line).
2. As Director, record:
   - `t_max_s` (must be <= 90)
   - `t_why`
   - `route="single_agent"`
3. Execute the change in `single_agent`.

Pass criteria:

- The Director does not spawn any agents.
- The task completes with `route="single_agent"`.

## Test B — Routing gate (should escalate to multi_agent)

Goal: confirm uncertain or >90s work escalates to multi-agent and follows the protocol.

1. Pick a task that is either:
   - uncertain (requires research / evidence), **or**
   - estimated > 90 seconds, **or**
   - multi-file / risky coordination.
2. As Director, record:
   - `t_max_s` (> 90) and `t_why`, **or** explicitly note uncertainty.
   - `route="multi_agent"`
3. Run the protocol:
   - Director spawns exactly one `auditor` and one `orchestrator` peer for a single `ssot_id`.
   - Orchestrator spawns only leaf slices (`operator`, `coder_spark`, `coder_codex` fallback).
   - Orchestrator uses windowed `functions.wait` scheduling.
   - Auditor gates completion (spec then quality) before the Director finalizes.

Pass criteria:

- No same-level or cross-level spawns occur (especially: Orchestrator never spawns Orchestrator/Auditor/Director).
- Orchestrator calls `functions.wait` at least once during the run.
- The run stays within depth=2.

Optional automated check (log-based):

1. Identify the `ssot_id` used in the run.
2. Run:
   - `python3 dev/multi-agent/e2e/verify_codex_tui_log.py --ssot-id <ssot_id>`

## Notes

- This test intentionally relies on real runtime behavior (tool registration, depth caps, and thread scheduling).
- The log verifier is conservative: it checks spawn topology and wait usage; it does not attempt to prove every windowing detail.

