# Protocol Workflows (v2)

This document is the **operational playbook** that pairs with the structural schemas in `schemas/`.
If the schemas answer **“what JSON must look like”**, this answers **“how the work must run”**.

## 0) Routing guardrails (fast path vs slow path)

This protocol is a **slow path**: it trades overhead for correctness, auditability, and coordination.

### Do not run multi-agent for micro tasks

If the task is `instruction_only`, `vcs_only`, or a tiny `single_file_edit` with clear acceptance criteria, stay in `micro_solo`.
This routing decision should be made by your global `AGENTS.md` before invoking this protocol.

### Defense-in-depth: short-circuit if mis-invoked

If a `dispatch-preflight` indicates `routing_decision != "multi_agent"`, **do not spawn implementers**.
Return a blocked/redirected result that recommends `micro_solo` execution.

## 1) Parallel dispatch workflow (independent domains)

Use when you have **2+ independent domains** (different failing tests, subsystems, or files) where fixes can proceed without shared state.

This workflow also applies to **read-only research** where independent slices improve coverage (e.g., multiple web queries, or parallel analysis across multiple repositories).
It also applies to **repeatable operational work** split across multiple independent targets (for example, running the same `git` workflow in several repositories).

### 1.1 Independence assessment (required)

Before spawning implementers:

1. Identify domains and record them in `dispatch_plan.independence_assessment.domains`.
2. For each domain, explicitly decide `can_parallelize`.
3. If *any* domain shares files, shared state, or causal coupling, set `can_parallelize=false` and keep it sequential.

### 1.2 Ownership lock policy (required)

When `conflict_policy="ownership_lock"`:

- Each implementer slice has `ownership_paths`.
- No two concurrent implementers may have overlapping `ownership_paths`.
- Shared files are handled by a dedicated single slice (or forced sequential execution).

For read-only research, treat `ownership_paths` as **scopes** (not just filesystem paths), for example:

- `web:topic/<slice_id>` for web research slices
- `repo:<owner>/<repo>` for multi-repo analysis slices

For multi-repo operational slices (commit/push, version bumps, config sync), treat each repo as its own scope (e.g., `repo:<owner>/<repo>`) and include the concrete working directory (e.g., `/abs/path/to/repo`) in `allowed_paths`.

### 1.3 Windowed concurrency (required)

Run implementers in a window:

1. Spawn up to `window_size`.
2. Use `wait-any` polling.
3. As one completes, review the result, then spawn the next slice (replenish) until all slices are done.
4. Always `close_agent` for completed children to avoid thread starvation.

### 1.4 Integration loop (required)

After slice results return:

1. Read every implementer `summary` + `verification_steps` evidence.
2. Check for ownership/overlap violations.
3. Perform `integration_report.conflict_check`.
4. Run `integration_report.full_test` (or the best available end-to-end verification command).
5. Only then finalize.

## 2) Subagent-per-task execution workflow (fresh implementer per task)

Use when you have an implementation plan with multiple tasks that are **mostly independent**, but may touch adjacent areas.

### 2.1 Fresh implementer per task (required)

- One task slice → one implementer.
- Do **not** reuse implementers across tasks (reduce context pollution).
- Do **not** run multiple implementing slices concurrently unless independence + ownership lock is satisfied.

### 2.2 Q&A gate (required)

If an implementer asks a clarifying question:

1. Answer clearly and completely.
2. If the answer changes scope/constraints, update the slice `task_contract`.
3. Re-dispatch the implementer with the updated contract.

### 2.3 Two-phase audit gate (required): spec → quality

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

1. The implementer fixes.
2. The same phase re-reviews.
3. Repeat until pass (bounded by your protocol’s pass limits).

## 3) Prompt contract template (Orchestrator → Implementer)

Every slice must include a `task_contract` with at least:

- `goal`: what to accomplish
- `scope`: the boundaries (what area/file/subsystem)
- `constraints`: what not to do (no refactors, touch only X, etc.)
- `expected_output`: what the implementer must return (and what “done” means)
- `non_goals`: explicitly excluded work

Recommended additions (encode either in the message or in schema fields):

- Minimal verification command(s) to run and expected signal
- Relevant error messages / failing test names
- Ownership paths (what files the implementer may touch)

For web research slices, include:

- The exact query set / angles
- The expected output format (e.g., bullet summary + links + risks/unknowns)

For operational slices, include:

- The exact commands to run (and which directory each runs in)
- Safety constraints (no history rewrites unless requested, stop on conflicts, report evidence)

## 4) Evidence standard (minimum)

### Implementer

- Must provide `verification_steps` with concrete commands and evidence.
- If no verification is possible, mark status `not_applicable` and explain why, plus a best-effort alternative.

### Orchestrator

- Must provide `integration_report`:
  - `conflict_check` command + evidence
  - `full_test` command + evidence

### Auditor

- Must provide `audit_phases` evidence for both spec and quality.
- Must provide `diff_review` when applicable.

## 5) Red flags (block immediately)

- Micro task routed to multi-agent (should short-circuit).
- Parallel implementers with overlapping ownership.
- “Just increase timeouts” fixes for flaky tests without root-cause reasoning.
- Running quality review before spec review passes.
- Proceeding after any reviewer marks `blocked=true`.
- Leaving completed agents unclosed (thread starvation risk).
