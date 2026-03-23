---
name: review-prepare
description: Use before creating or refreshing a PR head, including after `review-repair` changes the branch, to run the primary self-review gate on the actual diff. Wraps the shared `review-loop` mechanics for branch-readiness review and maps that result onto pre-PR go/no-go status.
---

# Review Prepare

## Scope

- This skill owns the primary self-review gate for branch readiness.
- This skill wraps `review-loop` for the actual diff and maps the shared loop result onto pre-PR branch-readiness status.
- This skill decides whether the branch is clean enough to proceed without any known owned review debt.
- This skill does not create a PR, handle external-review threads, merge, or close out trackers.

## Inputs

- Current diff or branch range
- Current head SHA
- Requirements source
- `plan/1` path when the task is plan-backed
- Verification commands for the touched area

## Outputs

- Emit a machine-readable result envelope with these required fields:
  - `status`: one of `no_findings`, `findings`, `needs_architecture_review`, `blocked`
  - `head_sha`: exact reviewed head SHA that this decision applies to
  - `evidence`: ordered list of verification or review evidence strings for that head; use `[]` when no fresh verification evidence exists yet

Every emitted result must use the stable `head_sha` field name for the reviewed branch state. Do not hide the reviewed SHA only inside prose.

## Hard gates

- Run `review-loop` on the actual diff instead of inventing a second local review engine here.
- Do not output `no_findings` unless `review-loop` reached `clean` for the current head.
- Do not output `no_findings` while any known owned issue remains on the current head, even if it is a small or obvious fix.
- External review is input to validate after self review, not a place to hand off known owned cleanup.
- Bind every decision to the explicit reviewed head SHA for that branch state through the stable `head_sha` field.
- Do not proceed to PR creation, PR head refresh, merge readiness, or external-review repair handling until this skill returns `no_findings`.

## Procedure

1. Collect the real review surface:
   - `git status --short`
   - `git rev-parse HEAD`
   - `git diff --stat`
   - `git diff <range>`
2. Run `review-loop` on the current diff and branch state.
3. Map the shared loop result to this wrapper's status vocabulary:
   - `clean` -> `no_findings`
   - `findings` -> `findings`
   - `needs_architecture_review` -> `needs_architecture_review`
   - `blocked` -> `blocked`
4. Emit the machine-readable result envelope with `status`, `head_sha`, and `evidence` for the reviewed branch state.

## Three-round escalation

- This wrapper inherits the three-round limit from `review-loop`.
- If `review-loop` returns `needs_architecture_review`, keep that status here and escalate to `research`, not `research-pro`.
- If `research` recommends structural changes to module boundaries, interfaces, data flow, or tests, let the caller route that result into whatever planning workflow is active.

## Recommended checks

- Compare requirements against the current diff, not just tests.
- Re-read the current `plan/1` if one exists.
- Treat `review-loop` as the shared implementation-plus-adversarial review engine instead of duplicating its mechanics here.
- Stack `verification-before-completion` before any success claim.
- Stack `scout-skeptic` when the diff is risky or the findings pattern is unclear, or run an explicit local skeptic pass before handing control to `review-loop`.

## Red flags

- Calling the branch "ready" because tests happen to pass while the diff still contains obvious review debt
- Returning `no_findings` without first running the shared `review-loop` on the current diff
- Returning `no_findings` while known owned issues are still queued for someone else to catch later
- Creating or refreshing a PR head before self-review reaches `no_findings`
- Carrying GitHub thread behavior into this skill
- Re-implementing `review-loop` logic here instead of using the shared review engine
