---
name: pre-commit
description: Trigger when preparing a commit where repo-specific pre-commit checks are required.
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

## Always-run preflight (evidence)

Run these commands and record their exit codes in the report:

- `git status --porcelain`
- `git diff --stat`

If the repository has a “no CJK characters” policy, also run:

- `rg -n \"[\\x{4E00}-\\x{9FFF}]\" -S .`

Note: `rg` exits with `0` when matches are found, `1` when no matches are found, and `2` on errors. Record the exit code and interpret it correctly.

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

- `python3 pre-commit/scripts/cmsg.py --type <type> --scope <scope> --summary <summary> --intent <intent> --impact <impact> --risk <low|medium|high>`

Local validation (required; record exit code in the report):

- `python3 pre-commit/scripts/validate_cmsg.py`

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
    - If present, run docs checks only when the repository explicitly documents one exact command for docs validation.
        - If an exact command is documented, run that exact command.
        - If no exact command is documented, skip docs checks and record that docs validation is not defined.
    - Do not infer or auto-detect docs commands.

3. `.github/workflows/` directory exists at repo-root?
    - If present, run workflow checks only when the repository explicitly documents one exact command.
        - If an exact command is documented, run that exact command.
        - If no exact command is documented, skip workflow checks and record that workflow verification is not defined.
    - Do not auto-detect workflow runs or use `gh` CLI watchers.

`lint-fix` may change files, so keep `fmt` and `test` tied to the same local state.

## Push hygiene (do not bypass policies by accident)

- Prefer pushing a feature branch and opening a PR.
- Do not force-push unless the user explicitly asked for it and you have confirmed the target ref.

## Outputs

- Produce a Pre-commit report with the following structure:

```
Pre-commit report

Preflight
- `git status --porcelain` (exit: <code>)
- `git diff --stat` (exit: <code>)
- `rg -n \"[\\x{4E00}-\\x{9FFF}]\" -S .` (exit: <code> (0=matches, 1=none, 2=error) | skipped: <reason>)

Commit message
- proposed: `<single-line cmsg/1 JSON>`
- validation: ran | skipped: <reason>
  - `python3 pre-commit/scripts/validate_cmsg.py` (exit: <code> | n/a)
  - fallback: `python -c '...'` (exit: <code> | n/a)

Repo gates
- Makefile.toml gate: ran | skipped: <reason>
  - `cargo make lint-fix` (exit: <code> | n/a)
  - `cargo make fmt` (exit: <code> | n/a)
  - `cargo make test` (exit: <code> | n/a)
- docs gate: ran | skipped: <reason>
- workflows gate: ran | skipped: <reason>
```
