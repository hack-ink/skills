# Protocol Parameters (v2)

This document is the single place to explain numeric “defaults” and other parameters that can look like magic numbers in logs or payloads.

If you change a parameter, update this file and the relevant schemas/fixtures together.

## Routing timebox: `t_max_s` (Director)

- **Meaning:** the Director’s maximum intended time budget for the current unit of work.
- **Where it appears:** Director status notes and sometimes logs.
- **Why it exists:** forces an explicit routing decision and prevents “accidental multi-agent” for tiny tasks.
- **Policy:**
  - If `t_max_s <= 90` and the task is clear/low-risk, prefer `routing_decision="single"`.
  - If uncertain or `t_max_s > 90`, prefer `routing_decision="multi"`.
- **Recommended defaults:**
  - Small edits: `t_max_s=90` (or less).
  - Multi-agent runs: pick a concrete number (example: `t_max_s=1200` for a 20-minute run) and record `t_why`.

## Review loop budget (Auditor + Orchestrator)

- **Fields:**
  - `dispatch-preflight.review_policy.auditor_passes_target = 2`
  - `dispatch-preflight.review_policy.auditor_passes_max = 5`
  - `review_loop.policy = "adaptive_min2_max5_second_pass_stable"`
- **Meaning:**
  - Target=2 enforces the required two-phase review (spec then quality).
  - Max=5 caps churn and prevents infinite loops.
- **Guideline:** if you hit the max, treat it as a decomposition/spec bug and escalate to the Director with a concise diagnosis.

## Concurrency sizing: `max_threads`, `reserve_threads`, `window_size`

- **`max_threads` (runtime config):** total agent thread slots available.
- **`reserve_threads` (policy input):** thread slots reserved for orchestration/review overhead (Director/Auditor/Orchestrator progress, logging, and integration).
- **`window_size` (dispatch policy):** max number of concurrent leaf slices in-flight.

Recommended calculation (default):

- `reserve_threads = 2`
- `window_size = min(max_threads - reserve_threads, window_cap)`
- `window_cap` should be kept modest to avoid diminishing returns from coordination overhead; start with `window_cap=4..8` and only increase when slices are truly independent and tool IO is the bottleneck.

## `functions.wait` polling + timeouts (Orchestrator)

- **Tool behavior:** `functions.wait` returns a completion as soon as any waited id reaches a final status; it can also time out and return “no completion yet”.
- **Why this matters:** windowed scheduling requires “wait-any”, not “wait-all”.

Recommended defaults:

- Poll with a finite timeout (example: `timeout_ms=30000`) and loop.
- On each completion:
  - consume the result,
  - `close_agent` for that child,
  - immediately spawn the next ready slice (if any) to keep the window full.

## Stall policy (soft vs hard)

You should treat “subagent runs too long” as a supervision problem (see `SUPERVISION.md`):

- **Soft timeout:** cooperative interruption + request partial results.
- **Hard timeout:** close/cancel and re-dispatch as a fresh slice, or escalate as `blocked` if progress cannot be recovered safely.
