# Protocol Workflows (v2)

This document is the **operational playbook** that pairs with the structural schemas in `schemas/`.
If the schemas answer **"what JSON must look like"**, this answers **"how the work must run"**.

## Hard gates summary (printable)

- If `dispatch-preflight.routing_decision != "multi_agent"`, short-circuit (no leaf spawns).
- Spawn allowlist: when `routing_decision == "multi_agent"`, spawn ONLY protocol agent types (Auditor/Orchestrator/Operator/Coder*) plus `awaiter` (waiting/polling only). Never spawn built-in/default agent types (for example `worker`, `default`, `explorer`).
- Only dispatch a Coder when the slice is clearly a coding task (repo changes). If unsure, keep it at Orchestrator.
- Do not parallelize without an explicit independence assessment and an ownership lock policy.
- Auditor review is two-phase: spec must pass before quality runs.
- No evidence, no completion: coders must return `verification_steps`; operators must return `actions`; orchestrator must return integration evidence for write workflows.
- Stop on `blocked=true` from any review phase.
- Close completed agents (thread starvation is a real failure mode).

## 0) Routing guardrails (fast path vs slow path)

This protocol is a **slow path**: it trades overhead for correctness, auditability, and coordination.

### Do not run multi-agent for micro tasks

If the task is `instruction_only`, `vcs_only`, or a tiny `single_file_edit` with clear acceptance criteria, stay in `micro_solo`.
This routing decision should be made by your global `AGENTS.md` before invoking this protocol.

### Defense-in-depth: short-circuit if mis-invoked

If a `dispatch-preflight` indicates `routing_decision != "multi_agent"`, **do not spawn leaf agents**.
Return a blocked/redirected result that recommends `micro_solo` execution.

Terminology note:

- `coder` is the coding leaf role for repo write work (code/config changes with verification evidence).
- `operator` is the non-coding leaf role for command execution, fetching, and inspection tasks without repo writes.

## 0.1) `review_only` flag (briefs vs work)

The `review_only` boolean distinguishes "a deliverable that is only a brief/review artifact" from "work that changes state".

Guidelines:

- Use `review_only=true` for prework artifacts such as an execution brief, an audit brief, or a review-only checkpoint where no changes should be claimed.
- Use `review_only=false` for normal research outputs and for any workflow that performs tool actions, writes files, or mutates state.
- If `review_only=true`, the payload must not claim that code or external systems were changed; treat it as a planning/review deliverable.

## 0.2) Runtime preconditions (depth + threads)

- This workflow assumes the runtime supports **depth=3** nesting for the leaf dispatch chain:
  - Director (main) -> Auditor -> Orchestrator -> (Coder | Operator)
- Recommended: set `max_depth = 3` and treat it as a **hard cap**. Deeper nesting tends to reduce clarity and makes failure modes harder to debug.
- If your runtime cannot support depth=3, do not force it: switch to a flattened topology (Director directly spawns Orchestrator and leaf agents, with Auditor review gates) and update the SSOT accordingly.

## 0.3) `ssot_id` convention (recommended)

Use `ssot_id = <scenario>-<token>` (short, ASCII, kebab-case):

- Recommended token forms: `uuid` or short `hash` (stable, human-scannable).
- Examples: `dev-550e8400-e29b-41d4-a716-446655440000`, `ops-9f2c0d6a1b3e`, `research-7c9e6679`
- Requirements:
  - One run -> one `ssot_id` shared across all payloads
  - Different runs -> different `ssot_id` (avoid collisions)
- Avoid raw epoch seconds (e.g. `...-1771782960`): they are opaque in logs and easy to misread.

## 1) Parallel dispatch workflow (independent domains)

Use when you have **2+ independent domains** (different failing tests, subsystems, or files) where fixes can proceed without shared state.

This workflow also applies to **read-only research** where independent slices improve coverage (e.g., multiple web queries, or parallel analysis across multiple repositories).
It also applies to **repeatable operational work** split across multiple independent targets (for example, running the same `git` workflow in several repositories).

### 1.1 Independence assessment (required)

Before spawning leaf agents:

1. Identify domains and record them in `dispatch_plan.independence_assessment.domains`.
2. For each domain, explicitly decide `can_parallelize`.
3. If _any_ domain shares files, shared state, or causal coupling, set `can_parallelize=false` and keep it sequential.

