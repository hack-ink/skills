# Broker E2E (interactive, single-first)

This is an interactive end-to-end test that exercises the protocol in a real Codex session (as the Broker).

It is intentionally separate from `dev/multi-agent/e2e/run_smoke.py`, which validates schemas + fixtures without spawning agents.

## Goals

- Verify the Broker routing gate applies the three-tier single-first model consistently.
- Verify the `max_depth=1` broker topology and spawn allowlists are respected in practice.
- Verify ticket-board scheduling uses wait-any replenishment with reuse-first warm workers.
- Verify optional Inspector review works for write/mixed runs.

## Preconditions

- Runtime config:
  - `max_depth = 1`
  - `max_threads` is non-trivial (`>= 8` is usually enough for a small window).
- You can access the Codex TUI log: `~/.codex/log/codex-tui.log`.

## Test A - Routing gate (`single`)

Goal: confirm small, clear tasks do not enter multi-agent mode.

1. Pick a tiny local-only task (example: rename one variable or adjust one doc line).
2. As Broker, record:
   - `t_max_s` (must be `<= 90`)
   - `t_why`
   - `route="single"`
3. Execute the change in `single`.

Pass criteria:

- Broker does not spawn any agents.
- Task completes with `route="single"`.

## Test B - Routing gate (`single-deep`)

Goal: confirm non-decomposable work stays local when it is either long or explicitly marked as needing deeper local inspection.

1. Pick one coherent lane of work that is not safely decomposable.
2. Use one of these qualifying shapes:
   - `t_max_s > 90`, or
   - `t_max_s <= 90` with `dev_requires_deeper_inspection=true` because more local inspection or uncertainty reduction is needed before any split decision would be credible.
3. Confirm it is not safely decomposable:
   - tightly coupled edits or reasoning steps,
   - one owner path or one continuous integration step,
   - splitting would add coordination cost without useful overlap.
4. As Broker, record:
   - `t_max_s` and `t_why`,
   - `decomposable=false`,
   - `dev_requires_deeper_inspection=true` when the task stays `single-deep` at `t_max_s <= 90`,
   - `route="single-deep"`.
5. Execute the task directly in the main thread.

Pass criteria:

- Broker does not spawn any agents.
- No `spawn_agent`, `functions.wait`, `send_input`, or `close_agent` calls are needed.
- Task completes with `route="single-deep"`.

## Test C - Routing gate (`multi`, single-first)

Goal: confirm `route="multi"` is used only when the task is decomposable and then uses ticket-board scheduling, not a linear planning bottleneck.

1. Pick a task estimated `> 90` seconds (or high uncertainty) that can be decomposed into independent read/write/review lanes.
2. Prepare at least 3 lanes:
   - one runner lane (`runner`) for probes/inventory,
   - one builder lane (`builder`) for scoped edits,
   - one inspector lane (`inspector`) for risk/evidence checks.
3. As Broker, record:
   - `t_max_s` (`> 90`) and `t_why`,
   - `decomposable=true`,
   - `route="multi"`.
4. If a task is not decomposable, keep it in `single-deep` even when `t_max_s > 90`.
5. Run the protocol:
   - Broker dispatches JSON-only `task-dispatch/1` tickets for allowed agent types (`runner`, `builder`, `inspector`).
   - Broker schedules with wait-any (`functions.wait`) and replenishes when slots free up.
   - Broker enforces write ownership locks (no overlapping in-flight `ownership_paths` for builder tickets).
   - Workers may return `handoff_requests`; Broker validates and enqueues them before dispatching.

Simple log-check in `~/.codex/log/codex-tui.log`:

- `functions.wait` appears repeatedly during active runs.
- new dispatches appear after completed waits (replenishment loop).
- no spawned worker launches another worker (depth remains 1).

Pass criteria:

- No non-Broker spawns occur (brokered topology).
- `functions.wait` is used with wait-any behavior and the run does not stop while children remain in-flight.
- No direct Broker repo writes occur in `multi`.
- Only allowed agent types are dispatched (`runner`, `builder`, `inspector`).
- Worker outputs are raw JSON (no markdown/code fences) and match their schemas.
- If any worker returns invalid/non-JSON output, Broker runs remediation (`send_input(interrupt=true)`, then close/re-dispatch when needed).

## Test D - Supervision (stall / crash handling)

Goal: confirm Broker does not wait forever and can recover from stalled/failed slices.

1. Pick a task with at least 2 runner slices where one can plausibly stall.
2. Ensure supervision loop follows `multi-agent/PLAYBOOK.md`:
   - bounded wait-any polling,
   - timeout interruption (`send_input(interrupt=true)`),
   - close/re-dispatch or explicit blocked outcome.

Pass criteria:

- Broker continues progress while other runnable work exists.
- If a slice fails or stalls beyond timeout, run retries safely or exits as blocked with explicit evidence.

## Test E - Reuse-first eliminates after_short delay

Goal: confirm dependency replenishment uses `send_input` on a warm worker, instead of cold-start spawning.

1. Set a unique base path in `/tmp`, for example:
   - `/tmp/swarmbench-live-<id>/wait_any/`
2. Spawn two builder slices at the same time:
   - `long` (~60s): write `long.start`, sleep, then `long.done`
   - `short` (~5s): write `short.start`, sleep, then `short.done`
3. When `short` completes:
   - do **not** `close_agent` for that builder
   - dispatch `after_short` (~10s) via `send_input` to the **same** builder `agent_id`
   - write `after_short.start`, sleep, then `after_short.done`
4. Continue wait-any polling until all slices complete.

Minimal command payloads for Builder slices:

```sh
mkdir -p /tmp/swarmbench-live-<id>/wait_any/alpha \
  && date +%s > /tmp/swarmbench-live-<id>/wait_any/alpha/long.start \
  && sleep 60 \
  && date +%s > /tmp/swarmbench-live-<id>/wait_any/alpha/long.done

mkdir -p /tmp/swarmbench-live-<id>/wait_any/beta \
  && date +%s > /tmp/swarmbench-live-<id>/wait_any/beta/short.start \
  && sleep 5 \
  && date +%s > /tmp/swarmbench-live-<id>/wait_any/beta/short.done

mkdir -p /tmp/swarmbench-live-<id>/wait_any/gamma \
  && date +%s > /tmp/swarmbench-live-<id>/wait_any/gamma/after_short.start \
  && sleep 10 \
  && date +%s > /tmp/swarmbench-live-<id>/wait_any/gamma/after_short.done
```

Pass criteria:

- `after_short.start < long.done` (dependency refill overlaps with `long`)
- TUI log shows `send_input` between `short` completion and `after_short` dispatch
- TUI log shows no `spawn_agent` for that handoff transition

## Notes

- This test targets real runtime behavior (tool registration, depth caps, thread scheduling).
- Use the TUI log as evidence; this document does not prescribe an automated log verifier.
