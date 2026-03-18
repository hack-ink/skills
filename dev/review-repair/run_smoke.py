#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "review-repair" / "SKILL.md"


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"review-repair skill must contain {needle!r}")


def main() -> int:
    text = SKILL_PATH.read_text(encoding="utf-8")
    for needle in [
        "name: review-repair",
        "External review feedback is input to evaluate",
        "machine-readable result envelope",
        "`status`",
        "`head_sha`",
        "`pr_ref`",
        "`evidence`",
        "repaired head SHA",
        "Reply in the GitHub thread",
        "Resolve a thread only",
        "If a repair batch needs `git commit` or `git push`, route through `delivery-prepare` before committing or pushing that repaired head.",
        "A repair batch that produces and pushes a new head is not review-complete by itself; return `needs_re_review` for that pushed head so the branch re-enters `review-request`.",
        "`needs_re_review`",
        "`awaiting_external`",
        "three consecutive rounds",
        "technical reasoning",
        "`research`",
    ]:
        assert_contains(text, needle)
    print("OK: review-repair contract captures verified thread repair and resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
