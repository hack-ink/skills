#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import re
import sys


SCENARIO_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate an ssot_id as scenario-hash (stable, no dates, no secrets)."
    )
    p.add_argument(
        "scenario",
        help="Scenario slug (ASCII kebab-case), e.g. 'pack-configs-pubfi-cli'",
    )
    p.add_argument(
        "--hex-len",
        type=int,
        default=12,
        help="Hex length for token prefix (default: 12; range: 8..64).",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    scenario = args.scenario.strip()
    if not SCENARIO_RE.fullmatch(scenario):
        print(
            "ERROR: scenario must be ASCII kebab-case, e.g. 'pack-configs-pubfi-cli'",
            file=sys.stderr,
        )
        return 2

    hex_len = int(args.hex_len)
    if hex_len < 8 or hex_len > 64:
        print("ERROR: --hex-len must be 8..64", file=sys.stderr)
        return 2

    token = hashlib.sha256(scenario.encode("utf-8")).hexdigest()[:hex_len]

    print(f"{scenario}-{token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
