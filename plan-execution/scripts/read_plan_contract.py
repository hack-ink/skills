#!/usr/bin/env python3
"""Read and validate a saved plan/1 contract from a plan file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from plan_contract import parse_contract_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read and validate a saved plan/1 contract from a plan file."
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="Plan file to inspect. Required unless --stdin is used.",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read the saved plan file content from stdin instead of --path.",
    )
    return parser.parse_args()


def read_input(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.stdin:
        return sys.stdin.read(), None
    if args.path is None:
        raise ValueError("--path is required unless --stdin is used")
    path = args.path.resolve()
    if not path.exists():
        raise ValueError(f"plan file path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"plan file path is not a file: {path}")
    return path.read_text(encoding="utf-8"), str(path)


def empty_result(*, path: str | None) -> dict[str, object]:
    return {
        "ok": False,
        "path": path,
        "plan_id": None,
        "phase": None,
        "current_task_id": None,
        "next_task_id": None,
        "task_ids": [],
        "tail_present": False,
        "migration_required": False,
        "contract": None,
        "errors": [],
    }


def build_result(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        raw_text, path = read_input(args)
    except ValueError as err:
        result = empty_result(path=None)
        result["errors"] = [str(err)]
        return result, 2

    result = empty_result(path=path)
    parsed = parse_contract_text(raw_text, require_fence=True)
    result["tail_present"] = bool(parsed.tail.strip())
    result["migration_required"] = parsed.migration_required
    if not parsed.ok or parsed.contract is None:
        result["errors"] = parsed.errors
        return result, 2

    contract = parsed.contract
    spec = contract["spec"]
    state = contract["state"]
    result["ok"] = True
    result["plan_id"] = spec["plan_id"]
    result["phase"] = state["phase"]
    result["current_task_id"] = state["current_task_id"]
    result["next_task_id"] = state["next_task_id"]
    result["task_ids"] = [task["id"] for task in spec["tasks"]]
    result["contract"] = contract
    return result, 0


def main() -> int:
    args = parse_args()
    payload, exit_code = build_result(args)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
