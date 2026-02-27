# Multi-Agent Playbook (vNext)

Hard constraint: runtime `max_depth = 1`.

This makes the Director a **broker/scheduler**. Depth=1 children do not have collab tools, so they cannot spawn. This is the only reliable way to prevent same-level spawns.

## 0) Routing gate (90s rule)

- Always record:
  - `t_max_s` (max seconds you expect to finish)
  - `t_why` (why that estimate / uncertainty)
- Route:
  - `single` if tiny, clear, low-risk and `t_max_s <= 90`
  - `multi` if uncertain or `t_max_s > 90`
- For `multi`, dispatch is **Supervisor-first per workstream**:
  - First slice for each workstream must be `agent_type="supervisor"` with `slice_kind="work"`.
  - The Supervisor Planning slice must return a full `dispatch_plan` that names workstreams and expected `timebox_minutes`.
  - For a given workstream, the Director MUST NOT dispatch any non-supervisor work slice (`operator`, `coder_*`, `auditor`) until that plan is received and accepted.
- Example (estimate only; not a hardcoded constant): `t_max_s = 900` (15 minutes).

## 1) Multi-agent supervisor workstream model

- Route `multi` into **N workstreams**, where N is based on disjoint ownership and dependency analysis.
- Director spawns one `supervisor` per workstream (1..N), ideally in parallel when dependencies allow.
- Each Supervisor must return a `worker-result.supervisor/1` sub-plan, including:
  - `ownership_paths` / `allowed_paths`
  - child `operator` and `coder_*` slices
  - direct dependencies and ordering notes
- Dispatch worker slices for a workstream as soon as its Supervisor plan is accepted, while other supervisor plans can continue to be evaluated independently.
- `max_depth=1` remains hard: supervisors cannot spawn sub-workers; they only return plans.
- If any workstream has blocking or high coupling, Director may collapse it to read-only investigation before continuing dispatch.

## 2) Roles (vNext)

- **Director (main thread)**: plans slices, spawns workers, schedules wait-any, integrates *decisions*, decides done/blocked, and (optionally) requests Auditor review. In `multi`, Director does **not** write the repo (no `apply_patch` / file edits). Any repo writes (including “integration”) must be delegated to a `coder_*` slice or the Supervisor Merge slice (`slice_kind="merge"`).
- **Supervisor (worker)**: subtask lead. Uses `agent_type="supervisor"` and returns `worker-result.supervisor/1`:
  - **Supervisor Planning**: produce a spawn-ready `dispatch_plan` (no repo writes, typically `slice_kind="work"`).
  - **Supervisor Merge**: perform integration + verification (repo writes allowed).
  The Supervisor worker never spawns (enforced by `max_depth=1`).
- **Operator (worker)**: non-coding execution (repo reads, commands, triage, reproductions, measurements, log inspection).
- **Coder (worker)**: repo writes (edits + tests). Use `coder_spark`; fall back to `coder_codex` only if needed.
- **Auditor (optional worker)**: review gate for correctness, evidence quality, and risk.

There is no Orchestrator role.

## 3) Spawn topology (strict)

The Director may spawn only these agent types: `operator`, `coder_spark`, `coder_codex`, `auditor`, `supervisor`.

Workers never spawn (enforced by `max_depth=1`).

## 4) Slice design (how to split)

Target smaller slices, but avoid “task confetti”.

Efficiency gate (split vs sequential):

- Split only when at least one testable condition holds:
  - >1 disjoint ownership path is required.
  - Shared dependency graph has >=2 independent branches.
  - Estimated implementation effort for a single coder path > 12 minutes.
  - At least one operation needs blocking I/O (build/test/package/fetch) while independent edits can proceed.
- Keep sequential when none of the above applies, especially for:
  - Single-file edits.
  - Clear one-pass transformations.
  - Any slice whose expected value-add is mostly exploratory.
- Hard anti-oversplit rule:
  - Do not split purely to create micro-slices < 2 minutes except command-only Operator probes.
  - Do not create duplicate workstreams for overlapping `ownership_paths`.

Recommended timeboxes:
- **Planning** (Supervisor): 6–10 min (produce `dispatch_plan` with disjoint ownership and explicit dependencies).
- **Probe** (Operator): 2–6 min (fast evidence to reduce uncertainty).
- **Work** (Operator): 4–12 min (commands + analysis + concrete next steps).
- **Work** (Coder): 4–12 min (small coherent change + verification).
- **Merge** (Supervisor): 15–25 min (resolve conflicts, run higher-scope checks).

Hard cap (prevents 20+ minute stalls):
- `coder_spark` + `slice_kind="work"` must have `timebox_minutes <= 12`. If you estimate more, split further or route the wrap-up into the Supervisor Merge slice.
- For route=`multi`, `timebox_minutes` for every scheduled workstream and work slice should remain in the 4–12 minute band unless explicitly marked **Merge**.

When to split:
- Independent paths (different dirs/modules) with **disjoint write ownership**.
- Clear “probe → decide” steps: run probes in parallel first, then branch.
- Work that is I/O bound (build/test) vs CPU bound (editing): overlap them.

