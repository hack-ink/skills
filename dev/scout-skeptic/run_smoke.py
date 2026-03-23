from __future__ import annotations

from pathlib import Path


DEV_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEV_DIR.parents[1]
COUPLED_SKILL_NEEDLES = [
    "`workspaces`",
    "`plan-writing`",
    "`plan-execution`",
    "`delivery-prepare`",
    "`delivery-closeout`",
    "`workspace-reconcile`",
    "`review-prepare`",
    "`review-repair`",
    "`pr-land`",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_exists(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"expected path to exist: {path}")


def assert_absent(path: Path) -> None:
    if path.exists():
        raise AssertionError(f"expected path to be removed: {path}")


def assert_contains(text: str, needle: str, *, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} must contain {needle!r}")


def assert_not_contains(text: str, needle: str, *, label: str) -> None:
    if needle in text:
        raise AssertionError(f"{label} must not contain {needle!r}")


def assert_scout_skeptic_skill() -> None:
    skill_path = REPO_ROOT / "scout-skeptic" / "SKILL.md"
    assert_exists(skill_path)
    text = read_text(skill_path)
    assert_contains(text, "name: scout-skeptic", label="scout-skeptic skill")
    assert_contains(text, "scout", label="scout-skeptic skill")
    assert_contains(text, "skeptic", label="scout-skeptic skill")
    assert_contains(text, "additive overlay", label="scout-skeptic skill")
    assert_contains(text, "## Non-trivial threshold", label="scout-skeptic skill")
    assert_contains(
        text,
        "Treat the task as trivial when the first short probe leaves only one obvious local action",
        label="scout-skeptic skill",
    )
    assert_contains(
        text,
        "one remaining implementation path plus a second distinct verification, regression, or reviewer-risk question",
        label="scout-skeptic skill",
    )
    assert_contains(
        text,
        "thresholded mechanism, not a vague preference",
        label="scout-skeptic skill",
    )
    assert_contains(text, "## Fanout threshold", label="scout-skeptic skill")
    assert_contains(
        text,
        "At least two independent read-only questions, hypotheses, or evidence gaps remain.",
        label="scout-skeptic skill",
    )
    assert_contains(
        text,
        "The main thread still has direct work, synthesis, or another verification step to do while the child agents run.",
        label="scout-skeptic skill",
    )
    assert_contains(
        text,
        "Spawn one `scout` objective and one `skeptic` objective.",
        label="scout-skeptic skill",
    )
    assert_contains(
        text,
        "Only one blocking read-only question remains.",
        label="scout-skeptic skill",
    )
    assert_contains(
        text,
        "The main thread would mostly wait on the result instead of continuing direct work or synthesis.",
        label="scout-skeptic skill",
    )
    assert_contains(text, "## Scout-Skeptic round", label="scout-skeptic skill")
    assert_contains(text, "bounded collect step", label="scout-skeptic skill")
    assert_contains(text, "not ready yet", label="scout-skeptic skill")
    assert_contains(text, "only missing evidence", label="scout-skeptic skill")
    assert_contains(text, "## Local checkpoint fallback", label="scout-skeptic skill")
    assert_contains(
        text,
        "say which threshold failed",
        label="scout-skeptic skill",
    )
    assert_contains(text, "current theory or working plan", label="scout-skeptic skill")
    assert_contains(text, "strongest contradictory evidence, regression risk, or skeptic concern", label="scout-skeptic skill")
    assert_contains(text, "missing evidence or missing test", label="scout-skeptic skill")
    assert_contains(text, "next direct action the main thread will take", label="scout-skeptic skill")
    assert_contains(
        text,
        "acceptance is already independently satisfied",
        label="scout-skeptic skill",
    )
    for needle in [
        "helper",
        "ticket-dispatch/1",
        "ticket-result/1",
        "write_scope",
        "review_mode",
        "changed_paths",
    ]:
        assert_not_contains(text, needle, label="scout-skeptic skill")
    print(f"OK: scout-skeptic skill exists ({skill_path})")


def assert_deleted_surface_absent() -> None:
    assert_absent(REPO_ROOT / "multi-agent")
    assert_absent(REPO_ROOT / "dev" / "multi-agent")
    print("OK: deleted multi-agent source surface is absent")


def assert_repo_docs() -> None:
    targets = [
        REPO_ROOT / "README.md",
    ]
    forbidden = [
        "multi-agent",
        "ticket-dispatch/1",
        "ticket-result/1",
        "write_scope",
        "review_mode",
        "changed_paths",
    ]
    for path in targets:
        text = read_text(path)
        assert_not_contains(text, "multi-agent", label=str(path))
        for needle in forbidden[1:]:
            assert_not_contains(text, needle, label=str(path))
    assert_contains(read_text(REPO_ROOT / "README.md"), "scout-skeptic", label="README.md")
    print("OK: repo docs point to scout-skeptic and omit deleted protocol surface")


def assert_installable_docs_decoupled() -> None:
    path = REPO_ROOT / "scout-skeptic" / "SKILL.md"
    text = read_text(path)
    assert_not_contains(text, "helper", label=str(path))
    for needle in COUPLED_SKILL_NEEDLES:
        assert_not_contains(text, needle, label=str(path))
    print("OK: installable skill docs stay decoupled from other concrete skills")


def main() -> int:
    assert_scout_skeptic_skill()
    assert_deleted_surface_absent()
    assert_repo_docs()
    assert_installable_docs_decoupled()
    print("OK: scout-skeptic smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
