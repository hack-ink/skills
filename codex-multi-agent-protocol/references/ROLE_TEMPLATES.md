# Role Templates (v2)

This document provides copy-pastable templates for the 5-role workflow:

- Director (main)
- Auditor
- Orchestrator
- Coder
- Operator

Goal: keep runs fast while preserving reliability via explicit contracts, evidence, and rerun escalation.

## Coder `task_contract` template (write)

Use for code/config changes.

- **goal**: <1 sentence outcome>
- **scope**: <exact files/dirs/systems in scope>
- **constraints**:
  - Do not modify unrelated files.
  - Do not change APIs unless requested.
  - Do not commit or push unless explicitly instructed.
  - Prefer minimal diffs; explain any non-trivial changes.
- **expected_output**:
  - Summary of changes (files + key edits).
  - `verification_steps`: commands + observed results.
  - Risk notes + rollback suggestion (if applicable).
- **non_goals**: <explicit exclusions>
- **writes_repo**: `true` (required by schema)

Coder output checklist:

- List touched file paths (or `not_applicable`).
- Provide concrete verification evidence (stdout snippets or exit codes).
- Call out any assumptions or blockers.

## Operator `task_contract` template (read_only ops/research)

Use for command execution, fetching, inspection, and research that feeds decisions without repo writes.

- **goal**: <what decision this work supports>
- **scope**: <topics/repos/dirs + boundaries>
- **constraints**:
  - Do not include sensitive internal identifiers in queries.
  - Do not modify repo-tracked files.
  - Prefer short, deterministic commands; stop on conflicts.
  - Use 3+ independent sources when feasible; prefer primary docs.
  - Label hypotheses vs verified facts.
- **expected_output**:
  - Command log: command -> exit code -> key output lines.
  - 3–7 bullets of findings, each tied to evidence.
  - Evidence map: claim -> evidence -> source link (for web research).
  - Open questions + what would resolve them.
- **non_goals**: <explicit exclusions>
- **writes_repo**: `false` (required by schema)

Operator output checklist:

- Provide an action log with concrete commands and evidence.
- Keep synthesis minimal; do not over-interpret ambiguous outputs.
- Call out any assumptions or blockers.

## Orchestrator slice decomposition checklist (recommended)

Before spawning any leaf slice, confirm:

- The slice has a single objective and a concrete done condition.
- The slice includes all inputs needed to start (paths, commands, error text, links).
- The slice has narrow ownership scopes and cannot conflict with other in-flight slices.
- The slice states its evidence requirement (`actions` / `verification_steps`).
- The slice states the assumptions policy: unknowns are resolved via research and safest reversible defaults (no user questions mid-flight).

## Auditor (spec -> quality) checklists

### Spec phase (must pass first)

- Is the coder output aligned with the `task_contract` goal and scope?
- Any unrequested extras or scope creep?
- Are constraints respected (no unrelated edits, no risky operations)?
- Is the evidence sufficient to accept as "done" for this task kind?

Block if any answer is "no".

### Quality phase (only after spec pass)

- Verification quality: do the steps actually cover the changed behavior?
- Failure modes: any obvious edge cases untested?
- Maintainability: is the change understandable and minimal?
- Risk: any security/safety concerns for tool usage or external inputs?

## Orchestrator integration checklist

- Confirm slices are independent and ownership scopes do not overlap (for parallel runs).
- Enforce the spawn allowlist: spawn ONLY protocol agent types (Auditor/Orchestrator/Operator/Coder*) plus `awaiter` (waiting/polling only); never spawn built-in/default agent types (for example `worker`, `default`, `explorer`).
- Use `awaiter` only as a waiting/polling helper (optional; prefer Orchestrator direct wait_any for short runs).
- Enforce windowed concurrency (spawn -> wait_any -> review -> replenish).
- Leaf agents do not interact with the user; any user checkpoint is Director-only.
- When uncertain, run a parallel Operator research fanout, synthesize options + assumptions, and return an Auditor-reviewable brief with a recommended safest default (avoid asking the user unless required).
- Default to `high` reasoning effort; use provider fallback only:
  - Availability fallback: `spark` -> `5.3-codex` (only when rate-limited / exhausted).
- Operator is single-tier by default (no provider fallback).
- Produce an integration report (conflict check + full verification command, when applicable).
