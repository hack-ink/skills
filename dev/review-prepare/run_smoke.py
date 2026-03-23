#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "review-prepare" / "SKILL.md"


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"review-prepare skill must contain {needle!r}")


def main() -> int:
    text = SKILL_PATH.read_text(encoding="utf-8")
    for needle in [
        "name: review-prepare",
        "Wraps the shared `review-loop` mechanics",
        "maps the shared loop result onto pre-PR branch-readiness status",
        "primary self-review gate for branch readiness",
        "Run `review-loop` on the actual diff",
        "machine-readable result envelope",
        "`status`",
        "`head_sha`",
        "`evidence`",
        "reviewed head SHA",
        "`no_findings`",
        "`findings`",
        "`needs_architecture_review`",
        "`blocked`",
        "inherits the three-round limit from `review-loop`",
        "`research`",
        "Do not proceed to PR creation",
        "including after `review-repair` changes the branch",
        "PR head refresh",
        "merge readiness",
        "Do not output `no_findings` while any known owned issue remains on the current head",
        "External review is input to validate after self review, not a place to hand off known owned cleanup",
        "Returning `no_findings` without first running the shared `review-loop` on the current diff",
    ]:
        assert_contains(text, needle)
    print("OK: review-prepare contract captures the pre-PR self-review loop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
