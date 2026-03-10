# git-worktrees (Dev-only)

This directory contains development-only artifacts for the `git-worktrees` skill. It is intentionally kept outside the installable skill directory so installations do not include smoke tests or local policy fixtures.

## Quick smoke

From the repo root:

```sh
python3 dev/git-worktrees/run_smoke.py
```

This smoke entrypoint creates a temporary Git repository and validates the current lifecycle policy end-to-end:

- `.worktrees/<single-segment>` layout with a slash branch name
- ignored local worktree directory
- lane commit and merge
- `git worktree remove` plus `git worktree prune`
- no stale worktree entry after closeout
