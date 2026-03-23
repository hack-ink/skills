---
name: workspaces
description: Use for any non-read-only development task that starts or resumes implementation in this repo unless the correct isolated lane is already active. Owns clone-backed `.workspaces/*` lane setup, reuse, and completed-lane cleanup of the workspace plus local and remote branches; does not own reconciliation, review, merge, or tracker closeout.
---

# Workspaces

## Scope

- This skill is the default entrypoint for non-read-only development tasks unless the correct isolated lane is already active.
- This skill owns lane setup, lane reuse, and completed-lane closeout.
- This skill does not own multi-lane reconciliation, review request/repair, merge execution, or tracker closeout.
- Keep the filesystem convention `.workspaces/*`. The skill name is shorter than the directory name on purpose.

Typical triggers:

- Start a non-read-only implementation task even when the user only asked for a fix, feature, or refactor
- Start a task in a clean branch-specific lane
- Resume implementation in an existing matching lane
- Close out a merged or explicitly abandoned lane
- Clean up a finished lane's workspace and branch state after `delivery-closeout`

## Core rule

- Default to one clone-backed `.workspaces/<lane>` lane per non-read-only implementation task, branch, and review stream unless the correct lane is already active.
- Prefer reusing an existing matching lane over creating a duplicate.
- Keep `.workspaces/` ignored.
- If a task explicitly needs a persisted `plan/1` artifact, create or update it from inside the active workspace so the plan stays in the same lane as the implementation.
- Do not leave task-local `docs/plans/...` artifacts behind in the primary checkout while implementation lives in a workspace lane.
- Use self-contained clone-backed workspaces, not linked shared-Git checkouts, when the lane itself needs to run `git add`, `git commit`, `git push`, or other Git writes under sandboxed execution.
- Run the repository's documented bootstrap and a fast baseline verification after creation.
- Treat closeout as part of task completion. A finished lane is not done until the workspace and branch state are clean.

## Lane model

Treat each `.workspaces/*` checkout as one independent lane:

- One task, branch, and review stream per workspace
- One agent or human owner at a time unless the lane is explicitly shared
- Keep unrelated fixes in separate workspaces even if they touch the same repository

Use separate workspaces by default when:

- Two tasks could land as separate PRs
- One lane may need to be paused, rebased, or abandoned without blocking another
- You want clean diffs and isolated verification per task

If the work is the same task or the same PR-sized change stream, you may stay on one branch and use other coordination methods inside that lane.

## Choose the directory

Use this priority order:

1. Reuse an existing project-local directory if `.workspaces/` or `workspaces/` already exists.
2. If the repository has scoped instructions (`AGENTS.md` or runtime-equivalent guidance), follow any stated workspace location convention.
3. If there is no existing convention, prefer `.workspaces/` only when it is already ignored or can be safely verified as ignored.
4. If neither a safe project-local directory nor a documented convention exists, ask the user where workspaces should live instead of inventing a global path.

Why `.workspaces/` instead of `.workspace/`:

- it holds multiple lane directories, so plural is clearer
- it mirrors common project-local hidden cache/layout conventions
- it avoids overloading singular `.workspace` names that other tools may already use

## Name the lane simply

Keep branch and directory naming predictable instead of encoding full ticket metadata into the path.

- Branch names should follow the repository's existing convention.
- Workspace directory names should stay short and single-segment.
- Prefer names that reveal the lane's task at a glance.

Examples:

- Branch `feat/cache-invalidation`, directory `feat-cache-invalidation`
- Branch `fix/login-timeout`, directory `fix-login-timeout`
- Branch `chore/release-notes`, directory `chore-release-notes`

If multiple agents or attempts work on the same broad task, keep the branch task-focused and only suffix the directory when needed, for example `feat-cache-invalidation-a` and `feat-cache-invalidation-b`.

## Safety checks before creation

Run these checks before creating the workspace:

```bash
git branch --list <branch-name>
```

If using a project-local directory, verify that it is ignored:

```bash
git check-ignore -q .workspaces || git check-ignore -q workspaces
```

If the intended local directory is not ignored:

- Do not silently proceed.
- Add or adjust ignore rules only when that repo change is in scope.
- Otherwise stop and ask the user how they want workspaces stored.

## Create or reuse the workspace

Basic flow:

```bash
repo_root="$(git rev-parse --show-toplevel)"
branch_name="<branch-name>"
workspace_dir_name="<single-segment-dir-name>"
workspace_path="$repo_root/.workspaces/$workspace_dir_name"

if [ -d "$workspace_path/.git" ]; then
  cd "$workspace_path"
  git status --short
  git rev-parse --abbrev-ref HEAD
  exit 0
fi

git clone --no-checkout . "$workspace_path"

origin_url="$(git -C "$repo_root" remote get-url origin 2>/dev/null || true)"
if [ -n "$origin_url" ]; then
  git -C "$workspace_path" remote set-url origin "$origin_url"
fi

git -C "$workspace_path" checkout -B "$branch_name" HEAD
cd "$workspace_path"
```

