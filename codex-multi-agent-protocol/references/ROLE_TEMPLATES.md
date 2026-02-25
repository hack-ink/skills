# Role Templates (v2)

This document provides copy-pastable templates for the 5-role workflow:

- Director (main)
- Auditor
- Orchestrator
- Coder
- Operator

Goal: keep runs fast while preserving reliability via explicit contracts, evidence, and rerun escalation.

## Schema-first output rule (required)

When producing a protocol payload:

- Output **JSON only** (no surrounding commentary).
- Start from the schema example in `schemas/*.json` and edit values (do not invent new keys).
- Do not omit required keys; do not add extra top-level keys (`additionalProperties: false` is enforced in many subschemas).
- Respect enums exactly (common gotcha: many `status` fields are `pass|fail|not_applicable`, not `done`).

### Minimal Operator output skeleton (read_only)

Use this as a fill-in template if you cannot reliably start from the schema `examples`.

```json
{
  "ssot_id": "<scenario>-<token>",
  "protocol_version": "2.0",
  "task_id": "<task-id>",
  "subtask_id": "<op-id>",
  "agent_type": "operator",
  "workflow_mode": "parallel_dispatch",
  "routing_mode": "assistant_nested",
  "slice_id": "<slice-id>",
  "attempt": 1,
  "status": "done",
  "summary": "<one sentence>",
  "blocked": false,
  "self_check": { "status": "pass", "command": "<cmd>", "evidence": "<stdout/exit>" },
  "task_contract": {
    "goal": "<goal>",
    "scope": "<scope>",
    "constraints": ["<c1>"],
    "expected_output": ["<o1>"],
    "non_goals": ["<n1>"],
    "writes_repo": false
  },
  "questions": [],
  "actions": [
    { "name": "<check>", "command": "<cmd>", "status": "pass", "evidence": "<stdout/exit>" }
  ],
  "rationale": "<why this evidence is sufficient>",
  "blocking_reason": "not_applicable",
  "allowed_paths": ["<abs/path/or/scope>"]
}
```

### Minimal Orchestrator output skeleton (read_only)

```json
{
  "ssot_id": "<scenario>-<token>",
  "protocol_version": "2.0",
  "task_id": "<task-id>",
  "subtask_id": "<orch-id>",
  "agent_type": "orchestrator",
  "workflow_mode": "parallel_dispatch",
  "routing_mode": "assistant_nested",
  "slice_id": "<slice-id>",
  "coder_subtask_ids": [],
  "operator_subtask_ids": ["<op-id-1>"],
  "parallel_peak_inflight": 1,
  "dispatch_plan": {
    "independence_assessment": { "conflict_policy": "ownership_lock", "domains": [] },
    "windowing": { "plan": "windowed", "window_size": 1, "wait_strategy": "wait_any" },
    "slices": []
  },
  "review_phases": [
    { "phase": "dispatch_safety", "status": "pass", "notes": "<why safe>" },
    { "phase": "finalization", "status": "pass", "notes": "<what completed>" }
  ],
  "status": "done",
  "blocked": false,
  "rationale": "REVIEW_ONLY: <brief summary>",
  "review_only": true,
  "blocking_reason": "not_applicable",
  "allowed_paths": ["<abs/path/or/scope>"],
  "review_loop": {
    "policy": "adaptive_min2_max3_second_pass_stable",
    "self_passes": 2,
    "converged": true,
    "new_issues_found_in_last_self_pass": false,
    "escalation_reason": "none"
  }
}
```

### Minimal Auditor output skeleton (read_only)

```json
{
  "ssot_id": "<scenario>-<token>",
  "protocol_version": "2.0",
  "task_id": "<task-id>",
  "subtask_id": "<audit-id>",
  "agent_type": "auditor",
  "workflow_mode": "parallel_dispatch",
  "routing_mode": "assistant_nested",
  "slice_id": "<slice-id>",
  "coder_subtask_ids": [],
  "operator_subtask_ids": [],
  "parallel_peak_inflight": 0,
  "audit_phases": [
    { "phase": "spec", "status": "pass", "findings": [], "evidence": "<evidence>" },
    { "phase": "quality", "status": "pass", "findings": [], "evidence": "<evidence>" }
  ],
  "diff_review": {
    "status": "not_applicable",
    "base_ref": "not_applicable",
    "head_ref": "not_applicable",
    "command": "not_applicable",
    "evidence": "not_applicable"
  },
  "verdict": "PASS",
  "status": "done",
  "blocked": false,
  "rationale": "<why pass>",
  "review_only": true,
  "blocking_reason": "not_applicable",
  "allowed_paths": ["<schema-paths-or-scopes>"],
  "review_loop": {
    "policy": "adaptive_min2_max3_second_pass_stable",
    "auditor_passes": 2,
    "orchestrator_self_passes": 2,
    "converged": true,
    "new_issues_found_in_last_audit_pass": false,
    "escalation_reason": "none"
  }
}
```

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

Auditor output contract (required):

- Timebox review work to **<= 120 seconds**. Do not perform open-ended exploration or redesign.
- Always set `verdict`:
  - `PASS`: accept the deliverable (`status="done"`, `blocked=false`).
  - `BLOCK`: reject due to concrete blockers (`status="awaiting_review"`, `blocked=true`, include `blockers`).
  - `NEEDS_EVIDENCE`: reject due to missing evidence (`status="awaiting_review"`, `blocked=true`, include `required_evidence`).
- Keep `blockers` to <= 3 and `required_evidence` to <= 5 (minimum needed to proceed).

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
- Enforce the repo-write gate: only `coder_*` may implement repo changes (no `apply_patch` / file edits by Orchestrator/Operator/Auditor).
- Use `awaiter` only as a waiting/polling helper (optional; prefer Orchestrator direct wait_any for short runs).
- Enforce windowed concurrency (spawn -> wait_any -> review -> replenish).
- Leaf agents do not interact with the user; any user checkpoint is Director-only.
- When uncertain, run a parallel Operator research fanout, synthesize options + assumptions, and return an Auditor-reviewable brief with a recommended safest default (avoid asking the user unless required).
- Default to `high` reasoning effort; use provider fallback only:
  - Availability fallback: `spark` -> `5.3-codex` (only when rate-limited / exhausted).
- Operator is single-tier by default (no provider fallback).
- Produce an integration report (conflict check + full verification command, when applicable).
