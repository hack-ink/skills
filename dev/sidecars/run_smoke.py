from __future__ import annotations

from pathlib import Path


DEV_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEV_DIR.parents[1]
COUPLED_SKILL_NEEDLES = [
    "`git-worktrees`",
    "`plan-writing`",
    "`plan-execution`",
    "`pre-commit`",
    "`parallel-conflict-resolution`",
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


def assert_sidecars_skill() -> None:
    skill_path = REPO_ROOT / "sidecars" / "SKILL.md"
    assert_exists(skill_path)
    text = read_text(skill_path)
    assert_contains(text, "scout", label="sidecars skill")
    assert_contains(text, "skeptic", label="sidecars skill")
    assert_contains(text, "## Sidecar round", label="sidecars skill")
    assert_contains(text, "bounded collect step", label="sidecars skill")
    assert_contains(text, "not ready yet", label="sidecars skill")
    assert_contains(text, "only missing evidence", label="sidecars skill")
    assert_contains(text, "acceptance is already independently satisfied", label="sidecars skill")
    for needle in [
        "helper",
        "ticket-dispatch/1",
        "ticket-result/1",
        "write_scope",
        "review_mode",
        "changed_paths",
    ]:
        assert_not_contains(text, needle, label="sidecars skill")
    print(f"OK: sidecars skill exists ({skill_path})")


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
    assert_contains(read_text(REPO_ROOT / "README.md"), "sidecars", label="README.md")
    print("OK: repo docs point to sidecars and omit deleted protocol surface")


def assert_installable_docs_decoupled() -> None:
    targets = [
        REPO_ROOT / "sidecars" / "SKILL.md",
        REPO_ROOT / "skill-routing" / "SKILL.md",
    ]
    for path in targets:
        text = read_text(path)
        assert_not_contains(text, "helper", label=str(path))
        for needle in COUPLED_SKILL_NEEDLES:
            assert_not_contains(text, needle, label=str(path))
    print("OK: installable skill docs stay decoupled from other concrete skills")


def main() -> int:
    assert_sidecars_skill()
    assert_deleted_surface_absent()
    assert_repo_docs()
    assert_installable_docs_decoupled()
    print("OK: sidecars smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
