#!/usr/bin/env python3
"""Compute review coverage from a review ledger and git blob SHAs."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


Status = dict[str, str]


def run(cmd: List[str], cwd: Path) -> str:
    try:
        result = subprocess.check_output(cmd, cwd=str(cwd), text=True)
    except subprocess.CalledProcessError as err:
        raise SystemExit(f"git command failed ({' '.join(cmd)}): {err}") from err
    return result


def git_ls_files(repo_root: Path, pathspec: List[str] | None = None) -> List[str]:
    command = ["git", "ls-files", "-z"]
    if pathspec:
        command.extend(["--", *pathspec])
    output = run(command, repo_root)
    return [item for item in output.split("\x00") if item]


def git_blob_sha(repo_root: Path, revision: str, path: str) -> str:
    return run(["git", "rev-parse", f"{revision}:{path}"], repo_root).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check review coverage against a ledger.")
    parser.add_argument("--repo-root", default=".", dest="repo_root")
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--scope-file", help="Optional newline-separated list of in-scope files.")
    parser.add_argument(
        "--pathspec",
        action="append",
        default=[],
        help="Repeatable git pathspec to narrow scope.",
    )
    parser.add_argument("--rev", default="HEAD", help="Git revision for blob SHA lookup.")
    parser.add_argument("--min-coverage", type=float, default=100.0)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob-style patterns of files to exclude from scope.",
    )
    return parser.parse_args()


def resolve_repo_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path


def in_scope(path: str, excludes: List[str]) -> bool:
    return not any(fnmatch.fnmatch(path, pattern) for pattern in excludes)


def read_scope(path: str) -> List[str]:
    scope = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value and not value.startswith("#"):
                scope.append(value)
    return scope


def load_ledger(path: str) -> Status:
    rows = {}
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"reviewed_file", "blob_sha", "status"}
        if not required.issubset(reader.fieldnames or set()):
            raise SystemExit("Ledger must include reviewed_file, blob_sha, and status columns")
        for row in reader:
            file_path = row["reviewed_file"].strip()
            status = row["status"].strip().lower()
            if not file_path or file_path.startswith("#"):
                continue
            rows[file_path] = {
                "blob_sha": row["blob_sha"].strip(),
                "status": status,
            }
    return rows


def main() -> int:
    args = parse_args()
    if args.scope_file and args.pathspec:
        raise SystemExit(
            "--scope-file and --pathspec are mutually exclusive; use one scope mode per run."
        )
    repo_root = Path(args.repo_root).resolve()
    if not (repo_root / ".git").exists():
        raise SystemExit(
            f"{repo_root} is not a git repository; pass a git repo to --repo-root",
        )

    ledger_path = resolve_repo_path(repo_root, args.ledger)
    ledger = load_ledger(str(ledger_path))
    if args.scope_file:
        scope_path = resolve_repo_path(repo_root, args.scope_file)
        raw_scope = read_scope(str(scope_path))
    else:
        raw_scope = git_ls_files(repo_root, args.pathspec or None)

    scope = [path for path in raw_scope if in_scope(path, args.exclude)]

    covered = 0
    missing: List[str] = []
    stale: List[Tuple[str, str, str]] = []
    wrong_status: List[str] = []

    for path in scope:
        current_sha = git_blob_sha(repo_root, args.rev, path)
        record = ledger.get(path)
        if not record:
            missing.append(path)
            continue
        if record.get("status") != "approved":
            wrong_status.append(path)
            continue
        if record.get("blob_sha") == current_sha:
            covered += 1
        else:
            stale.append((path, record.get("blob_sha", ""), current_sha))

    total = len(scope)
    coverage = (covered / total * 100) if total else 0.0

    print("Review coverage report")
    print(f"Revision: {args.rev}")
    print(f"Scope size: {total}")
    print(f"Covered: {covered}")
    print(f"Coverage: {coverage:.2f}%")
    print(f"Min required: {args.min_coverage:.2f}%")
    if missing:
        print(f"Missing ledger: {len(missing)}")
    if stale:
        print(f"Stale SHA: {len(stale)}")
    if wrong_status:
        print(f"Not approved: {len(wrong_status)}")

    if stale:
        for name, ledger_sha, live_sha in stale[:20]:
            print(f"  STALE {name} ledger={ledger_sha} live={live_sha}")
    if missing:
        for name in missing[:20]:
            print(f"  MISSING {name}")
    if wrong_status:
        for name in wrong_status[:20]:
            print(f"  NOT_APPROVED {name}")

    if coverage + 1e-9 < args.min_coverage:
        print("COVERAGE_FAIL")
        return 1
    print("COVERAGE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