If the branch name contains `/`, flatten it when choosing `workspace_dir_name` so the workspace still sits directly under `.workspaces/`. For example, branch `feature/foo` can use workspace directory `feature-foo`.

After creation, prove that the workspace is self-contained before handing it to another agent or sandbox:

```bash
git -C "$workspace_path" rev-parse --path-format=absolute --git-dir
git -C "$workspace_path" rev-parse --path-format=absolute --git-common-dir
```

Both paths should resolve inside `"$workspace_path"`. If either path escapes the lane root, stop and fix the workspace backend instead of letting the child lane discover it later during `git add`.

## Bootstrap and baseline

After creation:

1. Read the repository instructions first.
2. Run the repo-native bootstrap command, not a generic guess.
3. Run a baseline verification command that is fast enough to establish a clean starting point.

Examples:

- Rust: documented `cargo make ...`, `cargo xtask ...`, or a scoped `cargo check` / `cargo test` gate
- Node: documented package-manager install plus the repo's quick validation command
- Python: documented environment bootstrap plus the repo's smoke or test command

Do not automatically run the heaviest full-suite command if the repository already documents a lighter baseline gate.

## Outputs

- `workspace_ready` - created a new lane and verified it is usable.
- `workspace_reused` - reused an existing lane with matching task intent.
- `workspace_closed` - finished closeout and reached the default clean target state.
- `workspace_retained` - lane intentionally kept because the task is paused, blocked, or not actually complete.
- `warned` - local cleanup succeeded but some non-fatal cleanup target, usually the remote branch, could not be removed.
- `blocked` - setup or closeout stopped because a hard gate failed.

## Closeout / Teardown

- Closeout is only valid when the task is truly complete or explicitly abandoned.
- Valid closeout states:
  - PR merged and `delivery-closeout` already ran or was explicitly not needed
  - task explicitly abandoned or cancelled with approval to clean up the lane
- Do not clean up a lane that is still in review, still awaiting external action, or still carrying unresolved local investigation.

Before removal, inspect and prove the current state:

```bash
git -C "$workspace_path" status --short
git -C "$workspace_path" rev-parse --abbrev-ref HEAD
git -C "$workspace_path" remote get-url origin
```

If the lane is expected to be merged, discover the repo-appropriate integration branch from repo policy, PR/base-branch context, or Git metadata. Only stop and ask when multiple plausible target branches remain or the discovered target conflicts with lane intent.

Then verify it is not carrying unique commits:

```bash
git -C "$workspace_path" branch --merged <target-branch>
git -C "$workspace_path" log <target-branch>..<branch-name>
```

If there is no merge-base, compare divergence explicitly instead of guessing:

```bash
git -C "$workspace_path" rev-list --count <target-branch>..<branch-name>
git -C "$workspace_path" rev-list --count <branch-name>..<target-branch>
```

- If the workspace contains uncommitted edits, stop and inspect them before removal.

Remote-branch check:

```bash
git -C "$workspace_path" ls-remote --heads origin "$branch_name"
```

Teardown flow:

1. Verify the lane outcome and the unique-commit state.
2. If the same branch also exists in the primary checkout, delete that local branch there once it is safe and not currently checked out.
3. If the remote branch still exists and the task is complete, delete it:
   - `git -C "$workspace_path" push origin --delete "$branch_name"`
4. If the remote branch is already absent, record that it was auto-deleted or already cleaned up.
5. Fast-forward the primary checkout's integration branch to the latest upstream state before claiming full closeout:
   - require the primary checkout worktree to be clean
   - if the primary checkout is not already on `<target-branch>`, switch to it only after confirming the checkout is clean
   - `git -C "$repo_root" fetch origin "$target_branch"`
   - `git -C "$repo_root" pull --ff-only origin "$target_branch"`
6. Remove the workspace directory with `rm -rf "$workspace_path"` only after showing the dirty state and unique-commit risk.

Default closeout target state:

- `.workspaces/<lane>` does not exist
- the lane-local branch disappears with the clone-backed workspace
- any same-named local branch in the primary checkout is absent
- the primary checkout is on the integration branch and fast-forwarded to the latest upstream state
- the remote branch is absent

If remote branch deletion fails because of branch protection, platform policy, or network failure, return `warned` instead of falsely claiming a fully clean closeout.

## Red flags

- Creating a project-local workspace without verifying the directory is ignored
- Running a generic bootstrap command while ignoring repo instructions
- Treating a clone-backed workspace as if it still shared Git administrative state with the original checkout
- Using linked shared-Git checkouts for sandboxed child lanes that must perform lane-local Git writes
- Claiming a lane is fully closed while the remote branch still exists without recording whether GitHub auto-deleted it or deletion failed
