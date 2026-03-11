# Broker E2E (interactive, two-state)

This document is the manual runtime checklist for a live Broker session.

## Test A - Routing gate (`single`)

Goal: confirm only tiny, clear, low-risk work stays in `single`.

Pass criteria:

- Broker records `t_max_s` and `t_why`.
- Broker keeps the task in `route="single"`.
- Broker does not spawn any agents.

## Test B - Routing gate (`multi`)

Goal: confirm non-trivial work enters `multi` and uses the new ticket contract.

Pass criteria:

- Broker records `t_max_s` and `t_why`.
- Broker chooses `route="multi"`.
- Broker dispatches JSON-only `ticket-dispatch/1` payloads.
- If the manual child skill policy marks a known local skill `dispatch-authorized`, the Broker names it in `authorized_skills`.
- Broker never writes repo content directly in `multi`.

## Test C - Wait-any scheduling

Goal: confirm the Broker keeps a live ticket board and refills lanes without wait-all waves.

Pass criteria:

- `functions.wait` appears repeatedly while tickets are in flight.
- Broker uses wait-any replenishment instead of wait-all waves.
- Broker reuses warm workers when possible.
- Builder tickets never overlap on the same `write_scope`.

## Test D - Invalid-output recovery

Goal: confirm the Broker does not depend on a rich worker checkpoint payload.

Pass criteria:

- Broker requests one bounded retry for invalid output.
- If the retry still fails, Broker closes the child.
- Broker inspects local evidence and decides locally whether to salvage or redispatch.
- The runtime check does not expect worker-managed handoff tickets or schema-shaped checkpoints.

## Test E - Required review gates

Goal: confirm Inspector ordering remains broker-local.

Pass criteria:

- `spec_compliance` runs before `code_quality` when both are required.
- Closeout waits for required Inspector verdicts.
- `ticket-result/1` payloads remain JSON-only throughout the run.
