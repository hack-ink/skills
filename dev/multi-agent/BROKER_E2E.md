# Broker E2E (interactive, two-state)

This is an interactive end-to-end test that exercises the protocol in a real Codex session (as the Broker).

It is intentionally separate from `dev/multi-agent/e2e/run_smoke.py`, which validates schemas + fixtures without spawning agents.

## Goals

- Verify the Broker routing gate applies the two-state model consistently.
- Verify the `max_depth=1` broker topology and spawn allowlists are respected in practice.
- Verify ticket-board scheduling uses wait-any replenishment with reuse-first warm workers.
- Verify optional Inspector review works for write/mixed runs.

## Preconditions

- Runtime config:
  - `max_depth = 1`
  - `max_threads` is non-trivial (`>= 8` is usually enough for a small window).
- You can access the Codex TUI log: `~/.codex/log/codex-tui.log`.

## Test A - Routing gate (`single`)

Goal: confirm only tiny, clear fast-path work stays in `single`.

1. Pick a tiny local-only task (example: rename one variable or adjust one doc line).
2. As Broker, record:
   - `t_max_s` (`<= 60`)
   - `t_why`
   - `route="single"`
3. Execute the change in `single`.

Pass criteria:

- Broker does not spawn any agents.
- Task completes with `route="single"`.

## Test B - Routing gate (`multi`, scout-first)

Goal: confirm tasks outside the `single` fast path enter `multi` and begin with a scout-first board when split boundaries are not ready yet.

1. Pick a task that is not tiny, clear, and low-risk enough to stay in `single`.
2. As Broker, record:
   - `t_max_s` and `t_why`,
   - why the task is not tiny, clear, and low-risk, or why it exceeds the `single` fast-path cap (`t_max_s > 60`),
   - `route="multi"`.
3. Begin with a scout-first wave:
   - one runner probe,
   - optional inspector risk check,
   - no Builder ticket until the Broker has enough evidence to assign owned paths.
4. Continue in `multi` even if execution stays on one Builder work package after the scout phase.

Pass criteria:

- Broker enters `multi` and spawns at least one allowed worker.
- No direct Broker repo writes occur in `multi`.
- The run stays in `multi` while the Broker keeps work scoped to the smallest safe Builder package.

## Test C - Routing gate (`multi`, parallel expansion)

Goal: confirm `route="multi"` can expand into independent lanes once boundary evidence exists and still use ticket-board scheduling instead of a linear planning bottleneck.

1. Pick a task outside the `single` fast path with independent read/write/review lanes.
2. Prepare at least 3 lanes:
   - one runner lane (`runner`) for probes/inventory,
   - one builder lane (`builder`) for scoped edits,
   - one inspector lane (`inspector`) for risk/evidence checks.
3. As Broker, record:
   - `t_max_s` and `t_why`,
   - `route="multi"`.
4. Run the protocol:
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
- At least two lanes overlap once the Broker has enough evidence to expand.
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
- The same builder `agent_id` handles both `short` and `after_short`.
- TUI log shows `send_input` between `short` completion and `after_short` dispatch
- TUI log shows no `spawn_agent` for that handoff transition
- Runtime/backtest evidence should show the refill as reuse rather than spawn (`dispatch_mode="reuse"` for `after_short` and at least one builder reuse event overall).

## Notes

- This test targets real runtime behavior (tool registration, depth caps, thread scheduling).
- Use the TUI log as evidence; this document does not prescribe an automated log verifier.
