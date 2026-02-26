# Supervision: Timeouts, Crashes, and Recovery (v2)

This protocol treats leaf agents as **child tasks** under a parent supervisor (the Orchestrator).
The Orchestrator must ensure: no orphan work, bounded waiting, and explicit recovery decisions.

## What the parent can observe

- Parents learn child completion/failure via `functions.wait` on child ids.
- Parents should assume children can:
  - take longer than expected (stall),
  - return partial output,
  - or exit early with an error/failure status.

## Principles (required)

1. **Cooperative cancellation first**
   - Prefer interruption + “return partial state” over immediate termination.
2. **Bounded waiting**
   - Never “wait forever”. Use timeboxed polling and an explicit soft/hard timeout.
3. **No orphans**
   - When a child is done (success or failure), `close_agent` it so it releases its thread slot.
4. **Restart is normal**
   - If a child fails or returns unusable output, re-dispatch as a fresh slice with a clearer `task_contract`, or escalate to the Director if the slice cannot be made independent.

## Stall handling (required)

Define two thresholds per slice:

- **Soft timeout:** “this is taking too long; ask for a checkpoint”.
- **Hard timeout:** “stop supervising and recover”.

Suggested policy when you don’t have better domain guidance:

1. **Soft timeout reached**
   - Use `send_input(interrupt=true)` to request:
     - a short progress summary,
     - what is blocked,
     - and the smallest next action to finish.
   - If the slice can still complete, allow one more bounded wait window.
2. **Hard timeout reached**
   - `close_agent` the child.
   - Decide one of:
     - re-spawn the slice as a fresh leaf agent (same ownership scope),
     - split it into smaller independent slices,
     - or escalate to Director as `blocked=true` with `blocking_reason="timeout:<...>"`.

Notes:

- For `read_only` slices (Operators), hard cancellation is usually safe (no repo writes).
- For `write` slices (Coders), prefer interruption first; if you must stop, capture `git status`/`git diff` evidence in integration so recovery is explicit.

## Crash / early-exit handling (required)

If a child exits unexpectedly (error, empty output, schema-invalid output):

1. Treat it as a slice failure and record it in `integration_report` (or equivalent evidence fields).
2. Re-dispatch as a fresh slice if:
   - the ownership scope is unchanged, and
   - the failure looks transient or caused by an unclear contract.
3. Escalate to Director if:
   - the failure implies missing permissions/environment,
   - the slice contract was wrong (cannot be made independent),
   - or multiple retries would exceed review-loop budget / timebox.

## “Wait-any” scheduling (required)

Windowing is “wait-any”:

1. Spawn up to `window_size`.
2. Call `functions.wait(ids=[...], timeout_ms=...)` repeatedly.
3. When any child completes:
   - consume the result,
   - `close_agent` it,
   - immediately spawn the next ready slice (if one exists),
   - continue until all slices are complete or the workflow becomes blocked.

Avoid “wait-all” behavior unless:

- all remaining work is blocked on a shared dependency, or
- you are about to run a single integration/verification step that requires all slices to be complete.

