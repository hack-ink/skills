# workspaces (Dev-only)

This directory contains development-only artifacts for the `workspaces` skill. It is intentionally kept outside the installable skill directory so installations do not include smoke tests or local policy fixtures.

## Quick smoke

From the repo root:

```sh
python3 dev/workspaces/run_smoke.py
```

This smoke entrypoint creates a temporary Git repository and validates the current lifecycle policy end-to-end:

- `.workspaces/<single-segment>` layout with a slash branch name
- lane-local planning artifacts instead of plans stranded in the primary checkout
- ignored local workspace directory
- self-contained Git metadata inside the workspace
- lane commit, push, merge, and remote branch cleanup
- primary checkout fast-forward sync to the integration branch
- local branch cleanup in the primary checkout
- direct workspace-directory teardown after merge
- no accidental shared-Git lane registration for the workspace
