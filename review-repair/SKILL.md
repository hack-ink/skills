---
name: review-repair
description: Use after a PR has review feedback on GitHub. Owns unresolved-thread triage, fix-and-verify rounds, in-thread replies, conditional resolve, and escalation to `research` when three review-repair rounds do not converge.
---

# Review Repair

## Scope

- This skill owns the GitHub review-fix loop after a PR already exists.
- This skill reads unresolved review comments, evaluates them with technical rigor, fixes valid issues, reruns verification, replies in-thread, and resolves only the threads that are actually complete.
- This skill does not request review, merge, close out trackers, or clean up workspaces.

## Inputs

- PR URL or PR number
- Current head SHA
- `plan/1` path when applicable
- Optional review round identifier

## Outputs

- Emit a machine-readable result envelope with these required fields:
  - `status`: one of `repaired`, `no_action`, `needs_re_review`, `awaiting_external`, `needs_architecture_review`, `blocked`
  - `head_sha`: exact repaired or inspected head SHA that this result applies to
  - `pr_ref`: stable PR identity such as URL or number
  - `evidence`: ordered list of verification, review-thread, or blocker evidence strings for that head; use `[]` when none apply

Every emitted result must use the stable `head_sha` field name for the repaired branch state. Do not leave the SHA implied only by prose.

## Hard gates

- Judge each comment before touching code:
  - read the full thread before reacting
  - restate the technical requirement in your own words
  - verify the suggestion against the codebase, tests, and requirements
  - decide: fix now, push back with technical reasoning, or ask for clarification
- External review feedback is input to evaluate, not an automatic order to follow.
- Re-run fresh verification after every repair batch.
- Before any repair-batch `git commit` or `git push`, run `review-prepare` on the repaired diff and do not continue until it returns `no_findings` for the current repaired head.
- If a repair batch needs `git commit` or `git push`, route through `delivery-prepare` before committing or pushing that repaired head.
- Bind every repair decision and resolution decision to the explicit repaired head SHA that was verified through the stable `head_sha` field.
- A repair batch that produces and pushes a new head is not review-complete by itself; return `needs_re_review` for that pushed head so the branch re-enters `review-request`.
- Reply in the GitHub thread, not as a top-level PR comment.
- Resolve a thread only when all of these are true:
  - the code is actually fixed
  - verification passed on that new state
  - the thread reply matches the fix that landed
- When a thread satisfies those gates, resolve it through GitHub instead of leaving manual cleanup behind just because resolve requires CLI or API work.
- Do not resolve when you are pushing back, asking for clarification, or still carrying unresolved work.
- Do not use performative agreement in replies; answer with the fix, the question, or the technical pushback.

## Procedure

1. Collect unresolved review threads and requested changes.
   - Record the current head SHA before touching code.
2. For each thread:
   - restate the technical requirement
   - validate it against the codebase
   - decide: fix now, push back, or ask for clarification
3. Group compatible fixes into the smallest coherent repair batch.
4. Apply the batch and re-run scoped verification.
5. Run `review-prepare` on the repaired diff before any repair-batch commit or push.
   - if `review-prepare` returns findings, fix them, re-run verification, and re-run `review-prepare` until it returns `no_findings` for the current repaired head
   - do not treat repair-batch verification alone as enough to skip this self-review gate
6. If the repair batch needs commit or push:
   - after `review-prepare` is clean for the repaired head, run `delivery-prepare` before the commit or push
   - push the repaired head
   - treat that pushed head as `needs_re_review` so `review-request` can request a fresh review for the new head
7. Reply in-thread for every addressed comment.
8. Resolve only the threads that satisfy the hard gates.
   - Default CLI path:
     - look up thread IDs with `gh api graphql` against `pullRequest.reviewThreads`
     - use `path`, `line` / `startLine`, and the latest comment `url` or body to match the right `$THREAD_ID` before resolving
     - resolve a completed thread with `resolveReviewThread`
     - reopen a thread later with `unresolveReviewThread` if new evidence shows the fix was incomplete
9. If the branch head changes during the loop, stop carrying prior repair state forward implicitly and return `needs_re_review` for the new head.
10. Emit the machine-readable result envelope with `status`, `head_sha`, `pr_ref`, and `evidence` for that branch state.

## GitHub thread commands

Use these default commands unless the repository documents a stricter helper or wrapper.

List review thread IDs for a PR:

```bash
gh api graphql \
  -f query='
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          reviewThreads(first: 100) {
            nodes {
              id
              isResolved
              isOutdated
              path
              line
              startLine
              comments(last: 1) {
                nodes {
                  author {
                    login
                  }
                  body
                  url
                }
              }
            }
          }
        }
      }
    }
  ' \
  -F owner="$OWNER" \
  -F repo="$REPO" \
  -F number="$PR_NUMBER"
```

Use `path`, `line` / `startLine`, and the latest comment `url` or body from that query to select the matching `$THREAD_ID` before you call a mutation.

Resolve a completed thread:

```bash
gh api graphql \
  -f query='
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) {
        thread {
          id
          isResolved
        }
      }
    }
  ' \
  -F threadId="$THREAD_ID"
```

Reopen a thread if a later review pass shows the fix was incomplete:

```bash
gh api graphql \
  -f query='
    mutation($threadId: ID!) {
      unresolveReviewThread(input: {threadId: $threadId}) {
        thread {
          id
          isResolved
        }
      }
    }
  ' \
  -F threadId="$THREAD_ID"
```

## Three-round escalation

- Count one round as: review feedback -> repair -> re-verify -> next review pass.
- If three consecutive rounds still produce new structural problems, stop incremental patching.
- Return `needs_architecture_review`.
- Default escalation target is `research`.
- If `research` changes interfaces, data flow, module ownership, or test shape, keep this skill at `needs_architecture_review` and let `research` or the caller route the result back through `plan-writing`.

## Thread discipline

- Fixes must be acknowledged in the comment thread they address.
- Pushback must be technical and specific.
- Clarification requests must keep the thread open.
- If you were wrong after pushing back, correct the record briefly and continue with the fix.
- Resolve is part of the repair contract, not an optional courtesy.

## Red flags

- Treating every reviewer suggestion as automatically correct
- Repairing code without re-running verification
- Treating repair-batch verification as enough to skip `review-prepare` on the repaired diff
- Committing or pushing a repair batch without first running `delivery-prepare`
- Committing or pushing a repair batch before `review-prepare` returns `no_findings` for the repaired head
- Posting a top-level PR comment instead of replying in-thread
- Leaving a verified completed thread unresolved because the resolve step required `gh api graphql`
- Resolving a thread before the fix is verified
- Requesting another review round from inside this skill instead of returning `needs_re_review`
