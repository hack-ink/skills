#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plan_contract import parse_contract_text, render_contract_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize a plan/1 contract into the canonical fenced-markdown form."
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="Optional plan file to read. If omitted, read raw input from stdin.",
    )
    return parser.parse_args()


def read_input(args: argparse.Namespace) -> str:
    if args.path is None:
        return sys.stdin.read()
    return args.path.read_text(encoding="utf-8")


def main() -> int:
    args = parse_args()
    raw_text = read_input(args)
    result = parse_contract_text(raw_text, require_fence=False)
    if not result.ok or result.contract is None:
        for error in result.errors:
            print(f"plan/1 invalid: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(render_contract_markdown(result.contract, result.tail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
