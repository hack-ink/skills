#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from typing import Any


REQUIRED_KEYS = [
	"schema",
	"type",
	"scope",
	"summary",
	"intent",
	"impact",
	"breaking",
	"risk",
	"refs",
]


def fail(msg: str) -> "Never":  # type: ignore[name-defined]
	print(f"cmsg/1 invalid: {msg}", file=sys.stderr)
	raise SystemExit(2)


def main() -> None:
	raw = sys.stdin.read()
	text = raw.strip()
	if not text:
		fail("empty commit message")
	if "\n" in text or "\r" in text:
		fail("must be a single line JSON object")

	try:
		obj: Any = json.loads(text)
	except json.JSONDecodeError as e:
		fail(f"invalid JSON ({e})")

	if not isinstance(obj, dict):
		fail("top-level must be a JSON object")

	missing = [k for k in REQUIRED_KEYS if k not in obj]
	if missing:
		fail(f"missing keys: {missing}")

	if obj.get("schema") != "cmsg/1":
		fail("schema must be exactly 'cmsg/1'")
	if not isinstance(obj.get("breaking"), bool):
		fail("breaking must be a boolean")
	if not isinstance(obj.get("refs"), list):
		fail("refs must be an array")
	if obj.get("risk") not in ("low", "medium", "high"):
		fail("risk must be one of: low, medium, high")

	print("OK")


if __name__ == "__main__":
	main()

