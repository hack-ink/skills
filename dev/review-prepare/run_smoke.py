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
        "actual diff",
        "machine-readable result envelope",
        "`status`",
        "`head_sha`",
        "`evidence`",
        "reviewed head SHA",
        "`no_findings`",
        "`findings`",
        "`needs_architecture_review`",
        "`blocked`",
        "three consecutive rounds",
        "`research`",
        "Do not proceed to PR creation",
    ]:
        assert_contains(text, needle)
    print("OK: review-prepare contract captures the pre-PR self-review loop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
