---
name: review-loop
description: Use when a review workflow needs the shared bounded review -> fix -> verify -> re-review mechanics on a concrete diff or repaired branch state. Owns round structure, head-SHA binding, owned-fix discipline, and three-round escalation to `research`, but not PR, thread, merge, or closeout lifecycle.
---

# Review Loop

## Scope

- This skill is the shared review core used by concrete review stages.
- It reviews the actual diff or repaired branch state, fixes owned findings in the smallest coherent batch, reruns verification, and re-reviews until the current head is clean or escalated.
- This skill does not create a PR, request or resolve review threads, merge, or close out trackers.

## Inputs

- Concrete diff or branch range
- Current head SHA
- Requirements and intended user-visible behavior
- Verification commands for the touched area
- Optional caller-normalized external review claims or review focus areas

## Outputs

- Emit a machine-readable result envelope with these required fields:
  - `status`: one of `clean`, `findings`, `needs_architecture_review`, `blocked`
  - `head_sha`: exact reviewed head SHA that this loop result applies to
  - `evidence`: ordered list of verification or review evidence strings for that head; use `[]` when none apply yet

Every emitted result must use the stable `head_sha` field name for the reviewed branch state. Do not leave the SHA implied only by prose.

## Hard gates

- Review the actual diff or repaired branch state, not memory of the implementation.
- Every fix round must be followed by fresh verification on the current branch state.
- Do not return `clean` while any known owned issue remains on the current head, even if it is small.
- Run both passes every round:
  - an implementation pass against requirements, plan intent, and intended user-visible behavior
  - an adversarial reviewer pass against regression risk, missing tests, docs/config drift, migration fallout, and operator-facing fallout
- Treat caller-supplied external review claims as candidate findings to validate, not as automatic truth.
- Bind every decision to the explicit reviewed head SHA for that branch state through the stable `head_sha` field.
- If the branch changes during the loop, re-read `git rev-parse HEAD` and continue only against the new head.

## Procedure

1. Collect the real review surface:
   - `git status --short`
   - `git rev-parse HEAD`
   - `git diff --stat`
   - `git diff <range>`
2. Normalize the current review focus:
   - requirements and intended behavior
   - any caller-supplied external-review claims or risk focus
3. Run the implementation pass.
4. Run the adversarial reviewer pass.
5. Decide whether the current state is:
   - `findings`
   - `clean`
   - `needs_architecture_review`
   - `blocked`
6. If findings exist, fix the smallest coherent owned batch.
7. Run the scoped verification for that batch.
8. Re-read the current head and diff, then re-run both passes on the new state.
9. Emit the machine-readable result envelope for the reviewed head.

## Three-round escalation

- Count one round as: review -> fix -> re-verify -> re-review.
- If three consecutive rounds still produce new bugs, owned findings, or structural problems, stop patch-on-patch repair.
- Return `needs_architecture_review`.
- Default escalation target is `research`.
- If `research` recommends structural changes to module boundaries, interfaces, data flow, or test shape, let the caller route that result into whatever planning workflow is active instead of continuing the loop.

## Red flags

- Calling a diff clean because tests happen to pass
- Skipping the adversarial reviewer pass because the implementation pass looked straightforward
- Treating external review claims as automatically correct without validating them
- Letting one stale head SHA stand in for multiple reviewed states
- Continuing beyond three rounds of new findings without escalating to `research`
