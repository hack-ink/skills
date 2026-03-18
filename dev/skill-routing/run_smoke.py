from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib


DEV_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEV_DIR.parents[1]
SOURCE_HELPER_PATH = REPO_ROOT / "skill-routing" / "scripts" / "build_child_skill_policy.py"
SOURCE_TEMPLATE_PATH = REPO_ROOT / "skill-routing" / "child-skill-policy.toml"
SOURCE_SKILL_PATH = REPO_ROOT / "skill-routing" / "SKILL.md"
SOURCE_OVERLAY_SKILL_PATH = REPO_ROOT / "scout-skeptic" / "SKILL.md"
SOURCE_FIXTURE_PATH = REPO_ROOT / "skill-routing" / "routing-fixtures.json"
PRIMARY_PROCESS_REFERENCE_HEADING = "## Primary workflow references for overlay examples"


@dataclass(frozen=True)
class OverlayRoutingFixture:
    name: str
    prompt: str
    expect_primary_process_skills: tuple[str, ...]
    expect_overlay_skills: tuple[str, ...]
    policy_reason_needles: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test the child denylist policy and static routing contract."
    )
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
        "primary workflow skills and additive overlay skills",
        "`scout-skeptic` is an additive overlay skill",
    ]:
        if needle not in text:
            raise AssertionError(f"skill-routing doc must contain {needle!r}")
    print("OK: skill-routing doc states minimal denylist boundaries")


