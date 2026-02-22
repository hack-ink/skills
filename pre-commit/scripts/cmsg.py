#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser(description="Generate a single-line cmsg/1 commit message JSON.")
	p.add_argument("--type", required=True)
	p.add_argument("--scope", required=True)
	p.add_argument("--summary", required=True)
	p.add_argument("--intent", required=True)
	p.add_argument("--impact", required=True)
	p.add_argument("--breaking", action="store_true", default=False)
	p.add_argument("--risk", choices=["low", "medium", "high"], default="low")
	p.add_argument("--ref", action="append", default=[])
	return p.parse_args()


def main() -> None:
	args = parse_args()
	msg: dict[str, Any] = {
		"schema": "cmsg/1",
		"type": args.type,
		"scope": args.scope,
		"summary": args.summary,
		"intent": args.intent,
		"impact": args.impact,
		"breaking": bool(args.breaking),
		"risk": args.risk,
		"refs": list(args.ref),
	}
	sys.stdout.write(json.dumps(msg, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
	main()

