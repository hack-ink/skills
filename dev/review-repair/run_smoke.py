#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "review-repair" / "SKILL.md"


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"review-repair skill must contain {needle!r}")


def assert_block(text: str, block: str) -> None:
    needle = dedent(block).strip()
    if needle not in text:
        raise AssertionError(f"review-repair skill must contain block:\n{needle}")


def main() -> int:
    text = SKILL_PATH.read_text(encoding="utf-8")
    for needle in [
        "name: review-repair",
        "External review feedback is input to evaluate",
        "uses `review-loop` for any owned repair batch",
        "Use `review-loop` as the shared repair-batch review engine on the repaired diff.",
        "machine-readable result envelope",
        "`status`",
        "`head_sha`",
        "`pr_ref`",
        "`evidence`",
        "repaired head SHA",
        "Reply in the review thread",
        "Resolve a thread only",
        "resolve it through GitHub instead of leaving manual cleanup behind",
        "the repaired diff must reach `clean` through `review-loop` before any commit, push, or resolve decision that depends on the new state.",
        "A repaired head that reaches `clean` through `review-loop` satisfies the current-head self-review gate for downstream flow",
        "Do not leave a repaired head carrying known owned bugs or small cleanup while treating external review as the next line of defense.",
        "If a repair batch needs `git commit` or `git push`, route through `delivery-prepare` only after `review-loop` reaches `clean` for that repaired head.",
        "A repair batch that produces and pushes a new head is not complete by itself; keep ownership until the repaired diff is verified, the thread replies are posted, and every fixed thread is resolved.",
        "`gh api graphql`",
        "use `path`, `line` / `startLine`, and the latest comment `url` or body to match the right `$THREAD_ID` before resolving",
        "`awaiting_external`",
        "The bounded repair mechanics inherit the three-round limit from `review-loop`.",
        "external review feedback -> triage -> `review-loop` repair batch -> next review pass",
        "deeper architecture or design cause",
        "technical reasoning",
        "`research`",
        "Treating fixed threads as done without resolving them after the repaired state is verified",
    ]:
        assert_contains(text, needle)
    assert_block(
        text,
        """
        Apply the batch and run `review-loop` on the repaired diff.
           - if `review-loop` returns `findings`, keep fixing, re-verifying, and re-running `review-loop` until it returns `clean` for the current repaired head
           - if `review-loop` returns `needs_architecture_review` or `blocked`, stop and emit that result for the current head
        """,
    )
    assert_block(
        text,
        """
        If the repair batch needs commit or push:
           - after `review-loop` is clean for the repaired head, run `delivery-prepare` before the commit or push
           - push the repaired head
           - continue owning the external-review repair loop for that new head instead of assuming another request step
        """,
    )
    assert_block(
        text,
        """
        reviewThreads(first: 100) {
                    nodes {
                      id
                      isResolved
                      isOutdated
                      path
                      line
                      startLine
                      comments(last: 1) {
        """,
    )
    assert_block(
        text,
        """
        mutation($threadId: ID!) {
              resolveReviewThread(input: {threadId: $threadId}) {
        """,
    )
    assert_block(
        text,
        """
        mutation($threadId: ID!) {
              unresolveReviewThread(input: {threadId: $threadId}) {
        """,
    )
    print("OK: review-repair contract captures shared-loop repair and verified thread resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
