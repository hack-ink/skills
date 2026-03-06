# Multi-Agent Playbook (Single-First)

Hard constraint: runtime `max_depth = 1`.

`max_depth=1` makes the Broker a **scheduler**. Depth-1 children do not have collab tools, so they cannot spawn. This is the topology guardrail that prevents same-level spawning.

## 0) Routing gate (single-first)

- Always record:
  - `t_max_s` (max seconds expected to finish)
  - `t_why` (why that estimate / what evidence supports the route)
- Route:
  - `single` if the task is tiny, clear, low-risk, and likely to finish inside `t_max_s <= 90`
  - `single-deep` if the task is still one coherent lane but needs deeper inspection, longer focused execution, or uncertainty reduction before splitting
  - `multi` only if the task is actually decomposable into coherent packages with disjoint ownership, independent branches, or useful lane parallelism
- Escalation rule:
  - start at the smallest route that can plausibly finish
  - move from `single` to `single-deep` when the work grows but remains tightly coupled
  - move from `single` or `single-deep` to `multi` only after the split is justified by evidence, not by uncertainty alone
- For `multi`, use ticket scheduling with wait-any replenishment. There is no required planning phase.

## 1) Role model

Protocol terminology:

- **Broker**: main thread. Schedules tickets, enforces locks, integrates decisions, and closes workers.
- **Runner**: `agent_type="runner"`. Runs commands and gathers evidence.
- **Builder**: `agent_type="builder"`. Performs repo writes and verification.
- **Inspector**: `agent_type="inspector"`. Reviews evidence and risks.

Execution rule:

- Broker is orchestration-only in `multi`; no repo writes.
- All repo writes, including integration and conflict resolution, go through Builder tickets.

## 2) Ticket board model

Every scheduled unit is a `task-dispatch/1` ticket.

Mandatory ticket fields:

- `ssot_id`, `task_id`, `slice_id`
- `agent_type`, `slice_kind`, `timebox_minutes`
- `allowed_paths`, `ownership_paths`, `dependencies`
- `task_contract.goal`, `task_contract.acceptance`, `task_contract.constraints`
- Builder tickets additionally require `work_package_id`, `expected_work_s`, and non-empty `allowed_paths` plus `ownership_paths`

Board state tracked by Broker:

- `pending`: valid tickets not dispatched yet
- `inflight`: dispatched tickets not yet completed
- `done`: completed tickets
- `blocked`: tickets that cannot run due to dependency, lock, or repeated failure

## 3) Write ownership and locks

- A write-capable ticket is any ticket with `agent_type="builder"`.
- Broker must never run two in-flight write tickets with overlapping `ownership_paths`.
- Read/review tickets do not consume write locks.
- If a lock conflict blocks all pending write tickets, keep polling inflight tickets and refill on completion.

## 4) Lane caps (window policy)

Use separate caps by lane:

- `window_runner`: in-flight runner tickets (`runner`)
- `window_builder`: in-flight builder tickets (`builder`)
- `window_inspector`: in-flight inspector tickets (`inspector`)
- `reserve_threads`: headroom for Broker/control operations

Recommended default lane windows for `max_threads=48`:

- `window_runner <= 8`
- `window_builder <= 3`
- `window_inspector <= 3`
- `reserve_threads = 2`

Constraint:

- `window_runner + window_builder + window_inspector <= max_threads - reserve_threads`

## 5) Scheduling loop (wait-any + replenishment)

Do not use spawn-wave then wait-all.

Broker loop is mandatory:

1. Build runnable set: pending tickets with satisfied dependencies and lock-safe ownership.
2. Track worker state by lane:
   - `idle_workers[agent_type]`: reusable worker IDs
   - `inflight`: busy worker IDs plus `worker_id -> slice_id`
3. Dispatch runnable tickets while lane caps allow:
   - if `idle_workers[agent_type]` is non-empty, assign via `send_input` using JSON-only `task-dispatch/1`
   - otherwise `spawn_agent` using JSON-only `task-dispatch/1`
4. If `inflight` is non-empty, call `functions.wait` (wait-any) with bounded timeout.
5. On completion:
   - validate JSON-only/schema-valid worker result
   - record worker result and mark ticket done
   - move worker from busy to `idle_workers[agent_type]`
   - immediately refill from `pending`
