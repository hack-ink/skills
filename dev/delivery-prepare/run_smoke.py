#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "delivery-prepare" / "scripts" / "build_delivery_contract.py"
VALIDATOR = (
    REPO_ROOT / "delivery-prepare" / "scripts" / "validate_delivery_contract.py"
)
FALLBACK_VALIDATOR_SCRIPT = """
import json
import re
import sys

text = sys.stdin.read().strip()
assert text and "\\n" not in text and "\\r" not in text, "delivery/1 must be single-line JSON"
payload = json.loads(text)
required = "schema type scope summary intent impact breaking risk authority delivery_mode refs".split()
missing = [key for key in required if key not in payload]
assert not missing, missing
extra = sorted(set(payload) - set(required))
assert not extra, extra
assert payload["schema"] == "delivery/1"
assert payload["authority"] == "linear"
assert payload["delivery_mode"] in ("closeout", "status-only", "reopen")
assert isinstance(payload["breaking"], bool)
assert payload["risk"] in ("low", "medium", "high")
assert all(isinstance(payload[key], str) and payload[key].strip() for key in ("type", "scope", "summary", "intent", "impact"))
refs = payload["refs"]
assert isinstance(refs, list) and refs
linear_re = re.compile(r"^[A-Z][A-Z0-9]*-\\d+$")
github_re = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
seen = {}
authority_count = 0
for ref in refs:
    assert isinstance(ref, dict), "invalid ref object"
    if ref.get("system") == "linear":
        assert set(ref) == {"system", "id", "role"}, "invalid linear ref"
        assert linear_re.match(ref["id"]), "invalid linear ref"
        assert ref["role"] in ("authority", "related"), "invalid linear ref"
        key = ("linear", ref["id"])
    elif ref.get("system") == "github":
        assert set(ref) == {"system", "repo", "number", "role"}, "invalid github ref"
        assert github_re.match(ref["repo"]), "invalid github ref"
        assert isinstance(ref["number"], int) and ref["number"] > 0, "invalid github ref"
        assert ref["role"] == "mirror", "invalid github ref"
        key = ("github", ref["repo"], ref["number"])
    else:
        raise AssertionError("invalid ref object")
    previous = seen.get(key)
    if previous is not None:
        assert previous == ref, ("conflicting duplicate ref", key)
        continue
    seen[key] = ref
    if ref["system"] == "linear" and ref["role"] == "authority":
        authority_count += 1
assert authority_count == 1
""".strip()
FALLBACK_VALIDATOR = [
    "python3",
    "-c",
    FALLBACK_VALIDATOR_SCRIPT,
]


def run(
    cmd: list[str],
    cwd: Path,
    *,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        input=input_text,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(cmd)}\n"
            f"cwd: {cwd}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_invalid_contract(*, refs: object, **overrides: object) -> str:
    payload = {
        "schema": "delivery/1",
        "type": "chore",
        "scope": "delivery-prepare-smoke",
        "summary": "exercise validator",
        "intent": "smoke test",
        "impact": "validate delivery contract",
        "breaking": False,
        "risk": "low",
        "authority": "linear",
        "delivery_mode": "closeout",
        "refs": refs,
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":"))


