#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


LINEAR_REF_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")
GITHUB_REF_RE = re.compile(
	r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)#(?P<number>\d+)$"
)


def parse_linear_ref(raw: str) -> str:
	text = raw.strip()
	if not LINEAR_REF_RE.match(text):
		raise argparse.ArgumentTypeError("Linear refs must be in TEAM-123 form")
	return text


def parse_github_ref(raw: str) -> tuple[str, int]:
	text = raw.strip()
	match = GITHUB_REF_RE.match(text)
	if match is None:
		raise argparse.ArgumentTypeError(
			"GitHub refs must be in owner/repo#123 form"
		)
	return f"{match.group('owner')}/{match.group('repo')}", int(match.group("number"))


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Generate a single-line delivery/1 commit contract JSON."
	)
	parser.add_argument("--type", required=True)
	parser.add_argument("--scope", required=True)
	parser.add_argument("--summary", required=True)
	parser.add_argument("--intent", required=True)
	parser.add_argument("--impact", required=True)
	parser.add_argument("--breaking", action="store_true", default=False)
	parser.add_argument("--risk", choices=["low", "medium", "high"], default="low")
	parser.add_argument(
		"--delivery-mode",
		required=True,
		choices=["closeout", "status-only", "reopen"],
	)
	parser.add_argument(
		"--authority-linear-ref",
		required=True,
		type=parse_linear_ref,
	)
	parser.add_argument(
		"--linear-ref",
		action="append",
		type=parse_linear_ref,
		default=[],
	)
	parser.add_argument(
		"--github-ref",
		action="append",
		type=parse_github_ref,
		default=[],
	)
	return parser.parse_args()


def ref_key(ref: dict[str, Any]) -> tuple[object, ...]:
	if ref["system"] == "linear":
		return ("linear", ref["id"])
	return ("github", ref["repo"], ref["number"])


def fail(msg: str) -> None:
	print(f"delivery/1 invalid: {msg}", file=sys.stderr)
	raise SystemExit(2)


def append_ref(
	refs: list[dict[str, Any]],
	seen: dict[tuple[object, ...], dict[str, Any]],
	ref: dict[str, Any],
) -> None:
	key = ref_key(ref)
	previous = seen.get(key)
	if previous is not None:
		if previous != ref:
			fail(
				f"conflicting duplicate ref for {key!r}: {previous['role']} vs {ref['role']}"
			)
		return
	seen[key] = ref
	refs.append(ref)


def main() -> None:
	args = parse_args()
	refs: list[dict[str, Any]] = []
	seen: dict[tuple[object, ...], dict[str, Any]] = {}
	append_ref(
		refs,
		seen,
		{
			"system": "linear",
			"id": args.authority_linear_ref,
			"role": "authority",
		},
	)
	for linear_ref in args.linear_ref:
		append_ref(
			refs,
			seen,
			{"system": "linear", "id": linear_ref, "role": "related"},
		)
	for github_repo, github_number in args.github_ref:
		append_ref(
			refs,
			seen,
			{
				"system": "github",
				"repo": github_repo,
				"number": github_number,
				"role": "mirror",
			}
		)

	contract: dict[str, Any] = {
		"schema": "delivery/1",
		"type": args.type,
		"scope": args.scope,
		"summary": args.summary,
		"intent": args.intent,
		"impact": args.impact,
		"breaking": bool(args.breaking),
		"risk": args.risk,
		"authority": "linear",
		"delivery_mode": args.delivery_mode,
		"refs": refs,
	}
	sys.stdout.write(json.dumps(contract, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
	main()
