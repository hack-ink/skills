---
name: git-worktrees
description: Use when starting feature work that benefits from branch isolation, independent parallel implementation lanes, or a disposable workspace. Creates Git worktrees with directory selection, ignore verification, repo-native bootstrap, lane naming guidance, and Rust-aware cache guidance for large local builds.
---

# Git Worktrees

## Purpose

Use Git worktrees when you need an isolated branch checkout without disturbing the current workspace.

Typical triggers:

- Multiple unrelated implementation tasks or PR-like streams on the same repository
- Parallel feature work on the same repository
- Executing a plan in a clean branch-specific workspace
- Hotfix work while the current tree is dirty or mid-refactor
- Large Rust repos where branch isolation is useful but repeated setup cost matters

## Core rule

- Prefer an existing worktree layout over inventing a new one.
- When work is independent, default to one worktree per task lane instead of mixing unrelated changes in one branch or one agent run.
- Keep project-local worktree directories ignored.
- Use `git worktree` subcommands for lifecycle operations; do not create, move, or delete worktrees by hand unless recovery is required.
- Run the repository's documented bootstrap and baseline verification after creation.

## Lane model

Treat each worktree as one independent lane:

- One task, branch, and review stream per worktree
- One agent or human owner at a time unless the lane is explicitly shared
- Keep unrelated fixes in separate worktrees even if they touch the same repository

Use separate worktrees by default when:

- Two tasks could land as separate PRs
- One lane may need to be paused, rebased, or abandoned without blocking another
- You want clean diffs and isolated verification per task

If the work is the same task or the same PR-sized change stream, you may stay on one branch and use other coordination methods inside that lane.

## Choose the directory

Use this priority order:

1. Reuse an existing project-local directory if `.worktrees/` or `worktrees/` already exists.
2. If the repository has scoped instructions (`AGENTS.md` or runtime-equivalent guidance), follow any stated worktree location convention.
3. If there is no existing convention, prefer `.worktrees/` only when it is already ignored or can be safely verified as ignored.
4. If neither a safe project-local directory nor a documented convention exists, ask the user where worktrees should live instead of inventing a global path.
5. If you rely on the repo-root shared `target/` convention below, the worktree directory name must be a single path segment even when the Git branch name contains `/`.

## Name the lane simply

Keep branch and directory naming predictable instead of encoding full ticket metadata into the path.

- Branch names should follow the repository's existing convention.
- Worktree directory names should stay short and single-segment.
- Prefer names that reveal the lane's task at a glance.

Examples:

- Branch `feat/cache-invalidation`, directory `feat-cache-invalidation`
- Branch `fix/login-timeout`, directory `fix-login-timeout`
- Branch `chore/release-notes`, directory `chore-release-notes`

If multiple agents or attempts work on the same broad task, keep the branch task-focused and only suffix the directory when needed, for example `feat-cache-invalidation-a` and `feat-cache-invalidation-b`.

## Safety checks before creation

Run these checks before `git worktree add`:

```bash
git worktree list --porcelain
git branch --list <branch-name>
```

If using a project-local directory, verify that it is ignored:

```bash
git check-ignore -q .worktrees || git check-ignore -q worktrees
```

If the intended local directory is not ignored:

- Do not silently proceed.
- Add or adjust ignore rules only when that repo change is in scope.
- Otherwise stop and ask the user how they want worktrees stored.

## Create the worktree

Basic flow:

```bash
repo_root="$(git rev-parse --show-toplevel)"
branch_name="<branch-name>"
worktree_dir_name="<single-segment-dir-name>"
worktree_path="$repo_root/.worktrees/$worktree_dir_name"
git worktree add -b "$branch_name" "$worktree_path"
cd "$worktree_path"
```

Prefer `git worktree add -b <branch>` when creating a fresh branch for the task.

If the branch name contains `/`, flatten it when choosing `worktree_dir_name` so the worktree still sits directly under `.worktrees/`. For example, branch `feature/foo` can use worktree directory `feature-foo`.

If the branch already exists and is not checked out elsewhere, use:

```bash
git worktree add "$worktree_path" "$branch_name"
```

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

## Git features worth using

### Per-worktree Git config

If you need Git settings that should differ by worktree, enable the official worktree config extension and write them with `--worktree`:

```bash
git config extensions.worktreeConfig true
git config --worktree <key> <value>
```

Use this for worktree-local Git behavior. Do not use it as a substitute for repository configuration.

### Relative paths for portable worktrees

If the repository or parent directory may be moved, relative worktree links are useful:

```bash
git config worktree.useRelativePaths true
```

Or pass `--relative-paths` when creating the worktree.

Only do this when the team is on a Git release that supports relative worktrees.

### Lock worktrees on removable or intermittently mounted storage

