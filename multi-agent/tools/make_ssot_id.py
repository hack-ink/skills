#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import re
import secrets
import sys
import uuid


SCENARIO_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a protocol v2 ssot_id.")
    p.add_argument(
        "scenario",
        help="Scenario slug (ASCII kebab-case), e.g. 'pack-configs-pubfi-cli'",
    )
    p.add_argument(
        "--token",
        choices=["hex", "uuid", "sha256"],
        default="hex",
        help="Token strategy (default: hex).",
    )
    p.add_argument(
        "--hex-bytes",
        type=int,
        default=6,
        help="Bytes for hex token (default: 6 -> 12 hex chars). Ignored for uuid/sha256.",
    )
    p.add_argument(
        "--seed",
        default=None,
        help="Seed for sha256 token (required when --token sha256).",
    )
    p.add_argument(
        "--sha256-hex-len",
        type=int,
        default=12,
        help="Hex length for sha256 token prefix (default: 12).",
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

    if args.token == "uuid":
        token = str(uuid.uuid4())
    elif args.token == "sha256":
        if not args.seed:
            print("ERROR: --seed is required when --token sha256", file=sys.stderr)
            return 2
        hex_len = int(args.sha256_hex_len)
        if hex_len < 8 or hex_len > 64:
            print("ERROR: --sha256-hex-len must be 8..64", file=sys.stderr)
            return 2
        token = hashlib.sha256(args.seed.encode("utf-8")).hexdigest()[:hex_len]
    else:
        if args.hex_bytes < 4 or args.hex_bytes > 32:
            print("ERROR: --hex-bytes must be 4..32 (8..64 hex chars)", file=sys.stderr)
            return 2
        token = secrets.token_hex(args.hex_bytes)

    print(f"{scenario}-{token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

