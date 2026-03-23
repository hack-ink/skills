#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "review-loop" / "SKILL.md"


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"review-loop skill must contain {needle!r}")


def main() -> int:
    text = SKILL_PATH.read_text(encoding="utf-8")
    for needle in [
        "name: review-loop",
        "shared review core",
        "machine-readable result envelope",
        "`clean`",
        "`findings`",
        "`needs_architecture_review`",
        "`blocked`",
        "`head_sha`",
        "Every fix round must be followed by fresh verification",
        "implementation pass",
        "adversarial reviewer pass",
        "regression risk, missing tests, docs/config drift, migration fallout, and operator-facing fallout",
        "candidate findings to validate",
        "three consecutive rounds",
        "`research`",
    ]:
        assert_contains(text, needle)
    print("OK: review-loop contract captures the shared bounded review engine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
