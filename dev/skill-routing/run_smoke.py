from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import tempfile
import tomllib


DEV_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEV_DIR.parents[1]
SOURCE_HELPER_PATH = REPO_ROOT / "skill-routing" / "scripts" / "build_child_skill_policy.py"
SOURCE_TEMPLATE_PATH = REPO_ROOT / "skill-routing" / "child-skill-policy.toml"
SOURCE_SKILL_PATH = REPO_ROOT / "skill-routing" / "SKILL.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the child denylist policy.")
    parser.add_argument(
        "--runtime-policy",
        type=Path,
        help="Optional installed runtime policy to parse and validate.",
    )
    parser.add_argument(
        "--runtime-skills-root",
        type=Path,
        help="Installed skills root used with --runtime-policy. Defaults to the parent of the policy's skill directory.",
    )
    return parser.parse_args()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_skill_doc_boundary() -> None:
    text = SOURCE_SKILL_PATH.read_text(encoding="utf-8")
    for needle in [
        "not a full capability sandbox",
        "control-plane recursion",
        "runtime child behavior rules",
    ]:
        if needle not in text:
            raise AssertionError(f"skill-routing doc must contain {needle!r}")
    print("OK: skill-routing doc states minimal denylist boundaries")


def assert_repo_template_canonical(helper) -> None:
    policy = helper.load_policy(SOURCE_TEMPLATE_PATH)
    expected_policy = {
        "version": helper.POLICY_VERSION,
        "child_forbidden": ["sidecars"],
    }
    if policy != expected_policy:
        raise AssertionError(f"repo template must stay canonical, got {policy!r}")

    rendered = helper.render_policy(policy)
    if rendered != SOURCE_TEMPLATE_PATH.read_text(encoding="utf-8"):
        raise AssertionError("repo template is not canonical under helper render_policy()")

    print("OK: repo template remains canonical")


def assert_denylist_fixture(helper) -> None:
    known_skills = sorted(helper.list_known_skills())
    denylisted_skill = next((skill for skill in known_skills if skill != "sidecars"), None)
    if denylisted_skill is None:
        raise AssertionError("denylist smoke fixture needs at least one non-sidecars skill")
    allowed_skill = next(
        (skill for skill in known_skills if skill not in {"sidecars", denylisted_skill}),
        None,
    )
    if allowed_skill is None:
        raise AssertionError("denylist smoke fixture needs at least two non-sidecars skills")

    fixture_text = f"""
version = 5

child_forbidden = ["{denylisted_skill}", "{denylisted_skill}"]
""".strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        fixture_path = Path(tmp_dir) / "child-skill-policy.toml"
        fixture_path.write_text(fixture_text + "\n", encoding="utf-8")
        policy = helper.load_policy(fixture_path)

    actual_denylist = set(policy["child_forbidden"])
    if actual_denylist != {denylisted_skill}:
        raise AssertionError(
            "denylist fixture should canonicalize to "
            f"{[denylisted_skill]!r}, got {sorted(actual_denylist)!r}"
        )

    if helper.resolve_skill_policy(denylisted_skill, policy=policy) != helper.CHILD_FORBIDDEN_POLICY:
        raise AssertionError("denylisted skills must resolve as child-forbidden")
    if helper.resolve_skill_policy(allowed_skill, policy=policy) != helper.DEFAULT_CHILD_POLICY:
        raise AssertionError("omitted skills must stay allowed by default")

    try:
        helper.validate_child_skill_use(denylisted_skill, policy=policy)
    except ValueError as exc:
        if "child-forbidden" not in str(exc):
            raise AssertionError(
                f"denylisted skill should fail with a child-forbidden error, got {exc!r}"
            ) from exc
        print(f"OK: denylisted skill blocked ({exc})")
    else:
        raise AssertionError("denylisted skill should be rejected")

    helper.validate_child_skill_use(allowed_skill, policy=policy)
    print("OK: omitted skill remains allowed")


