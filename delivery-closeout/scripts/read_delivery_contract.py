#!/usr/bin/env python3
"""Read and validate a delivery/1 contract from git, stdin, or a file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


LINEAR_REF_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")
GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TOP_LEVEL_KEYS = {
    "schema",
    "type",
    "scope",
    "summary",
    "intent",
    "impact",
    "breaking",
    "risk",
    "authority",
    "delivery_mode",
    "refs",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read and validate a delivery/1 contract from git, stdin, or a file."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Git repository to inspect. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--rev",
        default="HEAD",
        help=(
            "Git revision whose commit message carries the contract when not using "
            "--stdin or --contract-file. Defaults to HEAD."
        ),
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--stdin",
        action="store_true",
        help="Read the delivery/1 contract from stdin instead of git log.",
    )
    source_group.add_argument(
        "--contract-file",
        type=Path,
        help="Read the delivery/1 contract from a file instead of git log.",
    )
    parser.add_argument(
        "--anchor-rev",
        help=(
            "Git revision to use as the closeout anchor commit. Defaults to --rev "
            "when reading from git. Required for --stdin/--contract-file."
        ),
    )
    return parser.parse_args()


def run_git(repo: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as err:
        raise ValueError(f"failed to run git in {repo}: {err}") from err
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "git command failed")
    return proc.stdout.strip()


def resolve_repo(repo_arg: Path) -> Path:
    repo = repo_arg.resolve()
    if not repo.exists():
        raise ValueError(f"git repository path does not exist: {repo}")
    if not repo.is_dir():
        raise ValueError(f"git repository path is not a directory: {repo}")
    return repo


def resolve_commit_sha(repo: Path, rev: str) -> str:
    return run_git(repo, "rev-parse", rev)


def read_contract_text(
    args: argparse.Namespace,
) -> tuple[str | None, str | None, str | None, str | None, str]:
    repo: Path | None = None
    if args.stdin:
        contract_source = "stdin"
        contract_rev = None
        contract_file = None
        raw_text = sys.stdin.read()
    elif args.contract_file is not None:
        contract_source = "file"
        contract_rev = None
        contract_path = args.contract_file.expanduser().resolve()
        contract_file = str(contract_path)
        if not contract_path.exists():
            raise ValueError(f"delivery contract file does not exist: {contract_path}")
        if not contract_path.is_file():
            raise ValueError(f"delivery contract file is not a regular file: {contract_path}")
        try:
            raw_text = contract_path.read_text(encoding="utf-8")
        except OSError as err:
            raise ValueError(
                f"failed to read delivery contract file {contract_path}: {err}"
            ) from err
    else:
        contract_source = "git"
        contract_rev = args.rev
        contract_file = None
        repo = resolve_repo(args.repo)
        raw_text = run_git(repo, "log", "-1", "--format=%B", args.rev)

    anchor_rev = args.anchor_rev
    if anchor_rev is None and contract_source in {"stdin", "file"}:
        raise ValueError(
            "anchor rev is required when reading a delivery/1 contract from stdin "
            "or --contract-file"
        )
    if anchor_rev is None and contract_source == "git":
        anchor_rev = args.rev
    commit_sha = None
    if anchor_rev is not None:
        if repo is None:
            repo = resolve_repo(args.repo)
        commit_sha = resolve_commit_sha(repo, anchor_rev)

    return commit_sha, contract_source, contract_rev, contract_file, raw_text


def require_non_empty_string(obj: dict[str, Any], key: str, errors: list[str]) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key} must be a non-empty string")


def validate_ref(ref: Any, index: int, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(ref, dict):
        errors.append(f"refs[{index}] must be an object")
        return None

    system = ref.get("system")
    if system == "linear":
        expected_keys = {"system", "id", "role"}
        if set(ref) != expected_keys:
            errors.append(
                f"refs[{index}] linear refs must use keys {sorted(expected_keys)}"
            )
            return None
        if ref.get("role") not in {"authority", "related"}:
            errors.append(f"refs[{index}] linear role must be authority or related")
            return None
        ref_id = ref.get("id")
        if not isinstance(ref_id, str) or not LINEAR_REF_RE.match(ref_id):
            errors.append(f"refs[{index}] linear id must be in TEAM-123 form")
            return None
        return {
            "system": "linear",
            "id": ref_id,
            "role": ref["role"],
        }

    if system == "github":
        expected_keys = {"system", "repo", "number", "role"}
        if set(ref) != expected_keys:
            errors.append(
                f"refs[{index}] GitHub refs must use keys {sorted(expected_keys)}"
            )
            return None
        if ref.get("role") != "mirror":
            errors.append(f"refs[{index}] GitHub role must be mirror")
            return None
        repo = ref.get("repo")
        if not isinstance(repo, str) or not GITHUB_REPO_RE.match(repo):
            errors.append(f"refs[{index}] GitHub repo must be in owner/repo form")
            return None
        number = ref.get("number")
        if not isinstance(number, int) or number <= 0:
            errors.append(f"refs[{index}] GitHub number must be a positive integer")
            return None
        return {
            "system": "github",
            "repo": repo,
            "number": number,
            "role": "mirror",
        }

    errors.append(f"refs[{index}] system must be linear or github")
    return None


def ref_key(ref: dict[str, Any]) -> tuple[object, ...]:
    if ref["system"] == "linear":
        return ("linear", ref["id"])
    return ("github", ref["repo"], ref["number"])


def load_contract(raw_text: str) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    text = raw_text.strip()
    if not text:
        return None, ["delivery/1 input is empty"]
    if "\n" in text or "\r" in text:
        return None, ["delivery/1 input must be a single line JSON object"]

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as err:
        return None, [f"delivery/1 input is not valid JSON: {err}"]

    if not isinstance(payload, dict):
        return None, ["delivery/1 input must decode to a JSON object"]
    missing = sorted(TOP_LEVEL_KEYS - set(payload))
    if missing:
        errors.append(f"missing keys: {missing}")
    extra = sorted(set(payload) - TOP_LEVEL_KEYS)
    if extra:
        errors.append(f"unexpected keys: {extra}")

    require_non_empty_string(payload, "type", errors)
    require_non_empty_string(payload, "scope", errors)
    require_non_empty_string(payload, "summary", errors)
    require_non_empty_string(payload, "intent", errors)
    require_non_empty_string(payload, "impact", errors)

    if payload.get("schema") != "delivery/1":
        errors.append("delivery/1 schema must be exactly delivery/1")
    if not isinstance(payload.get("breaking"), bool):
        errors.append("delivery/1 breaking must be a boolean")
    if payload.get("risk") not in ("low", "medium", "high"):
        errors.append("delivery/1 risk must be one of: low, medium, high")
    if payload.get("authority") != "linear":
        errors.append("delivery/1 authority must be exactly linear")
    if payload.get("delivery_mode") not in ("closeout", "status-only", "reopen"):
        errors.append(
            "delivery/1 delivery_mode must be one of: closeout, status-only, reopen"
        )

    refs = payload.get("refs")
    if not isinstance(refs, list):
        errors.append("delivery/1 refs must be an array")
    else:
        authority_count = 0
        related_count = 0
        unique_refs: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        seen_refs: dict[tuple[object, ...], dict[str, Any]] = {}
        for index, ref in enumerate(refs):
            validated_ref = validate_ref(ref, index, errors)
            if validated_ref is None:
                continue
            key = ref_key(validated_ref)
            previous = seen_refs.get(key)
            if previous is not None:
                if previous != validated_ref:
                    errors.append(
                        f"refs[{index}] duplicates an existing ref with a conflicting role"
                    )
                else:
                    duplicates.append(validated_ref)
                continue
            seen_refs[key] = validated_ref
            unique_refs.append(validated_ref)
            if validated_ref["system"] == "linear" and validated_ref["role"] == "authority":
                authority_count += 1
            if validated_ref["system"] == "linear" and validated_ref["role"] == "related":
                related_count += 1
        if authority_count > 1:
            errors.append("delivery/1 refs may contain at most one Linear authority ref")
        if authority_count == 0 and related_count > 0:
            errors.append("delivery/1 linear related refs require a Linear authority ref")
        payload["refs"] = unique_refs
        payload["_duplicates"] = duplicates

    if errors:
        return payload, errors
    return payload, []


def empty_result(
    *,
    commit_sha: str | None,
    contract_source: str | None,
    contract_rev: str | None,
    contract_file: str | None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "commit_sha": commit_sha,
        "contract_source": contract_source,
        "contract_rev": contract_rev,
        "contract_file": contract_file,
        "schema": None,
        "authority": None,
        "delivery_mode": None,
        "refs": [],
        "authority_ref": None,
        "related_linear_refs": [],
        "github_mirror_refs": [],
        "duplicates": [],
        "errors": [],
    }


def build_result(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = empty_result(
        commit_sha=None,
        contract_source=None,
        contract_rev=None,
        contract_file=None,
    )
    try:
        commit_sha, contract_source, contract_rev, contract_file, raw_message = (
            read_contract_text(args)
        )
    except ValueError as err:
        result["errors"] = [str(err)]
        return result, 2

    payload, errors = load_contract(raw_message)
    result = empty_result(
        commit_sha=commit_sha,
        contract_source=contract_source,
        contract_rev=contract_rev,
        contract_file=contract_file,
    )
    if payload is not None:
        result["schema"] = payload.get("schema")
        result["authority"] = payload.get("authority")
        result["delivery_mode"] = payload.get("delivery_mode")
        result["refs"] = payload.get("refs", [])
        result["duplicates"] = payload.get("_duplicates", [])

    if errors:
        result["errors"] = errors
        return result, 2

    refs = payload["refs"]
    authority_ref = next(
        (
            ref
            for ref in refs
            if ref["system"] == "linear" and ref["role"] == "authority"
        ),
        None,
    )
    result["authority_ref"] = authority_ref
    result["related_linear_refs"] = [
        ref for ref in refs if ref["system"] == "linear" and ref["role"] == "related"
    ]
    result["github_mirror_refs"] = [
        ref for ref in refs if ref["system"] == "github" and ref["role"] == "mirror"
    ]
    result["ok"] = True
    return result, 0


def main() -> int:
    args = parse_args()
    payload, exit_code = build_result(args)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
