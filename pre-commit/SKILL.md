---
name: pre-commit
description: Use when you are about to commit or push in a hack-ink repository that uses a Makefile.toml lint/format/test gate and requires docs-sync and GitHub Actions verification.
---

# Pre-commit

## Scope

- This skill is for hack-ink repositories where `Makefile.toml` is required.

## Steps

1. Before every commit, run full checks. **All tests must pass.**
   - Check `Makefile.toml` exists and confirm it defines tasks `lint-fix`, `fmt`, and `test`.
   - Run the commands in this exact order:
     - `cargo make lint-fix`
     - `cargo make fmt`
     - `cargo make test`

2. Verify staged docs coverage before proceeding (mandatory):
   - Stage code/config changes as normal.
   - If there are staged non-doc changes, require corresponding staged docs changes in `docs/` (excluding `docs/plan/**`).
   - If no such docs changes are staged, stop and require either:
     - staging the missing docs updates, or
     - explicit confirmation that docs updates are intentionally not needed for this commit.
   - Example:
     - `git diff --cached --name-only | grep -v '^docs/'` (staged non-doc files)
     - `git diff --cached --name-only -- docs/ | grep -v '^docs/plan/'` (staged docs files, excluding plan docs)

3. After push, verify CI is green before considering work complete:
   - `CURRENT_SHA="$(git rev-parse HEAD)"`
   - `gh` preferred:
     - `RUN_ID=$(gh run list --json id,headSha --limit 50 --jq '.[] | select(.headSha == "'"${CURRENT_SHA}"'") | .id' | head -n 1)`
     - `if [ -z "${RUN_ID}" ]; then echo "No GitHub Actions run found for ${CURRENT_SHA}; verify manually in Actions UI."; else gh run watch --exit-status "${RUN_ID}"; fi`
   - Manual fallback tied to HEAD:
     - `echo "Open your repository Actions page and confirm workflows for ${CURRENT_SHA} are successful."`

`lint-fix` may change code, so formatting must follow to keep a stable diff, and tests must run after both to validate the final result.

## Outputs

- Commands and exit codes: run `cargo make lint-fix`, `cargo make fmt`, `cargo make test`.
- Docs sync evidence (staged checks):
  - `NON_DOC_FILES=$(git diff --cached --name-only | grep -v '^docs/')`
  - `DOC_FILES=$(git diff --cached --name-only -- docs/ | grep -v '^docs/plan/')`
  - Include `NON_DOC_FILES` and `DOC_FILES`; when `NON_DOC_FILES` is non-empty, `DOC_FILES` must be non-empty (excluding `docs/plan/**`).
- Post-push CI evidence (for `CURRENT_SHA`):
  - Capture and record `${RUN_ID}` and watch result (`gh run list`, `gh run watch --exit-status`) when available.
  - If `RUN_ID` is empty, record manual verification note that actions for `${CURRENT_SHA}` were checked in the UI.
- Working-tree summary: run and record `git status` and `git diff --stat`.
