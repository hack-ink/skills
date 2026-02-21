---
name: pre-commit
description: Trigger when preparing a commit where repo-specific pre-commit checks are required.
---

# Pre-commit

## Scope

- This skill is path-conditional and runs only the commands explicitly required by the repository layout.

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

## Outputs

- For each section above, report:
    - Command executed and exact arguments.
    - Whether it ran or was skipped (with reason for each skip).
    - Exit code for each command.
- If `Makefile.toml` exists:
    - `cargo make lint-fix` exit code
    - `cargo make fmt` exit code
    - `cargo make test` exit code
- If `docs/` exists and has an explicitly documented command:
    - document-check command + exit code
- If `.github/workflows/` exists and has an explicitly documented command:
    - workflow-check command + exit code
- If docs or workflow command is skipped:
    - add explicit skip reason (e.g. `docs/check command not explicitly documented`; `workflow check command not explicitly documented`).
