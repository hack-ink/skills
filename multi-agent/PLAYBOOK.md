# Multi-Agent Playbook (Two-State)

Hard constraint: runtime `max_depth = 1`.

`max_depth=1` makes the Broker a **scheduler**. Depth-1 children do not have collab tools, so they cannot spawn. This is the topology guardrail that prevents same-level spawning.

## 0) Routing gate (two-state)

- Always record:
  - `t_max_s` (max seconds expected to finish)
  - `t_why` (why that estimate / what evidence supports the route)
- Route:
  - `single` only if the task is tiny, clear, low-risk, and clearly fits the fast path (`t_max_s <= 60`)
  - `multi` for everything else: long tasks, uncertain tasks, risky tasks, or work that needs scout-first boundary discovery
- Escalation rule:
  - start in `single` only when the task clearly fits the fast-path bar above, including the `t_max_s <= 60` cap
  - otherwise enter `multi` immediately
  - within `multi`, start with scout-first tickets when boundaries are unclear and expand fanout only after evidence
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
- `dependencies`
- `task_contract.goal`, `task_contract.acceptance`, `task_contract.constraints`
- Broker should pack enough task context into `task_contract` for the worker to execute without reconstructing plan intent from broad repo rereads. If a worker must reread a plan or broad design doc, say so explicitly in the ticket.
- Inspector tickets that participate in ordered review gates should set `review_mode`. Leave `review_mode` unset for pre-mortems or other review slices that are not part of a named gate sequence.
- Builder tickets additionally require `work_package_id` and non-empty `ownership_paths`
- Runner and Inspector tickets must omit `ownership_paths` or leave it empty; both mean no write lock
- Worker result schemas use `agent_type` as the canonical identity field; `/1` result payloads may also use `role` as an identity alias only, and new outputs should emit `agent_type`
- Builder results carry the originating `work_package_id`; Broker validates that it matches the dispatch before accepting the result
- For Builder results, using the `role="builder"` alias does not change the required `/1` wire shape. `work_package_id` remains mandatory.
- Worker evidence and recovery are structured by schema, not free prose:
  - runner evidence: `analysis`, `commands`, `files_read`
  - builder evidence: `diff_summary`, `git_diff_summary`, `verification`
  - inspector evidence: `review_notes`
  - blocked/partial runner and builder results use structured `recovery.checkpoint`

Board state tracked by Broker:

- `pending`: valid tickets not dispatched yet
- `inflight`: dispatched tickets not yet completed
- `done`: completed tickets
- `blocked`: tickets that cannot run due to dependency, lock, or repeated failure

Parent task/work-package state is Broker-local bookkeeping, not a new wire-level schema field:

- A Builder ticket returning `done` means the implementation slice finished, not that the parent task or work package is ready to advance.
- The Broker may track derived parent states such as `awaiting_builder`, `awaiting_required_review`, `ready_to_advance`, and `blocked`, but these remain scheduler-local concepts rather than `task-dispatch/1` or worker-result fields.
- If Inspector gates are required, the parent task/work package is only complete after the required review slices pass.
- Downstream or closeout advancement must not treat Builder success alone as sufficient when required Inspector gates are still open.

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
   - if the completed ticket opens or blocks required review gates, update the Broker-local parent task/work package bookkeeping before advancing downstream work
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
  - normalized+sorted `ownership_paths` (trim trailing `/`; non-builder paths normalize to `[]`)
- `slice_id` must remain unique on the board; dedup merges into one canonical ticket and never keeps duplicates with the same `slice_id`.
- Merge rule is additive-only: union list-like constraints (`acceptance`, `constraints`, `evidence_requirements`) and dependency sets; do not merge when core execution fields diverge.

`handoff_requests` are suggestions, not direct spawns. Only the Broker dispatches workers.

## 7) Split heuristics (avoid linear bottlenecks)

Split when at least one condition holds:

- disjoint ownership paths exist
- dependency graph has independent branches
- blocking I/O can overlap with independent edits
- a single coherent write exceeds a 12-minute timebox

Keep sequential when none apply:

- tightly coupled edits requiring continuous shared context
- tasks that still need guarded scout-first execution before the Broker can assign owned paths confidently
- one-pass changes where a single Builder lane plus Inspector sequencing is clearer than fanout
- initial probes that must finish before ownership boundaries are credible

