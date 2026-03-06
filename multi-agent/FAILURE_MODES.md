# Failure Modes (Single-First Multi)

Use this when a run becomes unreliable (stalls, schema failures, ownership deadlocks, or over-splitting).

## 1) Schema-invalid output

1. `send_input(interrupt=true)` requesting a strict schema retry (JSON-only).
2. If retry fails, `close_agent` and re-dispatch a narrowed slice.
3. After repeated failures, mark `blocked` with evidence.

## 2) Stuck/slow worker

1. Interrupt and request a checkpoint: state, last action, next 3 steps, blocked reason.
2. If still stuck/non-responsive, close and re-dispatch smaller scope.
3. If the same stall repeats, require an Inspector pre-mortem before continuing.

## 3) Ownership lock deadlock

- If all pending Builder tickets conflict with active locks:
  - keep Runner/Inspector lanes busy (evidence gathering, risk checks)
  - wait-any poll until a Builder completes
  - if no progress is possible, mark `blocked` with the conflicting ownership paths

## 4) Over-splitting

Symptoms:

- tickets are <2 minutes but require heavy coordination
- frequent duplicate handoff requests
- repeated lock conflicts due to sloppy ownership partitioning
- ticket storm: dispatch count keeps rising while net completed work per ticket stays low
- dispatch overhead dominates runtime (wait-any refill latency is mostly scheduling round-trips)

Fix:

- merge micro-slices into coherent Builder work packages per owned area
- reduce initial Builder package count and expand only after first-wave evidence
- enforce per-worker handoff budget; request merged packages when budget is exceeded
- keep Runner probes broad and few, not a swarm of tiny greps
