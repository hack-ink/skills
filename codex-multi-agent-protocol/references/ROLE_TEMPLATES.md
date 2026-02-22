# Role Templates (v2)

This document provides copy-pastable templates for the 4-role workflow:

- Director (main)
- Auditor
- Orchestrator
- Implementer

Goal: keep runs fast while preserving reliability via explicit contracts, evidence, and rerun escalation.

## Implementer `task_contract` template (write)

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

Implementer output checklist:

- List touched file paths (or `not_applicable`).
- Provide concrete verification evidence (stdout snippets or exit codes).
- Call out any assumptions or blockers.

## Implementer `task_contract` template (read_only research)

Use for research that feeds decisions.

- **goal**: <what decision this research supports>
- **scope**: <topics + boundaries>
- **constraints**:
  - Do not include sensitive internal identifiers in queries.
  - Use 3+ independent sources when feasible; prefer primary docs.
  - Label hypotheses vs verified facts.
- **expected_output**:
  - 3–7 bullets of findings.
  - Evidence map: claim -> evidence -> source link.
  - Open questions + what would resolve them.
- **non_goals**: <explicit exclusions>

## Auditor (spec -> quality) checklists

### Spec phase (must pass first)

- Is the implementer output aligned with the `task_contract` goal and scope?
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
- Enforce windowed concurrency (spawn -> wait_any -> review -> replenish).
- Default to `high` reasoning effort; use provider fallback only:
  - Availability fallback: `spark` -> `5.3-codex` (only when rate-limited / exhausted).
- Produce an integration report (conflict check + full verification command, when applicable).