### 1.2 Ownership lock policy (required)

When `conflict_policy="ownership_lock"`:

- Each leaf slice has `ownership_paths`.
- No two concurrent leaf slices may have overlapping `ownership_paths`.
- Shared files are handled by a dedicated single slice (or forced sequential execution).

For read-only research, treat `ownership_paths` as **scopes** (not just filesystem paths), for example:

- `web:topic/<slice_id>` for web research slices
- `repo:<owner>/<repo>` for multi-repo analysis slices

For multi-repo operational slices (commit/push, version bumps, config sync), treat each repo as its own scope (e.g., `repo:<owner>/<repo>`) and include the concrete working directory (e.g., `/abs/path/to/repo`) in `allowed_paths`.

### 1.3 Windowed concurrency (required)

Run leaf agents in a window:

1. Spawn up to `window_size`.
2. Use `wait-any` polling.
3. As one completes, review the result, then spawn the next slice (replenish) until all slices are done.
4. Always `close_agent` for completed children to avoid thread starvation.

Recommended default:

- Keep a small reserve for orchestration/review work.
  - Example: `reserve_threads=2`, `window_size = max_threads - reserve_threads`

### 1.4 Integration loop (required)

After slice results return:

1. Read every leaf agent `summary` plus evidence:
    - Coder: `verification_steps`
    - Operator: `actions`
2. Check for ownership/overlap violations.
3. Perform `integration_report.conflict_check`.
4. Run `integration_report.full_test` (or the best available end-to-end verification command).
5. Only then finalize.

### 1.5 Dynamic replanning (supported)

Dynamic parallelism is allowed and recommended:

- As slice results arrive, the Orchestrator may:
  - unblock dependent work,
  - refine the plan,
  - and spawn new slices immediately (still subject to independence + ownership lock).
- Do not wait for the entire wave to finish if new independent work is now ready.

### 1.6 `awaiter` helper (optional)

`awaiter` is an allowed helper type for **waiting/polling only**. It is not a worker role.

Use an `awaiter` ONLY when:

- At least one in-flight slice is expected to take `> 30s`, or
- You are running a large window (suggestion: `window_size >= 8`) and want the Orchestrator to keep integrating/reviewing while completions are polled, or
- You need a watchdog that reports "no progress" timeouts.

Rules:

- `awaiter` must not spawn agents and must not run command/tool actions other than waiting/polling.
- `awaiter` outputs status only (completed/inflight ids, last completion timestamp, and any timeout alarms).
- The Orchestrator remains responsible for `close_agent` hygiene and integration evidence.

Hard rules still apply:

- Coder slices are `code_change` only.
- Operator slices may run tool/command actions but must not write the repo (`writes_repo=false`).
- Close completed children to reclaim thread slots.

### 1.7 Slice naming (recommended)

Avoid adding new schema fields just to track waves. Encode it in ids:

- Operator: `op-w1-01`, `op-w1-02`, ...
- Coder: `code-w2-01`, `code-w2-02`, ...
- Avoid epoch-based ids here as well; prefer short wave/sequence tokens.

## 2) Subagent-per-task execution workflow (fresh leaf agent per task)

Use when you have an implementation plan with multiple tasks that are **mostly independent**, but may touch adjacent areas.

### 2.1 Fresh leaf agent per task (required)

- One task slice -> one leaf agent.
- Do **not** reuse leaf agents across tasks (reduce context pollution).
- Do **not** run multiple implementing slices concurrently unless independence + ownership lock is satisfied.

### 2.2 Q&A gate (required)

If a coder asks a clarifying question:

1. Escalate the question to the Director (main). Leaf agents do not interact with the user directly.
2. Director asks the user and records the answer (or explicitly records "unknown").
3. If the answer changes scope/constraints, update the slice `task_contract` and re-dispatch the coder.

If the Director cannot obtain an answer (user has no context/experience to answer):

4. Spawn 2+ parallel **Operator** research slices to propose options (claim -> evidence -> source + open questions).
5. Orchestrator synthesizes 1–3 candidate assumptions with tradeoffs.
6. Director asks the user to pick (or confirm a safest default), then updates `task_contract` and continues the coder slice.

