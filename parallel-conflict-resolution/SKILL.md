---
name: parallel-conflict-resolution
description: Use when reconciling merge, rebase, or cherry-pick conflicts across parallel worktrees or independent branches. Covers conflict triage, preserving uncommitted work, choosing a reconciliation strategy, and verification before closeout.
---

# Parallel Conflict Resolution

## Purpose

Resolve conflicts between parallel lanes without losing work or guessing at the right integration strategy.

Typical triggers:

- A merge or rebase stops with conflicts
- A cherry-pick only partially applies
- Two worktrees or branches evolved the same files differently
- Parallel task lanes need to be reconciled or re-split before review

## Core rule

- Inspect the current state first: do not start editing conflict markers blindly.
- Detect the Git operation state automatically before editing conflicted files. This is an AI-side probe, not a default reason to ask the user.
- Preserve uncommitted work before changing strategy.
- Choose the reconciliation method that matches the lane relationship instead of defaulting to merge-everything.
- Treat generated artifacts, lockfiles, codegen outputs, and build outputs as tooling-owned: when the repo exposes a canonical regeneration path, reconcile the source inputs and rerun that command instead of editing the generated file by hand.
- Verify the final integrated state before claiming the lane is ready.

## Triage first

Run the smallest commands that tell you what kind of conflict you have:

```bash
git status --short
git rev-parse --abbrev-ref HEAD
git diff --name-only --diff-filter=U
git rev-parse -q --verify MERGE_HEAD
git rev-parse -q --verify CHERRY_PICK_HEAD
git rev-parse -q --verify REBASE_HEAD
```

Then inspect the conflicted files and the operation in progress:

```bash
[ -d "$(git rev-parse --git-path rebase-merge)" ] || \
[ -d "$(git rev-parse --git-path rebase-apply)" ]
git status
git ls-files -u
```

Interpret the probe before editing:

- `MERGE_HEAD` present: treat the operation as `merge`.
- `CHERRY_PICK_HEAD` present: treat the operation as `cherry-pick`.
- `REBASE_HEAD` present, or `rebase-merge` / `rebase-apply` exists via `git rev-parse --git-path ...`: treat the operation as `rebase`.
- No operation marker but unresolved files remain: treat this as an unresolved index state. Continue analysis, but do not assume a specific `--continue` / `--abort` flow without more evidence.
- Ask the user only when the operation state stays ambiguous or the intended reconciliation strategy cannot be inferred safely.

If needed, read the relevant patch or branch delta before choosing a fix:

```bash
git diff --merge
git log --oneline --left-right --cherry <upstream>...HEAD
```

## Preserve work before strategy changes

- If the tree contains manual resolution progress you may need later, copy the conflicted files or create a patch before aborting.
- If unrelated local edits exist, stash or move them out of the way before retrying.
- Do not run `git reset --hard` or delete a worktree to "start fresh" unless the user explicitly approved that loss.

Use official abort/quit flows when backing out of an in-progress operation:

```bash
git merge --abort
git rebase --abort
git cherry-pick --abort
```

## Pick the right reconciliation path

Choose deliberately:

- `rebase`: use when one lane should be replayed onto the newer base and you want a linear task history.
- `cherry-pick`: use when only a subset of commits should cross lanes.
- `merge`: use when both branch histories should remain intact and the target branch accepts merge commits.
- Manual resolution in place: use when the current operation is otherwise correct and only file-level conflicts need settlement.
- Re-split the work: use when the conflict exists because two lanes mixed unrelated concerns and the cleanest fix is to separate commits differently.

Good heuristics:

- If one branch is clearly the destination lane, rebase or cherry-pick toward it.
- If commits are entangled and repeated conflicts keep appearing, stop and re-split before stacking more fixes.
- If generated files dominate the conflict, resolve the source-of-truth inputs first and rerun the repo's canonical generation command. Do not hand-merge build output, lockfiles, or codegen artifacts.

## Resolve carefully

- Read each conflicted hunk against both sides and the surrounding function or section.
- Prefer keeping intent, not just both text blocks.
- Remove conflict markers completely.
- Re-check with `git diff --name-only --diff-filter=U` until no unresolved files remain.

For repeated conflict-heavy files, compare against each side explicitly:

```bash
git show :1:path/to/file
git show :2:path/to/file
git show :3:path/to/file
```

## Verify before closeout

After resolving:

1. Confirm the operation state is clean enough to continue.
2. If any generated artifacts, lockfiles, or codegen outputs were involved, rerun the canonical regeneration/sync command before verification.
3. Run the repo's scoped verification for the touched area.
4. Review the resulting diff to ensure no accidental lane bleed-through remains.

Minimum checks:

```bash
git status --short
git diff --stat
```

Then run the repo-native test, build, or lint command that covers the reconciled files.

## Red flags

- Resolving conflicts without first identifying whether the operation is a merge, rebase, or cherry-pick
- Aborting an operation after making useful manual edits without preserving them
- Combining unrelated lanes just to make the conflict disappear
- Manually resolving generated files, lockfiles, codegen outputs, or build outputs instead of rerunning the canonical regeneration path
- Claiming the conflict is fixed before `git status` and repo-native verification say so
