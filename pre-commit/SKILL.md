---
name: pre-commit
description: Use when you are about to commit (or push) in a hack-ink repository that requires a Makefile.toml-based lint/format/test gate.
---

# Pre-commit

## Scope

- This skill is for hack-ink repositories where `Makefile.toml` is required.

## Steps

1. Check `Makefile.toml` exists and confirm it defines tasks `lint-fix`, `fmt`, and `test`.
2. Run the commands in this exact order:
    - `cargo make lint-fix`
    - `cargo make fmt`
    - `cargo make test`

`lint-fix` may change code, so formatting must follow to keep a stable diff, and tests should run after both to validate the final result.

## Outputs

- Commands run: `cargo make lint-fix`, `cargo make fmt`, `cargo make test`
- Exit codes for each command.
- Working-tree summary: `git status` and `git diff --stat`.