### 2.3 Two-phase audit gate (required): spec -> quality

Auditor review is explicitly two-phase, reflected in `audit_phases`:

1. **Spec phase**
    - Check alignment with SSOT + `task_contract`.
    - Block on missing requirements or unrequested extras.
2. **Quality phase**
    - Check maintainability, risk, tests, correctness evidence quality.
    - Block on weak verification, unsafe patterns, or ownership/parallelism violations.

Hard rule: **quality must not run before spec passes**.

### 2.4 Re-review loop (required)

If any phase finds issues:

1. The coder fixes.
2. The same phase re-reviews.
3. Repeat until pass (bounded by your protocol's pass limits).

### 2.5 Coder provider fallback (recommended)

Keep tiering minimal to avoid over-design:

- Use **high** reasoning effort by default.
- Use **provider fallback** only: `spark` (preferred) -> `5.3-codex` (fallback only when spark is unavailable/exhausted).

Recommended default configuration names:

- `coder_spark`
- `coder_codex`

Fallback trigger (example):

- The runtime rejects the spark tier due to quota/token exhaustion/rate limits (or equivalent availability signal).

Execution policy (minimal state machine):

1. Start at `coder_spark` (high reasoning).
2. If **availability** triggers, switch provider: `coder_spark` -> `coder_codex`.
3. If **quality** triggers, rerun with a tighter `task_contract` and better verification (do not change provider).

If your runtime does not support multiple coder agent types, approximate this by rerunning with a stronger model tier (SSOT-controlled) rather than inventing deeper nesting.

### 2.6 Operator model policy (recommended)

Keep Operator single-tier by default to reduce complexity:

- Use **high** reasoning effort.
- Do not design an Operator-specific fallback unless you have a real operational need.

## 3) Prompt contract template (Orchestrator -> Coder)

Every slice must include a `task_contract` with at least:

- `goal`: what to accomplish
- `scope`: the boundaries (what area/file/subsystem)
- `constraints`: what not to do (no refactors, touch only X, etc.)
- `expected_output`: what the coder must return (and what "done" means)
- `non_goals`: explicitly excluded work
- `writes_repo`: must be `true` for Coder slices

Recommended additions (encode either in the message or in schema fields):

- Minimal verification command(s) to run and expected signal
- Relevant error messages / failing test names
- Ownership paths (what files the coder may touch)

For web research slices, include:

- The exact query set / angles
- The expected output format (e.g., bullet summary + links + risks/unknowns)

For operational slices, include:

- The exact commands to run (and which directory each runs in)
- Safety constraints (no history rewrites unless requested, stop on conflicts, report evidence)

## 3.1) Prompt contract template (Orchestrator -> Operator)

Every operator slice must include a `task_contract` with at least:

- `goal`: what evidence to collect
- `scope`: the boundaries (repo(s), directories, or `web:` scopes)
- `constraints`: explicit safety constraints (no writes, no long-running commands, stop on conflicts)
- `expected_output`: required evidence format (commands + outputs + short synthesis)
- `non_goals`: explicitly excluded work
- `writes_repo`: must be `false` for Operator slices

Operator evidence requirements:

- Prefer exact command lists where feasible.
- Record command outputs succinctly (exit codes, key stdout/stderr lines).

## 4) Evidence standard (minimum)

### Coder

- Must provide `verification_steps` with concrete commands and evidence.
- If no verification is possible, mark status `not_applicable` and explain why, plus a best-effort alternative.

### Orchestrator

- Must provide `integration_report`:
    - `conflict_check` command + evidence
    - `full_test` command + evidence
- Must obey repository-level write gates (if present). For example, before any `git commit` / `git push`, run the repository's pre-commit gate skill and follow its required commit message format.

### Auditor

- Must provide `audit_phases` evidence for both spec and quality.
- Must provide `diff_review` when applicable.

## 5) Red flags (block immediately)

- Micro task routed to multi-agent (should short-circuit).
- Parallel coders with overlapping ownership.
- "Just increase timeouts" fixes for flaky tests without root-cause reasoning.
- Running quality review before spec review passes.
- Proceeding after any reviewer marks `blocked=true`.
- Leaving completed agents unclosed (thread starvation risk).
