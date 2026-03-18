---
name: review-request
description: Use after a PR exists and `review-prepare` has converged to request Codex review on the pushed branch. Owns review request gating for non-draft PRs with a clean workspace and fresh verification evidence; does not repair comments or merge.
---

# Review Request

## Scope

- This skill owns the PR review request step.
- Default meaning is a Codex review request on an existing PR.
- This skill does not repair comments, resolve threads, merge the PR, or close out trackers.

## Inputs

- PR URL or PR number
- Head SHA
- Optional review summary or scope

## Outputs

- Emit a machine-readable result envelope with these required fields:
  - `status`: one of `review_requested`, `blocked`
  - `head_sha`: exact branch head SHA the review request applies to
  - `pr_ref`: stable PR identity such as URL or number
  - `evidence`: ordered list of verification or gating evidence strings for that head; use `[]` when no additional evidence is available

## Hard gates

- The PR must already exist.
- The PR must be non-draft.
- The branch must already be pushed.
- The workspace must be clean.
- The current head must have fresh verification evidence.
- `review-prepare` must already be clean for this branch state.
- The requested review must be explicitly bound to the same head SHA that was verified through the stable `head_sha` field.

## Procedure

1. Confirm the PR target and current head SHA.
2. Verify that the branch is pushed and the PR is not draft.
3. Confirm the working tree is clean:
   - `git status --short`
4. Confirm fresh verification evidence exists for the current head.
5. Request Codex review through the current repo-approved review entrypoint.
6. Emit the machine-readable result envelope with `status`, `head_sha`, `pr_ref`, and `evidence`.
7. Treat any later branch head change as invalidating this request for downstream gate purposes until a new request is sent for the new head.

## Hand-off

- After the request is sent, waiting and re-entry belong to orchestration.
- When review comments arrive, switch to `review-repair`.
- If the branch changes and another round is needed, come back here explicitly.

## Red flags

- Requesting review on a draft PR
- Requesting review before the branch is pushed
- Requesting review from a dirty workspace
- Treating this skill as if it owns the repair loop or merge decision