If a worktree lives on an external disk or network share, lock it so Git does not prune its administrative files:

```bash
git worktree lock --reason "<why>"
```

### Repair moved worktrees

If a worktree or the main repository was moved manually and Git can no longer find it, prefer:

```bash
git worktree repair
```

## Rust guidance

### What happens to `target/`

- `git worktree add` checks out tracked files. It does not copy untracked build output such as `target/`.
- A fresh Rust worktree therefore starts without a `target/` directory unless you create one later.
- By default, Cargo writes build output to `<workspace-root>/target`, so each worktree gets its own build directory and disk usage can multiply quickly.

### Required approach

1. If active development happens inside `.worktrees/<worktree-dir-name>`, treat shared Rust build output as a worktree-local temporary patch.
2. Use `build.target-dir` as the primary mechanism.
3. Keep the target directory project-local.
4. Do not commit this patch to `main` or any branch that will be merged unchanged.

Temporary patch example:

```toml
# .cargo/config.toml
[build]
target-dir = "../../target"
```

### Path-resolution constraint

- A tracked `.cargo/config.toml` is checked out into every linked worktree.
- Relative `build.target-dir` paths are therefore resolved from each checkout's own root, not from Git's common directory.
- That means a `.worktrees/<worktree-dir-name>`-specific path such as `../../target` must **not** be committed as a repository-wide default.
- The `../../target` example assumes the worktree root is exactly one level below `.worktrees/`, so keep the worktree directory name to a single path segment when using this convention.
- For the `.worktrees` layout, keep this as a local temporary patch inside the worktree where it is needed.

### Practical recommendation for Rust repos

- When developing inside `.worktrees/<worktree-dir-name>`, patch `.cargo/config.toml` locally in that worktree.
- If the repository already tracks `.cargo/config.toml`, leave the worktree-only change uncommitted.
- If the repository does not track `.cargo/config.toml`, you may create it locally in the worktree, but do not `git add` it unless the user explicitly asks for a repo-wide policy change.
- If the repository has branch-specific generated outputs that clash often, reconsider whether full `target` sharing is worth the contention cost before enabling it.

### `.worktrees` convention

- If active development happens inside `.worktrees/<worktree-dir-name>`, do **not** copy `target/` into the linked worktree.
- Instead, always point Cargo's output directory back at the repository-root `target/` directory.
- In this skill, "build directory" means Cargo's `build.target-dir`, not `build.build-dir`.
- For that layout, the required setting from the linked worktree root is:

```toml
[build]
target-dir = "../../target"
```

- This convention is for linked worktrees that live directly under `.worktrees/` only. Do not assume the same relative path is correct for the main checkout or for nested worktree paths.
- Before creating a commit or PR from the worktree, make sure this temporary patch is not included unless the user explicitly requested a repository-wide Rust build policy change.

## Closeout / Teardown

Use this when a lane is merged, intentionally abandoned, or paused long enough that the checkout should be reclaimed.

Before removal:

- Confirm the lane outcome first: merged, intentionally abandoned, or explicitly paused.
- Inspect the current state:

```bash
git status --short
git rev-parse --abbrev-ref HEAD
```

- If the lane is expected to be merged, first discover the repo-appropriate, up-to-date integration branch for that lane from repo policy, PR or base-branch context, or Git metadata. Only stop and confirm if multiple plausible target branches remain or the discovered target conflicts with lane intent.
- Then verify it is not carrying unique commits. Prefer checks such as:

```bash
git branch --merged <target-branch>
git log <target-branch>..<branch-name>
```

- If the worktree contains uncommitted edits, stop and inspect them before any force removal.
- For Rust lanes under `.worktrees/<worktree-dir-name>`, make sure the worktree-only `.cargo/config.toml` patch (for example `target-dir = "../../target"`) is not staged or committed unless the user explicitly requested a repository-wide policy change.

Teardown flow:

1. Remove the worktree with `git worktree remove <path>`.
2. Only use `--force` after showing the dirty state and unique-commit risk.
3. If the branch is no longer needed, delete it separately from another checkout with `git branch -d <branch-name>`.
4. If Git still reports stale administrative entries, use `git worktree prune` only after verifying the missing path is truly gone.

Notes:

- Worktree removal does not delete branch refs automatically.
- Do not delete the shared repo-root `target/` directory just because one Rust lane finished; other lanes or the main checkout may still rely on it.

## Red flags

- Creating a project-local worktree without verifying the directory is ignored
- Running a generic bootstrap command while ignoring repo instructions
- Treating a worktree as "copied state" from the original checkout
- Assuming Rust `target/` is shared automatically
- Deleting a worktree directory with plain `rm -rf` instead of `git worktree remove`
