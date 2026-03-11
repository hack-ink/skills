#!/usr/bin/env python3
"""Validate or initialize the manual child skill policy."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib


POLICY_VERSION = 3
DEFAULT_CHILD_POLICY = "any-agent"
POLICY_VALUES = {"any-agent", "dispatch-authorized", "main-thread-only"}
SKILLS_REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate or initialize the manual child skill policy."
    )
    skill_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--policy",
        type=Path,
        default=skill_root / "child-skill-policy.toml",
        help="Policy file to read/write.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the canonical policy to --policy instead of printing it.",
    )
    return parser.parse_args()


def normalize_policy_table(raw: object, table_name: str) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{table_name} must be a TOML table")
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(f"{table_name} entries must be string = string")
        if value not in POLICY_VALUES:
            raise ValueError(f"Invalid policy value {value!r} for {key!r}")
        if value != DEFAULT_CHILD_POLICY:
            normalized[key] = value
    return dict(sorted(normalized.items()))


def list_known_skills(skills_root: Path = SKILLS_REPO_ROOT) -> set[str]:
    known: set[str] = set()

    for entry in sorted(skills_root.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir() and (entry / "SKILL.md").is_file():
            known.add(entry.name)

    system_root = skills_root / ".system"
    if system_root.is_dir():
        for entry in sorted(system_root.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir() and (entry / "SKILL.md").is_file():
                known.add(entry.name)

    return known


def blank_policy(*, default_child_policy: str = DEFAULT_CHILD_POLICY) -> dict[str, object]:
    if default_child_policy != DEFAULT_CHILD_POLICY:
        raise ValueError(
            "manual child skill policy currently supports only "
            f"default_child_policy={DEFAULT_CHILD_POLICY!r}"
        )
    return {
        "version": POLICY_VERSION,
        "default_child_policy": default_child_policy,
        "skills": {},
    }


def load_policy(policy_path: Path) -> dict[str, object]:
    if not policy_path.exists():
        return blank_policy()

    data = tomllib.loads(policy_path.read_text(encoding="utf-8"))
    default_child_policy = data.get("default_child_policy", DEFAULT_CHILD_POLICY)
    version = data.get("version", POLICY_VERSION)
    if not isinstance(version, int):
        raise ValueError(f"Invalid version {version!r} in {policy_path}")
    if version not in {2, POLICY_VERSION}:
        raise ValueError(f"Unsupported policy version {version!r} in {policy_path}")
    if default_child_policy != DEFAULT_CHILD_POLICY:
        raise ValueError(
            "manual child skill policy currently supports only "
            f"default_child_policy={DEFAULT_CHILD_POLICY!r} in {policy_path}"
        )

    raw_skills = data.get("skills")
    if raw_skills is None and version == 2:
        raw_skills = data.get("generated")

    policy = blank_policy(default_child_policy=default_child_policy)
    policy["skills"] = normalize_policy_table(raw_skills, "skills")
    known_skills = list_known_skills()
    unknown_skills = sorted(
        skill_name for skill_name in policy["skills"] if skill_name not in known_skills
    )
    if unknown_skills:
        raise ValueError(
            "child-skill-policy.toml entries must reference known local skills; "
            f"unknown: {', '.join(unknown_skills)}"
        )
    return policy


def resolve_skill_policy(
    skill_name: str,
    *,
    policy: dict[str, object] | None = None,
) -> str:
    if policy is None:
        return DEFAULT_CHILD_POLICY
    skills = policy.get("skills", {})
    if not isinstance(skills, dict):
        raise ValueError("policy.skills must be a mapping")
    value = skills.get(skill_name, policy.get("default_child_policy", DEFAULT_CHILD_POLICY))
    if value not in POLICY_VALUES:
        raise ValueError(f"Invalid effective policy {value!r} for {skill_name!r}")
    return value


def validate_authorized_skills(
    authorized_skills: list[str],
    *,
    policy: dict[str, object],
) -> None:
    known_skills = list_known_skills()
    for skill_name in authorized_skills:
        if skill_name not in known_skills:
            raise ValueError(
                "authorized_skills must reference known local skills; "
                f"unknown: {skill_name!r}"
            )
        effective_policy = resolve_skill_policy(
            skill_name,
            policy=policy,
        )
        if effective_policy == "dispatch-authorized":
            continue
        if effective_policy == "main-thread-only":
            raise ValueError(
                f"authorized_skills must not grant main-thread-only skill {skill_name!r}"
            )
        raise ValueError(
            "authorized_skills is only for skills explicitly marked "
            f"dispatch-authorized in child-skill-policy.toml; got {skill_name!r}"
        )


def render_policy(policy: dict[str, object]) -> str:
    lines = [
        f"version = {policy['version']}",
        f'default_child_policy = "{policy["default_child_policy"]}"',
        "",
        "[skills]",
        "# Optional manual restrictions. Empty means child agents may use any skill.",
        "# Add entries only when you want to restrict a known local skill explicitly.",
        '# Example: "plan-execution" = "dispatch-authorized"',
        '# Example: "multi-agent" = "main-thread-only"',
    ]
    skills = policy["skills"]
    if not isinstance(skills, dict):
        raise ValueError("policy.skills must be a mapping")
    for name, value in skills.items():
        lines.append(f'"{name}" = "{value}"')
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    policy = load_policy(args.policy.resolve())
    rendered = render_policy(policy)
    if args.write:
        args.policy.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