If a task was tiny and clear enough to stay local, it should have routed to `single` before reaching this section. Once in `multi`, keeping execution serial is acceptable; do not force fanout just to satisfy the route name.

Recommended timeboxes:

- Runner probe: 2-6 min
- Runner work: 4-12 min
- Builder work: 4-12 min
- Inspector review: 4-10 min

Protocol modules (use as needed; do not turn them into mandatory linear phases):

- `COUNCIL.md`: optional scout-first bootstrap wave (read/review only)
- `BROKER_SPLIT.md`: split ladder + dispatch templates for scout-first or parallel scheduling
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
- Builder `done` results include `work_package_id`, owned `ownership_paths`, and structured diff/verification evidence.
- Runner and Builder `blocked`/`partial` results include schema-shaped recovery data instead of prose-only stall notes.
- `/1` alias support is field-level, not shape-level: `role` is still accepted as an identity alias, but Builder `/1` results still require `work_package_id` and the current evidence/recovery contract.

If output is non-JSON or schema-invalid:

1. `send_input(interrupt=true)` and request exact schema retry
2. if retry fails, `close_agent` and re-dispatch narrowed slice
3. escalate to `blocked` after repeated failure

## 10) Slow/stuck worker handling

If worker exceeds `timebox_minutes`:

1. interrupt and request a schema-shaped checkpoint (`state`, `last_action`, `resume_from`, next 1-3 steps, blocked reason if any)
2. if the stuck worker is a Builder and owned diffs may already have landed locally, switch to salvage/adoption handling before any generic redispatch:
   - close the original stuck worker before dispatching any follow-up Builder so salvage continues from a single live owner
   - independently inspect the current workspace state under the Builder's `ownership_paths`; rely on `git diff`, targeted file reads, and fresh verification instead of trusting an interrupted or malformed Builder report
   - record scheduler-local provenance for the salvage decision: prior `slice_id`, `work_package_id`, why the original Builder result was unusable, what evidence was re-verified, and whether the landed diff is adopted as complete or partial
   - keep the same parent task and same `work_package_id` only while the follow-up stays under the same `ownership_paths`; mint a new work package when ownership changes
   - if the landed diff is only partial, dispatch a narrowed Builder follow-up from the current workspace state that covers the remaining work only and explicitly avoids replaying completed side effects
   - if the landed state cannot be verified independently or ownership is ambiguous, escalate to human takeover or `blocked` instead of speculative adoption
3. if no Builder salvage path applies, close and re-dispatch with smaller scope
4. after repeated stalls, mark `blocked` with evidence

## 11) Inspector policy

- Default for write/mixed runs: run Inspector review before final closeout.
- Read-only runs: Inspector is optional unless outcome is high impact.
- Cap review loops with `audit_max_rounds = 5`.
- Treat Inspector as a mode-driven review lane, not a second role system:
  - `spec_compliance`: verify the implementation matches the requested scope, call out missing requirements, and flag extra/unrequested behavior.
  - `code_quality`: review the accepted scope for maintainability, safety, testing, and implementation quality.
  - `final_closeout`: review the whole board for cross-slice gaps before final closeout.
- `review_mode` is the canonical wire-level transport for the ordered Inspector gate names above. Pre-mortem or exploratory Inspector slices may omit it.
- If both `spec_compliance` and `code_quality` are required, run `spec_compliance` first. Do not start `code_quality` while spec gaps are still open.
- If Inspector finds issues on a required gate, route the same work package (or a narrowed follow-up under the same parent) back to Builder, then re-run the relevant Inspector gate before advancing.
- Final closeout for write/mixed runs should prefer a whole-board Inspector pass, not only per-package spot checks.

## 12) `ssot_id` policy

Use scenario-hash format only (no dates, no secrets).

Generator:

```bash
# Set MULTI_AGENT_HOME to the installed `multi-agent` skill directory
# (the folder containing this doc and `tools/`), derived from the runtime's skills entry.
MULTI_AGENT_HOME="<skill-root>"
python3 "$MULTI_AGENT_HOME"/tools/make_ssot_id.py <scenario>
```