def normalize_string_list(raw: object, field_name: str, *, item_name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise AssertionError(f"{field_name} in {item_name!r} must be a JSON array")
    normalized: list[str] = []
    for value in raw:
        if not isinstance(value, str) or not value.strip():
            raise AssertionError(f"{field_name} in {item_name!r} must contain non-empty strings")
        normalized.append(value)
    return tuple(normalized)


def load_primary_process_skill_references() -> tuple[str, ...]:
    text = SOURCE_SKILL_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    collecting = False
    references: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not collecting:
            if stripped == PRIMARY_PROCESS_REFERENCE_HEADING:
                collecting = True
            continue

        if stripped.startswith("## "):
            break
        if not stripped:
            continue
        if not (stripped.startswith("- `") and stripped.endswith("`")):
            raise AssertionError(
                "primary workflow reference section must contain only bullet lines with backtick-wrapped skill names"
            )
        references.append(stripped[len("- `") : -1])

    if not collecting:
        raise AssertionError(
            f"skill-routing doc must contain {PRIMARY_PROCESS_REFERENCE_HEADING!r}"
        )
    if not references:
        raise AssertionError("primary workflow reference section must list one or more skills")
    if len(references) != len(set(references)):
        raise AssertionError("primary workflow reference section must not contain duplicates")

    return tuple(references)


def load_overlay_routing_fixtures() -> tuple[OverlayRoutingFixture, ...]:
    if not SOURCE_FIXTURE_PATH.exists():
        raise AssertionError(f"missing overlay routing fixture file: {SOURCE_FIXTURE_PATH}")

    try:
        data = json.loads(SOURCE_FIXTURE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"routing fixture file must be valid JSON: {exc}"
        ) from exc
    version = data.get("version")
    if version != 1:
        raise AssertionError(
            f"routing fixture file must declare version = 1, got {version!r}"
        )

    raw_fixtures = data.get("fixtures")
    if not isinstance(raw_fixtures, list) or not raw_fixtures:
        raise AssertionError("routing fixture file must declare one or more fixtures")

    fixtures: list[OverlayRoutingFixture] = []
    for raw_fixture in raw_fixtures:
        if not isinstance(raw_fixture, dict):
            raise AssertionError("each routing fixture must be a JSON object")
        name = raw_fixture.get("name")
        prompt = raw_fixture.get("prompt")
        if not isinstance(name, str) or not name.strip():
            raise AssertionError(f"fixture missing non-empty name: {raw_fixture!r}")
        if not isinstance(prompt, str) or not prompt.strip():
            raise AssertionError(f"fixture {name!r} missing non-empty prompt")
        fixtures.append(
            OverlayRoutingFixture(
                name=name,
                prompt=prompt,
                expect_primary_process_skills=normalize_string_list(
                    raw_fixture.get("expect_primary_process_skills"),
                    "expect_primary_process_skills",
                    item_name=name,
                ),
                expect_overlay_skills=normalize_string_list(
                    raw_fixture.get("expect_overlay_skills"),
                    "expect_overlay_skills",
                    item_name=name,
                ),
                policy_reason_needles=normalize_string_list(
                    raw_fixture.get("policy_reason_needles"),
                    "policy_reason_needles",
                    item_name=name,
                ),
            )
        )

    return tuple(fixtures)


def assert_overlay_routing_fixtures(helper) -> None:
    fixtures = load_overlay_routing_fixtures()
    policy_surfaces = [
        SOURCE_OVERLAY_SKILL_PATH.read_text(encoding="utf-8"),
        SOURCE_SKILL_PATH.read_text(encoding="utf-8"),
    ]
    known_local_skills = helper.list_known_skills()
    known_primary_process_skills = set(load_primary_process_skill_references())

    positive_cases = 0
    negative_cases = 0
    stacked_cases = 0
    direct_only_cases = 0
    seen_prompts: set[str] = set()

    for fixture in fixtures:
        if fixture.prompt in seen_prompts:
            raise AssertionError(
                f"routing fixtures must use distinct prompt surfaces; duplicate prompt in {fixture.name!r}"
            )
        seen_prompts.add(fixture.prompt)

        if "scout-skeptic" in fixture.prompt:
            raise AssertionError(
                f"fixture {fixture.name!r} prompt must not mention skill names directly"
            )

        if not fixture.policy_reason_needles:
            raise AssertionError(
                f"fixture {fixture.name!r} must cite one or more checked-in policy needles"
            )

        for needle in fixture.policy_reason_needles:
            if all(needle not in text for text in policy_surfaces):
                raise AssertionError(
                    f"fixture {fixture.name!r} cites missing policy needle {needle!r}"
                )

        if len(fixture.expect_primary_process_skills) != len(
            set(fixture.expect_primary_process_skills)
        ):
            raise AssertionError(
                f"fixture {fixture.name!r} must not duplicate primary process skills"
            )

        unknown_primary = sorted(
            skill_name
            for skill_name in fixture.expect_primary_process_skills
            if skill_name not in known_primary_process_skills
        )
        if unknown_primary:
            raise AssertionError(
                f"fixture {fixture.name!r} references unknown primary workflow skill(s): "
                + ", ".join(unknown_primary)
            )

        unknown_overlay = sorted(
            skill_name
            for skill_name in fixture.expect_overlay_skills
            if skill_name not in known_local_skills
        )
        if unknown_overlay:
            raise AssertionError(
                f"fixture {fixture.name!r} references unknown overlay skill(s): {', '.join(unknown_overlay)}"
            )

        overlap = sorted(
            set(fixture.expect_primary_process_skills).intersection(
                fixture.expect_overlay_skills
            )
        )
        if overlap:
            raise AssertionError(
                f"fixture {fixture.name!r} must not classify the same skill as both primary and overlay: "
                + ", ".join(overlap)
            )

        if fixture.expect_overlay_skills:
            positive_cases += 1
            if fixture.expect_overlay_skills != ("scout-skeptic",):
                raise AssertionError(
                    f"fixture {fixture.name!r} must use scout-skeptic as the only overlay, "
                    f"got {fixture.expect_overlay_skills!r}"
                )
            if fixture.expect_primary_process_skills:
                stacked_cases += 1
        else:
            negative_cases += 1
            if not fixture.expect_primary_process_skills:
                direct_only_cases += 1

    if positive_cases == 0 or negative_cases == 0:
        raise AssertionError(
            "overlay routing matrix must include both positive and negative fixtures"
        )
    if stacked_cases == 0:
        raise AssertionError(
            "routing fixtures must include at least one overlay-positive case that preserves a primary workflow skill"
        )
    if direct_only_cases == 0:
        raise AssertionError(
            "routing fixtures must include at least one direct-only case with no primary workflow skill"
        )

    print(
        "OK: static routing contract covers positive and negative scout-skeptic cases"
    )


def assert_repo_template_canonical(helper) -> None:
    policy = helper.load_policy(SOURCE_TEMPLATE_PATH)
    expected_policy = {
        "version": helper.POLICY_VERSION,
        "child_forbidden": ["scout-skeptic"],
    }
    if policy != expected_policy:
        raise AssertionError(f"repo template must stay canonical, got {policy!r}")

    rendered = helper.render_policy(policy)
    if rendered != SOURCE_TEMPLATE_PATH.read_text(encoding="utf-8"):
        raise AssertionError("repo template is not canonical under helper render_policy()")

    print("OK: repo template remains canonical")


def assert_denylist_fixture(helper) -> None:
    known_skills = sorted(helper.list_known_skills())
    denylisted_skill = next((skill for skill in known_skills if skill != "scout-skeptic"), None)
    if denylisted_skill is None:
        raise AssertionError("denylist smoke fixture needs at least one non-scout-skeptic skill")
    allowed_skill = next(
        (skill for skill in known_skills if skill not in {"scout-skeptic", denylisted_skill}),
        None,
    )
    if allowed_skill is None:
        raise AssertionError("denylist smoke fixture needs at least two non-scout-skeptic skills")

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
            'version = 4\n\nmain_thread_only = ["scout-skeptic"]\n',
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
    assert_overlay_routing_fixtures(helper)
    assert_repo_template_canonical(helper)
    assert_denylist_fixture(helper)
    assert_unknown_skill_rejected(helper)
    assert_legacy_field_rejected(helper)

    if args.runtime_policy is not None:
        assert_runtime_policy(helper, args.runtime_policy, args.runtime_skills_root)
    else:
        print("OK: runtime policy check skipped (no --runtime-policy provided)")

    print("OK: skill-routing contract smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