def main() -> None:
    missing_authority = run(
        [
            "python3",
            str(GENERATOR),
            "--type",
            "chore",
            "--scope",
            "delivery-prepare-smoke",
            "--summary",
            "missing authority ref",
            "--intent",
            "smoke test",
            "--impact",
            "validate required authority ref",
            "--risk",
            "low",
            "--delivery-mode",
            "closeout",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert_equal(
        missing_authority.returncode,
        2,
        "generator should reject missing authority linear ref",
    )
    assert_true(
        "--authority-linear-ref" in missing_authority.stderr,
        "generator error should mention --authority-linear-ref",
    )
    print("OK: generator rejects missing authority linear ref")

    missing_mode = run(
        [
            "python3",
            str(GENERATOR),
            "--type",
            "chore",
            "--scope",
            "delivery-prepare-smoke",
            "--summary",
            "missing delivery mode",
            "--intent",
            "smoke test",
            "--impact",
            "validate required delivery mode",
            "--risk",
            "low",
            "--authority-linear-ref",
            "PUB-582",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert_equal(missing_mode.returncode, 2, "generator should reject missing mode")
    assert_true(
        "--delivery-mode" in missing_mode.stderr,
        "generator error should mention --delivery-mode",
    )
    print("OK: generator rejects missing delivery mode")

    generated = run(
        [
            "python3",
            str(GENERATOR),
            "--type",
            "chore",
            "--scope",
            "delivery-prepare-smoke",
            "--summary",
            "valid delivery contract",
            "--intent",
            "smoke test",
            "--impact",
            "validate generator",
            "--risk",
            "low",
            "--delivery-mode",
            "closeout",
            "--authority-linear-ref",
            "PUB-582",
            "--linear-ref",
            "PUB-600",
            "--github-ref",
            "hack-ink/ELF#30",
        ],
        cwd=REPO_ROOT,
    )
    payload = json.loads(generated.stdout)
    assert_equal(payload["schema"], "delivery/1", "generator schema")
    assert_equal(payload["authority"], "linear", "generator authority")
    assert_equal(payload["delivery_mode"], "closeout", "generator delivery mode")
    assert_equal(
        payload["refs"],
        [
            {"system": "linear", "id": "PUB-582", "role": "authority"},
            {"system": "linear", "id": "PUB-600", "role": "related"},
            {
                "system": "github",
                "repo": "hack-ink/ELF",
                "number": 30,
                "role": "mirror",
            },
        ],
        "generator refs",
    )
    print("OK: generator emits delivery/1 typed refs")

    generated_dupes = run(
        [
            "python3",
            str(GENERATOR),
            "--type",
            "chore",
            "--scope",
            "delivery-prepare-smoke",
            "--summary",
            "duplicate refs",
            "--intent",
            "smoke test",
            "--impact",
            "validate dedupe",
            "--risk",
            "low",
            "--delivery-mode",
            "closeout",
            "--authority-linear-ref",
            "PUB-582",
            "--linear-ref",
            "PUB-600",
            "--linear-ref",
            "PUB-600",
            "--github-ref",
            "hack-ink/ELF#30",
            "--github-ref",
            "hack-ink/ELF#30",
        ],
        cwd=REPO_ROOT,
    )
    dupes_payload = json.loads(generated_dupes.stdout)
    assert_equal(
        dupes_payload["refs"],
        [
            {"system": "linear", "id": "PUB-582", "role": "authority"},
            {"system": "linear", "id": "PUB-600", "role": "related"},
            {
                "system": "github",
                "repo": "hack-ink/ELF",
                "number": 30,
                "role": "mirror",
            },
        ],
        "generator should dedupe repeated refs by target",
    )
    print("OK: generator deduplicates repeated refs")

    conflicting_generator = run(
        [
            "python3",
            str(GENERATOR),
            "--type",
            "chore",
            "--scope",
            "delivery-prepare-smoke",
            "--summary",
            "conflicting duplicate refs",
            "--intent",
            "smoke test",
            "--impact",
            "reject conflicting duplicates",
            "--risk",
            "low",
            "--delivery-mode",
            "closeout",
            "--authority-linear-ref",
            "PUB-582",
            "--linear-ref",
            "PUB-582",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert_equal(
        conflicting_generator.returncode,
        2,
        "generator should reject conflicting duplicate refs",
    )
    assert_true(
        "conflicting duplicate ref" in conflicting_generator.stderr,
        "generator error should mention conflicting duplicate refs",
    )
    print("OK: generator rejects conflicting duplicate refs")

    string_ref_validation = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(refs=["PUB-582"]),
        check=False,
    )
    assert_equal(
        string_ref_validation.returncode,
        2,
        "validator should reject string refs",
    )
    assert_true(
        "refs[0] must be an object" in string_ref_validation.stderr,
        "validator error should mention string refs are invalid",
    )
    print("OK: validator rejects string refs")

    missing_authority_field = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=json.dumps(
            {
                "schema": "delivery/1",
                "type": "chore",
                "scope": "delivery-prepare-smoke",
                "summary": "missing authority",
                "intent": "smoke test",
                "impact": "validate missing authority",
                "breaking": False,
                "risk": "low",
                "delivery_mode": "closeout",
                "refs": [{"system": "linear", "id": "PUB-582", "role": "authority"}],
            },
            separators=(",", ":"),
        ),
        check=False,
    )
    assert_equal(
        missing_authority_field.returncode,
        2,
        "validator should reject missing authority field",
    )
    assert_true(
        "missing keys: ['authority']" in missing_authority_field.stderr,
        "validator error should mention missing authority",
    )
    print("OK: validator rejects missing authority")

    invalid_mode = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[{"system": "linear", "id": "PUB-582", "role": "authority"}],
            delivery_mode="ship",
        ),
        check=False,
    )
    assert_equal(invalid_mode.returncode, 2, "validator should reject invalid mode")
    assert_true(
        "delivery_mode must be one of: closeout, status-only, reopen"
        in invalid_mode.stderr,
        "validator error should mention invalid mode",
    )
    print("OK: validator rejects invalid delivery mode")

    zero_authority = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {"system": "linear", "id": "PUB-600", "role": "related"},
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "mirror",
                },
            ]
        ),
        check=False,
    )
    assert_equal(
        zero_authority.returncode,
        2,
        "validator should reject missing authority ref",
    )
    assert_true(
        "refs must contain exactly one Linear authority ref" in zero_authority.stderr,
        "validator error should mention missing authority ref",
    )
    print("OK: validator rejects zero authority refs")

    multiple_authority = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {"system": "linear", "id": "PUB-600", "role": "authority"},
            ]
        ),
        check=False,
    )
    assert_equal(
        multiple_authority.returncode,
        2,
        "validator should reject multiple authority refs",
    )
    assert_true(
        "refs must contain exactly one Linear authority ref"
        in multiple_authority.stderr,
        "validator error should mention multiple authority refs",
    )
    print("OK: validator rejects multiple authority refs")

    github_as_authority = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "authority",
                }
            ]
        ),
        check=False,
    )
    assert_equal(
        github_as_authority.returncode,
        2,
        "validator should reject non-linear authority refs",
    )
    assert_true(
        "GitHub role must be mirror" in github_as_authority.stderr,
        "validator error should mention GitHub authority refs are invalid",
    )
    print("OK: validator rejects non-linear authority refs")

    github_missing_repo = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {"system": "github", "number": 30, "role": "mirror"},
            ]
        ),
        check=False,
    )
    assert_equal(
        github_missing_repo.returncode,
        2,
        "validator should reject GitHub refs missing repo",
    )
    assert_true(
        "GitHub refs must use keys" in github_missing_repo.stderr,
        "validator error should mention GitHub repo shape",
    )
    print("OK: validator rejects GitHub refs missing repo")

    conflicting_duplicate_validation = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {"system": "linear", "id": "PUB-582", "role": "related"},
            ]
        ),
        check=False,
    )
    assert_equal(
        conflicting_duplicate_validation.returncode,
        2,
        "validator should reject conflicting duplicate refs",
    )
    assert_true(
        "duplicates an existing ref with a conflicting role"
        in conflicting_duplicate_validation.stderr,
        "validator error should mention conflicting duplicate refs",
    )
    print("OK: validator rejects conflicting duplicate refs")

    duplicate_validation = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "mirror",
                },
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "mirror",
                },
            ]
        ),
        check=False,
    )
    assert_equal(
        duplicate_validation.returncode,
        0,
        "validator should accept exact duplicate refs",
    )
    assert_equal(
        duplicate_validation.stdout.strip(),
        "OK",
        "validator success output for exact duplicates",
    )
    print("OK: validator accepts exact duplicate refs")

    fallback_bad_github = run(
        FALLBACK_VALIDATOR,
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {"system": "github", "role": "mirror"},
            ]
        ),
        check=False,
    )
    assert_equal(
        fallback_bad_github.returncode,
        1,
        "fallback validator should reject malformed GitHub refs",
    )
    print("OK: fallback validator rejects malformed GitHub refs")

    fallback_conflicting_duplicate = run(
        FALLBACK_VALIDATOR,
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {"system": "linear", "id": "PUB-582", "role": "related"},
            ]
        ),
        check=False,
    )
    assert_equal(
        fallback_conflicting_duplicate.returncode,
        1,
        "fallback validator should reject conflicting duplicate refs",
    )
    print("OK: fallback validator rejects conflicting duplicate refs")

    fallback_duplicate_valid = run(
        FALLBACK_VALIDATOR,
        cwd=REPO_ROOT,
        input_text=build_invalid_contract(
            refs=[
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "mirror",
                },
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "mirror",
                },
            ]
        ),
        check=False,
    )
    assert_equal(
        fallback_duplicate_valid.returncode,
        0,
        "fallback validator should accept exact duplicate refs",
    )
    print("OK: fallback validator accepts exact duplicate refs")

    valid_validation = run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        input_text=generated.stdout,
    )
    assert_equal(valid_validation.stdout.strip(), "OK", "validator success output")
    print("OK: validator accepts valid delivery/1 contracts")

    fallback_valid = run(
        FALLBACK_VALIDATOR,
        cwd=REPO_ROOT,
        input_text=generated.stdout,
    )
    assert_equal(fallback_valid.returncode, 0, "fallback validator success exit")
    print("OK: fallback validator accepts valid delivery/1 contracts")


if __name__ == "__main__":
    main()
