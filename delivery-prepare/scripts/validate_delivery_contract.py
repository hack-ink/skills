#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from typing import Any, NoReturn


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


def fail(msg: str) -> NoReturn:
	print(f"delivery/1 invalid: {msg}", file=sys.stderr)
	raise SystemExit(2)


def require_non_empty_string(obj: dict[str, Any], key: str) -> None:
	value = obj.get(key)
	if not isinstance(value, str) or not value.strip():
		fail(f"{key} must be a non-empty string")


def validate_ref(ref: Any, index: int) -> dict[str, Any]:
	if not isinstance(ref, dict):
		fail(f"refs[{index}] must be an object")

	system = ref.get("system")
	if system == "linear":
		expected_keys = {"system", "id", "role"}
		if set(ref) != expected_keys:
			fail(f"refs[{index}] linear refs must use keys {sorted(expected_keys)}")
		if ref.get("role") not in {"authority", "related"}:
			fail(f"refs[{index}] linear role must be authority or related")
		ref_id = ref.get("id")
		if not isinstance(ref_id, str) or not LINEAR_REF_RE.match(ref_id):
			fail(f"refs[{index}] linear id must be in TEAM-123 form")
		return {
			"system": "linear",
			"id": ref_id,
			"role": ref["role"],
		}

	if system == "github":
		expected_keys = {"system", "repo", "number", "role"}
		if set(ref) != expected_keys:
			fail(f"refs[{index}] GitHub refs must use keys {sorted(expected_keys)}")
		if ref.get("role") != "mirror":
			fail(f"refs[{index}] GitHub role must be mirror")
		repo = ref.get("repo")
		if not isinstance(repo, str) or not GITHUB_REPO_RE.match(repo):
			fail(f"refs[{index}] GitHub repo must be in owner/repo form")
		number = ref.get("number")
		if not isinstance(number, int) or number <= 0:
			fail(f"refs[{index}] GitHub number must be a positive integer")
		return {
			"system": "github",
			"repo": repo,
			"number": number,
			"role": "mirror",
		}

	fail(f"refs[{index}] system must be linear or github")


def ref_key(ref: dict[str, Any]) -> tuple[object, ...]:
	if ref["system"] == "linear":
		return ("linear", ref["id"])
	return ("github", ref["repo"], ref["number"])


def main() -> None:
	raw = sys.stdin.read()
	text = raw.strip()
	if not text:
		fail("empty commit message")
	if "\n" in text or "\r" in text:
		fail("must be a single line JSON object")

	try:
		obj: Any = json.loads(text)
	except json.JSONDecodeError as err:
		fail(f"invalid JSON ({err})")

	if not isinstance(obj, dict):
		fail("top-level must be a JSON object")
	missing = sorted(TOP_LEVEL_KEYS - set(obj))
	if missing:
		fail(f"missing keys: {missing}")
	extra = sorted(set(obj) - TOP_LEVEL_KEYS)
	if extra:
		fail(f"unexpected keys: {extra}")

	require_non_empty_string(obj, "type")
	require_non_empty_string(obj, "scope")
	require_non_empty_string(obj, "summary")
	require_non_empty_string(obj, "intent")
	require_non_empty_string(obj, "impact")

	if obj.get("schema") != "delivery/1":
		fail("schema must be exactly 'delivery/1'")
	if not isinstance(obj.get("breaking"), bool):
		fail("breaking must be a boolean")
	if obj.get("risk") not in ("low", "medium", "high"):
		fail("risk must be one of: low, medium, high")
	if obj.get("authority") != "linear":
		fail("authority must be exactly 'linear'")
	if obj.get("delivery_mode") not in ("closeout", "status-only", "reopen"):
		fail("delivery_mode must be one of: closeout, status-only, reopen")

	refs = obj.get("refs")
	if not isinstance(refs, list):
		fail("refs must be an array")
	if not refs:
		fail("refs must be a non-empty array")

	authority_count = 0
	seen_refs: dict[tuple[object, ...], dict[str, Any]] = {}
	for index, ref in enumerate(refs):
		validated_ref = validate_ref(ref, index)
		key = ref_key(validated_ref)
		previous = seen_refs.get(key)
		if previous is not None:
			if previous != validated_ref:
				fail(f"refs[{index}] duplicates an existing ref with a conflicting role")
			continue
		seen_refs[key] = validated_ref
		if validated_ref["system"] == "linear" and validated_ref["role"] == "authority":
			authority_count += 1

	if authority_count != 1:
		fail("refs must contain exactly one Linear authority ref")

	print("OK")


if __name__ == "__main__":
	main()