6. On timeout:
   - do not exit
   - continue loop
7. If `pending` is non-empty and `inflight` is empty:
   - mark run `blocked`
   - report cause (dependency cycle, lock deadlock, or dispatch validation failure)

Hard rule: once any worker is spawned, keep polling until no tickets are runnable/in-flight or an explicit blocked state is returned.

`close_agent` is allowed only for:

- rotation
- failure recovery
- end-of-run cleanup

### Rotation (default policy)

Rotate a warm worker (close and remove from pool) when either threshold is hit:

- `tickets_handled >= 6`
- `invalid_output_count >= 2`

### Dispatch-overhead aware

Reuse-first is mandatory. Do not spawn a new worker for tiny follow-up slices when an idle worker exists for that lane.

## 6) Handoff protocol

Multi-mode scheduling is dynamic.

- Workers may return optional `handoff_requests` containing additional `task-dispatch/1` tickets.
- Broker validates each requested ticket before enqueueing:
  - schema-valid payload
  - allowed `agent_type`
  - dependency references are resolvable
  - write ownership does not violate active locks
- Broker deduplicates only when the fingerprint matches after normalization:
  - `schema`, `ssot_id`, `task_id`, `agent_type`, `slice_kind`
  - sorted `dependencies`
  - normalized+sorted `allowed_paths` and `ownership_paths` (trim trailing `/`)
- `slice_id` must remain unique on the board; dedup merges into one canonical ticket and never keeps duplicates with the same `slice_id`.
- Merge rule is additive-only: union list-like constraints (`acceptance`, `constraints`, `no_touch`, `evidence_requirements`) and dependency sets; do not merge when core execution fields diverge.

`handoff_requests` are suggestions, not direct spawns. Only the Broker dispatches workers.

## 7) Split heuristics (avoid linear bottlenecks)

Split when at least one condition holds:

- disjoint ownership paths exist
- dependency graph has independent branches
- blocking I/O can overlap with independent edits
- a single coherent write exceeds a 12-minute timebox

Keep sequential when none apply:

- tiny single-file edits
- one-pass mechanical transformations
- tightly coupled edits requiring continuous shared context
- exploratory or uncertain work that has not yet produced a safe package boundary (`single-deep` first)

Recommended timeboxes:

- Runner probe: 2-6 min
- Runner work: 4-12 min
- Builder work: 4-12 min
- Inspector review: 4-10 min

Protocol modules (use as needed; do not turn them into mandatory linear phases):

- `COUNCIL.md`: optional bootstrap wave (read/review only)
- `BROKER_SPLIT.md`: split ladder + dispatch templates for safe parallel scheduling
- `WORKER_PROTOCOL.md`: worker behavior and handoff request quality bar once `route="multi"` is active
- `FAILURE_MODES.md`: recovery playbook for stalls, schema failures, deadlocks, and over-splitting

## 8) Dispatch topology (strict)

The Broker may spawn only:

- `runner`
- `builder`
- `inspector`

Workers never spawn under `max_depth=1`.

## 9) Output contract (JSON-only)

JSON-only is strict:

- one full JSON value only
- no markdown fences
- no surrounding prose or trailing text

Worker output schemas:

- Runner: `worker-result.runner/1`
- Builder: `worker-result.builder/1`
- Inspector: `review-result.inspector/1`

If output is non-JSON or schema-invalid:

1. `send_input(interrupt=true)` and request exact schema retry
2. if retry fails, `close_agent` and re-dispatch narrowed slice
3. escalate to `blocked` after repeated failure

## 10) Slow/stuck worker handling

If worker exceeds `timebox_minutes`:

1. interrupt and request checkpoint (state, last action, next 3 steps, blocked status)
2. if still stuck/non-responsive, close and re-dispatch with smaller scope
3. after repeated stalls, mark `blocked` with evidence

## 11) Inspector policy

- Default for write/mixed runs: run Inspector review before final closeout.
- Read-only runs: Inspector is optional unless outcome is high impact.
- Cap review loops with `audit_max_rounds = 5`.

## 12) `ssot_id` policy

Use scenario-hash format only (no dates, no secrets).

Generator:

- `python3 multi-agent/tools/make_ssot_id.py <scenario>`