def assert_unknown_skill_rejected(helper) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        fixture_path = Path(tmp_dir) / "child-skill-policy.toml"
        fixture_path.write_text(
            'version = 5\n\nchild_forbidden = ["not-a-real-skill"]\n',
            encoding="utf-8",
        )
        try:
            helper.load_policy(fixture_path)
        except ValueError as exc:
            if "known local skills" not in str(exc):
                raise AssertionError(
                    "unknown denylist entries should mention known local skills, "
                    f"got {exc!r}"
                ) from exc
            print(f"OK: unknown denylist entry rejected ({exc})")
            return

    raise AssertionError("unknown denylist entry should be rejected")


def assert_legacy_field_rejected(helper) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        fixture_path = Path(tmp_dir) / "child-skill-policy.toml"
        fixture_path.write_text(
            'version = 4\n\nmain_thread_only = ["sidecars"]\n',
            encoding="utf-8",
        )
        try:
            helper.load_policy(fixture_path)
        except ValueError as exc:
            text = str(exc)
            if "main_thread_only" not in text or "child_forbidden" not in text:
                raise AssertionError(
                    "legacy policy rejection should mention both main_thread_only and child_forbidden, "
                    f"got {exc!r}"
                ) from exc
            print(f"OK: legacy field rejected ({exc})")
            return

    raise AssertionError("legacy main_thread_only field should be rejected")


def infer_runtime_skills_root(runtime_policy: Path) -> Path:
    resolved = runtime_policy.resolve()
    if len(resolved.parents) < 2:
        raise AssertionError(
            f"cannot infer runtime skills root from {runtime_policy}; pass --runtime-skills-root"
        )
    return resolved.parents[1]


def load_runtime_policy(helper, runtime_policy: Path) -> dict[str, object]:
    if not runtime_policy.exists():
        raise AssertionError(f"runtime policy does not exist: {runtime_policy}")

    data = tomllib.loads(runtime_policy.read_text(encoding="utf-8"))
    if "main_thread_only" in data:
        raise AssertionError(
            "runtime policy must not use legacy main_thread_only; migrate it to child_forbidden"
        )

    version = data.get("version", helper.POLICY_VERSION)
    if not isinstance(version, int):
        raise AssertionError(f"runtime policy version must be an integer, got {version!r}")
    if version != helper.POLICY_VERSION:
        raise AssertionError(
            f"runtime policy version must be {helper.POLICY_VERSION}, got {version!r}"
        )

    unexpected_keys = sorted(key for key in data if key not in helper.ALLOWED_KEYS)
    if unexpected_keys:
        raise AssertionError(
            "runtime policy only supports version and child_forbidden; unexpected keys: "
            + ", ".join(unexpected_keys)
        )

    child_forbidden = helper.normalize_skill_list(
        data.get("child_forbidden"),
        "child_forbidden",
    )
    return {
        "version": version,
        "child_forbidden": child_forbidden,
    }


def assert_runtime_policy(helper, runtime_policy: Path, runtime_skills_root: Path | None) -> None:
    policy = load_runtime_policy(helper, runtime_policy)
    installed_root = runtime_skills_root.resolve() if runtime_skills_root else infer_runtime_skills_root(
        runtime_policy
    )
    installed_skills = helper.list_known_skills(installed_root)
    if not installed_skills:
        raise AssertionError(f"no installed skills found under runtime root {installed_root}")

    unknown_skills = sorted(
        skill_name
        for skill_name in policy["child_forbidden"]
        if skill_name not in installed_skills
    )
    if unknown_skills:
        raise AssertionError(
            "runtime policy child_forbidden entries must reference known installed skills; "
            f"unknown: {', '.join(unknown_skills)}"
        )

    print(
        "OK: runtime policy parsed and references known installed skills "
        f"({runtime_policy} against {installed_root})"
    )


def main() -> int:
    args = parse_args()
    helper = load_module(SOURCE_HELPER_PATH, "build_child_skill_policy")

    assert_skill_doc_boundary()
    assert_repo_template_canonical(helper)
    assert_denylist_fixture(helper)
    assert_unknown_skill_rejected(helper)
    assert_legacy_field_rejected(helper)

    if args.runtime_policy is not None:
        assert_runtime_policy(helper, args.runtime_policy, args.runtime_skills_root)
    else:
        print("OK: runtime policy check skipped (no --runtime-policy provided)")

    print("OK: skill-routing policy smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