When not to split:
- Single-file trivial changes (stay `single`).
- Anything that needs a shared mutable context every minute (heavy merge pressure).
- Micro-slices (< ~2 minutes) unless they are purely command execution.

Write ownership rule:
- Every coder slice declares `ownership_paths` (directories/files).
- The Director never runs two in-flight coder slices with overlapping `ownership_paths`.

## 5) Windowing (concurrency caps)

Definitions:
- `max_threads`: global runtime agent budget (set in Codex config).
- `window_size`: in-flight workers the Director will maintain for this run.
- `reserve_threads`: threads the Director intentionally leaves unused (headroom).

For `max_threads = 48`:
- `reserve_threads = 4` (Director + optional Auditor + headroom).
- Hard caps for this protocol (per run):
  - **write/mixed**: `window_size <= 12`
  - **read_only**: `window_size <= 16`

This keeps parallelism high without degrading throughput via merge conflicts and coordination thrash.

## 6) Scheduling (wait-any, replenishing)

Do not “spawn-wave then wait-all”.

Director scheduling loop (mandatory):
1. Maintain:
   - `pending`: slices not yet dispatched
   - `inflight`: spawned slices not yet finished + closed
   - `done`: completed slices
2. While `pending` is not empty OR `inflight` is not empty:
   - Spawn from `pending` into `inflight` until either:
     - `len(inflight) == window_size`, or
     - no slice is runnable due to dependencies/ownership locks.
   - If `inflight` is non-empty: call `functions.wait` (wait-any) with a bounded timeout and handle whichever child finishes.
     - On timeout: do **not** exit; loop and poll again.
     - On completion: record result, `close_agent`, remove from `inflight`, and immediately try to refill from `pending`.
   - If `inflight` is empty but `pending` is non-empty: the run is blocked (dependency cycle, ownership deadlock, or dispatch error). Stop and report `blocked` with the reason.

Hard rule: if you have spawned at least one child and `inflight` is non-empty, you must keep polling `functions.wait` until `inflight` becomes empty (or you explicitly mark the run blocked). Never “spawn then stop”.

Supervisor-Merge rule (prevents “Director writes code”):
  - If results require applying edits, resolving conflicts, or running final verification in the repo, dispatch a dedicated **Supervisor Merge** slice (`slice_kind="merge"`, broad `ownership_paths` as needed). The Director remains broker-only.

## 7) Dispatch schema (Director → worker)

Every `spawn_agent` message must be **JSON-only** and validate against:
- `schemas/task-dispatch.schema.json` (`schema="task-dispatch/1"`)
- Allowed `slice_kind` values are exactly `probe`, `work`, `review`, and `merge` in this protocol.

Minimum fields to set correctly:
- `ssot_id`: `scenario-<hex>` (stable, not date-based)
- `agent_type`: `operator` | `coder_spark` | `coder_codex` | `auditor` | `supervisor`
- `timebox_minutes`
- `ownership_paths` + `allowed_paths` (especially for coders)
- `task_contract.goal` + `task_contract.acceptance`

## 8) Worker outputs (JSON-only)

`JSON-only` is exact, strict:
- The output must be one full JSON value (typically an object), and nothing else.
- No surrounding prose, no markdown wrappers, no code fences (` ``` `), and no trailing text.
- No partial payload fragments.

Workers must return JSON-only results:
- Supervisor: `worker-result.supervisor/1`
- Operator: `worker-result.operator/1`
- Coder: `worker-result.coder/1`
- Auditor: `review-result.auditor/1`

If a worker cannot comply, it must return `status="blocked"` and explain why.
If a worker returns non-JSON or markdown-wrapped output, the Director must:
1. `send_input(interrupt=true)` asking for a raw JSON-only retry of the exact required schema.
2. If still non-compliant, `close_agent`, then re-dispatch the same slice with the same contract (or narrower scope).
3. Escalate to `blocked` only if repeated attempts still violate JSON-only.

## 9) Supervision (slow / stuck / crash)

If a worker exceeds its `timebox_minutes`:
1. `send_input(interrupt=true)` asking for a checkpoint: current state, last action, next 3 steps, and whether it is blocked.
2. If still not responding or clearly stuck: `close_agent`, then re-dispatch the slice (or shrink scope).
3. If repeated stalls: mark the run `blocked` with explicit reason and evidence.

If a worker errors/exits:
- The Director treats it as `blocked` for that slice, captures error evidence, and either retries with a smaller slice or escalates.

## 10) Auditor policy (default)

- **write/mixed runs**: request Auditor review before finalizing.
- **read_only runs**: skip Auditor unless the outcome is high-impact.

Audit loop cap:
- `audit_max_rounds = 5` (hard stop to avoid infinite loops).
  - Typical is 1 pass; 2 passes only if the first is `BLOCK` or `NEEDS_EVIDENCE`.

## 11) `ssot_id` policy

Use `scenario-hash` (no dates, no secrets).

Generator:
- `python3 multi-agent/tools/make_ssot_id.py <scenario>`
