#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "review-request" / "SKILL.md"


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"review-request skill must contain {needle!r}")


def main() -> int:
    text = SKILL_PATH.read_text(encoding="utf-8")
    for needle in [
        "name: review-request",
        "non-draft",
        "already be pushed",
        "workspace must be clean",
        "fresh verification evidence",
        "machine-readable result envelope",
        "`status`",
        "`head_sha`",
        "`pr_ref`",
        "`evidence`",
        "head SHA",
        "`review_requested`",
        "`blocked`",
        "does not repair comments",
    ]:
        assert_contains(text, needle)
    print("OK: review-request contract preserves request-only ownership")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
