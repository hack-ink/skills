---
name: pre-commit
description: Use when preparing a commit or push and repo-specific pre-commit checks are required.
---

# Pre-commit

## Scope

- This skill is path-conditional and runs only the commands explicitly required by the repository layout.

## Hard gate

Do not run `git commit` or `git push` until you have produced a **Pre-commit report** (see template below) that includes:

- Every command you ran (or explicitly skipped)
- The exact exit code for each command you ran
- A clear skip reason for each skipped gate

If a gate is not applicable, record it as `skipped` with a reason and do not invent substitute commands.

This repository also requires commit messages to follow the `cmsg/1` schema (single-line JSON). Do not use free-form commit messages.

Note: Some checks are **manual reviews** and may not have an exit code. For these, record:

- What you scanned/read (files/paths)
- Your conclusion (impact/no-impact/unclear + risk)

## Always-run preflight (evidence)

Run these commands and record their exit codes in the report:

- `git status --porcelain`
- `git diff --stat`

## Commit message gate (required)

Before committing, draft a commit message that is:

- A single-line JSON object (no leading/trailing text)
- `schema` is exactly `cmsg/1`
- Contains these keys: `schema,type,scope,summary,intent,impact,breaking,risk,refs`

Minimum type/shape constraints:

- `breaking`: boolean
- `refs`: array (can be empty)
- `risk`: one of `low`, `medium`, `high`

Recommended message generator (prints a single-line JSON message):

- Skill scripts live under this skill's directory (the folder containing this `SKILL.md`).
- Locate that directory via the runtime's skills list and set `PRE_COMMIT_HOME` to it before running these commands.
- `python3 "$PRE_COMMIT_HOME/scripts/cmsg.py" --type <type> --scope <scope> --summary <summary> --intent <intent> --impact <impact> --risk <low|medium|high>`

Local validation (required; record exit code in the report):

- `python3 "$PRE_COMMIT_HOME/scripts/validate_cmsg.py"`

Fallback validation (use only if the script is unavailable; record exit code in the report):

- `python -c 'import json,sys; o=json.loads(sys.stdin.read()); req=\"schema type scope summary intent impact breaking risk refs\".split(); missing=[k for k in req if k not in o]; assert not missing, missing; assert o[\"schema\"]==\"cmsg/1\"; assert isinstance(o[\"breaking\"], bool); assert isinstance(o[\"refs\"], list); assert o[\"risk\"] in (\"low\",\"medium\",\"high\")'`

## Steps

1. `Makefile.toml` exists at repo-root?
    - If present, run **exactly** in this order:
        - `cargo make lint-fix`
        - `cargo make fmt`
        - `cargo make test`
    - If not present, record that the Makefile.toml gate is not applicable and skip this section.

2. `docs/` directory exists at repo-root?
    - If present, perform a **documentation impact review**:
        - Check whether this change requires docs updates (user-facing behavior, config/env vars, CLI, APIs, runbooks).
        - If docs were edited, sanity-check that the edits match the change.
        - If docs were not edited, record why (no docs impact vs. missed update) and the resulting risk.
    - If the repository documents an exact docs-validation command, you may run it, but it is not required. Default to reading/scanning relevant docs content.

3. `.github/workflows/` directory exists at repo-root?
    - If present, perform a **workflow impact review**:
        - Scan workflow definitions to understand what checks CI will run.
        - Use the local commands you already ran (and their results) to infer whether this change is likely to impact CI.
        - If the change plausibly affects CI but your local runs do not cover it, record the gap and risk (and optionally run additional local checks if they are clearly justified).
    - Do not auto-run workflows or use `gh` watchers as a substitute for CI.

`lint-fix` may change files, so keep `fmt` and `test` tied to the same local state.

## Outputs

- Produce a Pre-commit report with the following structure:

```
Pre-commit report

Preflight
- `git status --porcelain` (exit: <code>)
- `git diff --stat` (exit: <code>)

Commit message
- proposed: `<single-line cmsg/1 JSON>`
- validation: ran | skipped: <reason>
  - `python3 "$PRE_COMMIT_HOME/scripts/validate_cmsg.py"` (exit: <code> | n/a)
  - fallback: `python -c '...'` (exit: <code> | n/a)

Repo gates
- Makefile.toml gate: ran | skipped: <reason>
  - `cargo make lint-fix` (exit: <code> | n/a)
  - `cargo make fmt` (exit: <code> | n/a)
  - `cargo make test` (exit: <code> | n/a)
- docs review: done | skipped: <reason>
  - scanned/read: <paths/files>
  - conclusion: <no-impact|impact|unclear> (risk: <low|medium|high>)
- workflows review: done | skipped: <reason>
  - scanned: <paths/files>
  - conclusion: <no-impact|impact|unclear> (risk: <low|medium|high>)
```
