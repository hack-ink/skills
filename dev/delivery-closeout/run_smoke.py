#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
READER = REPO_ROOT / "delivery-closeout" / "scripts" / "read_delivery_contract.py"
GENERATOR = (
    REPO_ROOT / "delivery-prepare" / "scripts" / "build_delivery_contract.py"
)


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


def init_repo(root: Path) -> None:
    run(["git", "init"], cwd=root)
    run(["git", "config", "user.name", "Smoke Tester"], cwd=root)
    run(["git", "config", "user.email", "smoke@example.com"], cwd=root)


def commit_message(root: Path, message: str) -> str:
    run(["git", "commit", "--allow-empty", "-m", message], cwd=root)
    return run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()


def build_contract(refs: object, *, schema: str = "delivery/1", delivery_mode: str = "closeout") -> str:
    return json.dumps(
        {
            "schema": schema,
            "type": "chore",
            "scope": "delivery-closeout-smoke",
            "summary": "exercise reader",
            "intent": "smoke test",
            "impact": "validate delivery contract reading",
            "breaking": False,
            "risk": "low",
            "authority": "linear",
            "delivery_mode": delivery_mode,
            "refs": refs,
        },
        separators=(",", ":"),
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="delivery-closeout-smoke-") as tmp_dir:
        temp_root = Path(tmp_dir)

        repo_ok = temp_root / "repo-ok"
        repo_ok.mkdir()
        init_repo(repo_ok)
        generated = run(
            [
                "python3",
                str(GENERATOR),
                "--type",
                "chore",
                "--scope",
                "delivery-closeout-smoke",
                "--summary",
                "valid delivery contract",
                "--intent",
                "smoke test",
                "--impact",
                "validate reader",
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
        commit_sha = commit_message(repo_ok, generated.stdout.strip())
        stdin_reader_cmd = [
            "python3",
            str(READER),
            "--repo",
            str(repo_ok),
            "--anchor-rev",
            commit_sha,
            "--stdin",
        ]
        ok_proc = run(
            ["python3", str(READER), "--repo", str(repo_ok)],
            cwd=REPO_ROOT,
        )
        ok_payload = json.loads(ok_proc.stdout)
        assert_true(ok_payload["ok"], "valid delivery contract should read successfully")
        assert_equal(ok_payload["commit_sha"], commit_sha, "reader commit sha")
        assert_equal(ok_payload["contract_source"], "git", "reader contract source")
        assert_equal(ok_payload["contract_rev"], "HEAD", "reader contract rev")
        assert_equal(ok_payload["contract_file"], None, "reader contract file")
        assert_equal(ok_payload["authority"], "linear", "reader authority")
        assert_equal(ok_payload["delivery_mode"], "closeout", "reader mode")
        assert_equal(
            ok_payload["authority_ref"],
            {"system": "linear", "id": "PUB-582", "role": "authority"},
            "reader authority ref",
        )
        assert_equal(
            ok_payload["related_linear_refs"],
            [{"system": "linear", "id": "PUB-600", "role": "related"}],
            "reader related refs",
        )
        assert_equal(
            ok_payload["github_mirror_refs"],
            [
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "mirror",
                }
            ],
            "reader GitHub mirrors",
        )
        assert_equal(ok_payload["duplicates"], [], "reader should not report duplicates")
        print("OK: generator output flows directly into reader without repo inference")

        untracked_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(refs=[]),
        )
        untracked_payload = json.loads(untracked_proc.stdout)
        assert_true(
            untracked_payload["ok"],
            "empty refs should read successfully for untracked delivery",
        )
        assert_equal(untracked_payload["authority_ref"], None, "reader authority ref for untracked delivery")
        assert_equal(untracked_payload["refs"], [], "reader refs for untracked delivery")
        print("OK: reader accepts untracked delivery contracts with empty refs")

        repo_anchor = temp_root / "repo-anchor"
        repo_anchor.mkdir()
        init_repo(repo_anchor)
        anchor_sha = commit_message(
            repo_anchor,
            build_contract(
                refs=[
                    {"system": "linear", "id": "PUB-582", "role": "authority"},
                    {
                        "system": "github",
                        "repo": "hack-ink/ELF",
                        "number": 30,
                        "role": "mirror",
                    },
                ],
                delivery_mode="status-only",
            ),
        )
        final_closeout_contract = build_contract(
            refs=[
                {"system": "linear", "id": "PUB-582", "role": "authority"},
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "mirror",
                },
            ],
            delivery_mode="closeout",
        )
        missing_anchor_stdin_proc = run(
            [
                "python3",
                str(READER),
                "--repo",
                str(repo_anchor),
                "--stdin",
            ],
            cwd=REPO_ROOT,
            input_text=final_closeout_contract,
            check=False,
        )
        assert_equal(
            missing_anchor_stdin_proc.returncode,
            2,
            "stdin closeout contract without an anchor should fail",
        )
        missing_anchor_stdin_payload = json.loads(missing_anchor_stdin_proc.stdout)
        assert_true(
            missing_anchor_stdin_payload["errors"]
            and "anchor rev is required" in missing_anchor_stdin_payload["errors"][0],
            "stdin closeout contract should require an explicit anchor",
        )
        print("OK: explicit stdin contracts require an anchor rev")

        anchored_stdin_proc = run(
            [
                "python3",
                str(READER),
                "--repo",
                str(repo_anchor),
                "--anchor-rev",
                anchor_sha,
                "--stdin",
            ],
            cwd=REPO_ROOT,
            input_text=final_closeout_contract,
        )
        anchored_stdin_payload = json.loads(anchored_stdin_proc.stdout)
        assert_true(
            anchored_stdin_payload["ok"],
            "stdin closeout contract should read successfully against an explicit anchor",
        )
        assert_equal(
            anchored_stdin_payload["commit_sha"],
            anchor_sha,
            "stdin anchor commit sha",
        )
        assert_equal(
            anchored_stdin_payload["contract_source"],
            "stdin",
            "stdin contract source",
        )
        assert_equal(
            anchored_stdin_payload["delivery_mode"],
            "closeout",
            "stdin contract mode",
        )
        print("OK: explicit stdin contracts can close out a pushed anchor without a new commit")

        contract_file = temp_root / "final-closeout.json"
        contract_file.write_text(final_closeout_contract, encoding="utf-8")
        missing_anchor_file_proc = run(
            [
                "python3",
                str(READER),
                "--repo",
                str(repo_anchor),
                "--contract-file",
                str(contract_file),
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        assert_equal(
            missing_anchor_file_proc.returncode,
            2,
            "file-based closeout contract without an anchor should fail",
        )
        missing_anchor_file_payload = json.loads(missing_anchor_file_proc.stdout)
        assert_true(
            missing_anchor_file_payload["errors"]
            and "anchor rev is required" in missing_anchor_file_payload["errors"][0],
            "file-based closeout contract should require an explicit anchor",
        )
        print("OK: explicit contract files require an anchor rev")

        anchored_file_proc = run(
            [
                "python3",
                str(READER),
                "--repo",
                str(repo_anchor),
                "--anchor-rev",
                anchor_sha,
                "--contract-file",
                str(contract_file),
            ],
            cwd=REPO_ROOT,
        )
        anchored_file_payload = json.loads(anchored_file_proc.stdout)
        assert_true(
            anchored_file_payload["ok"],
            "file-based closeout contract should read successfully against an explicit anchor",
        )
        assert_equal(
            anchored_file_payload["commit_sha"],
            anchor_sha,
            "file anchor commit sha",
        )
        assert_equal(
            anchored_file_payload["contract_source"],
            "file",
            "file contract source",
        )
        assert_equal(
            anchored_file_payload["contract_file"],
            str(contract_file.resolve()),
            "file contract path",
        )
        print("OK: explicit contract files can close out a pushed anchor without a new commit")

        duplicate_reader_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(
                refs=[
                    {"system": "linear", "id": "PUB-582", "role": "authority"},
                    {"system": "linear", "id": "PUB-582", "role": "authority"},
                    {"system": "linear", "id": "PUB-600", "role": "related"},
                    {"system": "linear", "id": "PUB-600", "role": "related"},
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
        )
        duplicate_reader_payload = json.loads(duplicate_reader_proc.stdout)
        assert_equal(
            duplicate_reader_payload["refs"],
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
            "reader should dedupe repeated refs by target",
        )
        assert_equal(
            duplicate_reader_payload["duplicates"],
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
            "reader should report skipped duplicates",
        )
        print("OK: reader deduplicates repeated refs")

        conflicting_duplicate_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(
                refs=[
                    {"system": "linear", "id": "PUB-582", "role": "authority"},
                    {"system": "linear", "id": "PUB-582", "role": "related"},
                ]
            ),
            check=False,
        )
        assert_equal(
            conflicting_duplicate_proc.returncode,
            2,
            "conflicting duplicate refs should fail",
        )
        conflicting_duplicate_payload = json.loads(conflicting_duplicate_proc.stdout)
        assert_true(
            any(
                "duplicates an existing ref with a conflicting role" in error
                for error in conflicting_duplicate_payload["errors"]
            ),
            "reader should reject conflicting duplicate refs",
        )
        print("OK: reader rejects conflicting duplicate refs")

        shorthand_generator = run(
            [
                "python3",
                str(GENERATOR),
                "--type",
                "chore",
                "--scope",
                "delivery-closeout-smoke",
                "--summary",
                "invalid shorthand",
                "--intent",
                "smoke test",
                "--impact",
                "reject shorthand refs",
                "--risk",
                "low",
                "--delivery-mode",
                "closeout",
                "--authority-linear-ref",
                "PUB-582",
                "--github-ref",
                "#30",
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        assert_equal(
            shorthand_generator.returncode,
            2,
            "generator should reject shorthand GitHub refs",
        )
        assert_true(
            "owner/repo#123" in shorthand_generator.stderr,
            "generator error should mention full GitHub ref shape",
        )
        print("OK: generator rejects #123 shorthand")

        shorthand_reader = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(refs=["#30"]),
            check=False,
        )
        assert_equal(
            shorthand_reader.returncode,
            2,
            "reader should reject string shorthand refs",
        )
        shorthand_payload = json.loads(shorthand_reader.stdout)
        assert_true(
            "refs[0] must be an object" in shorthand_payload["errors"],
            "reader error should mention typed refs",
        )
        print("OK: reader rejects #123 shorthand")

        github_only_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(
                refs=[
                    {
                        "system": "github",
                        "repo": "hack-ink/ELF",
                        "number": 30,
                        "role": "mirror",
                    }
                ]
            ),
        )
        github_only_payload = json.loads(github_only_proc.stdout)
        assert_equal(
            github_only_payload["authority_ref"],
            None,
            "GitHub-only refs should not invent a Linear authority",
        )
        assert_equal(
            github_only_payload["github_mirror_refs"],
            [
                {
                    "system": "github",
                    "repo": "hack-ink/ELF",
                    "number": 30,
                    "role": "mirror",
                }
            ],
            "reader GitHub-only mirrors",
        )
        print("OK: reader accepts GitHub-only ref sets without Linear authority")

        related_without_authority_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(
                refs=[{"system": "linear", "id": "PUB-600", "role": "related"}]
            ),
            check=False,
        )
        assert_equal(
            related_without_authority_proc.returncode,
            2,
            "related-only Linear refs should fail",
        )
        related_without_authority_payload = json.loads(
            related_without_authority_proc.stdout
        )
        assert_true(
            "delivery/1 linear related refs require a Linear authority ref"
            in related_without_authority_payload["errors"],
            "reader should reject related-only Linear refs",
        )
        print("OK: reader rejects related-only Linear refs")

        multiple_authority_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(
                refs=[
                    {"system": "linear", "id": "PUB-582", "role": "authority"},
                    {"system": "linear", "id": "PUB-600", "role": "authority"},
                ]
            ),
            check=False,
        )
        assert_equal(
            multiple_authority_proc.returncode,
            2,
            "multiple authority refs should fail",
        )
        multiple_authority_payload = json.loads(multiple_authority_proc.stdout)
        assert_true(
            "delivery/1 refs may contain at most one Linear authority ref"
            in multiple_authority_payload["errors"],
            "reader should reject multiple authority refs",
        )
        print("OK: multiple authority refs are rejected")

        reopen_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(
                refs=[{"system": "linear", "id": "PUB-582", "role": "authority"}],
                delivery_mode="reopen",
            ),
        )
        reopen_payload = json.loads(reopen_proc.stdout)
        assert_equal(reopen_payload["delivery_mode"], "reopen", "reader mode passthrough")
        print("OK: delivery mode is read from the contract")

        invalid_json_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text="not json",
            check=False,
        )
        assert_equal(invalid_json_proc.returncode, 2, "invalid JSON should fail")
        invalid_json_payload = json.loads(invalid_json_proc.stdout)
        assert_true(
            invalid_json_payload["errors"][0].startswith(
                "delivery/1 input is not valid JSON:"
            ),
            "invalid JSON failure reason",
        )
        print("OK: invalid JSON blocks the reader")

        multiline_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=json.dumps(
                {
                    "schema": "delivery/1",
                    "type": "chore",
                    "scope": "delivery-closeout-smoke",
                    "summary": "pretty printed contract",
                    "intent": "smoke test",
                    "impact": "reject multiline input",
                    "breaking": False,
                    "risk": "low",
                    "authority": "linear",
                    "delivery_mode": "closeout",
                    "refs": [
                        {"system": "linear", "id": "PUB-582", "role": "authority"}
                    ],
                },
                indent=2,
            ),
            check=False,
        )
        assert_equal(
            multiline_proc.returncode,
            2,
            "multiline JSON should fail",
        )
        multiline_payload = json.loads(multiline_proc.stdout)
        assert_true(
            "delivery/1 input must be a single line JSON object"
            in multiline_payload["errors"],
            "multiline failure reason",
        )
        print("OK: multiline JSON blocks the reader")

        wrong_schema_proc = run(
            stdin_reader_cmd,
            cwd=REPO_ROOT,
            input_text=build_contract(
                refs=[{"system": "linear", "id": "PUB-582", "role": "authority"}],
                schema="wrong/1",
            ),
            check=False,
        )
        assert_equal(wrong_schema_proc.returncode, 2, "wrong schema should fail")
        wrong_schema_payload = json.loads(wrong_schema_proc.stdout)
        assert_true(
            "delivery/1 schema must be exactly delivery/1"
            in wrong_schema_payload["errors"],
            "wrong schema failure reason",
        )
        print("OK: wrong schema blocks the reader")

        invalid_rev_proc = run(
            ["python3", str(READER), "--repo", str(repo_ok), "--rev", "does-not-exist"],
            cwd=REPO_ROOT,
            check=False,
        )
        assert_equal(invalid_rev_proc.returncode, 2, "invalid rev should fail")
        assert_equal(invalid_rev_proc.stderr, "", "invalid rev should not traceback")
        invalid_rev_payload = json.loads(invalid_rev_proc.stdout)
        assert_equal(invalid_rev_payload["duplicates"], [], "invalid rev duplicates")
        assert_equal(invalid_rev_payload["schema"], None, "invalid rev schema")
        assert_true(
            invalid_rev_payload["errors"]
            and "does-not-exist" in invalid_rev_payload["errors"][0],
            "invalid rev failure reason",
        )
        print("OK: invalid rev returns structured JSON")

        missing_repo = temp_root / "missing-repo"
        missing_repo_proc = run(
            ["python3", str(READER), "--repo", str(missing_repo)],
            cwd=REPO_ROOT,
            check=False,
        )
        assert_equal(missing_repo_proc.returncode, 2, "missing repo should fail")
        assert_equal(missing_repo_proc.stderr, "", "missing repo should not traceback")
        missing_repo_payload = json.loads(missing_repo_proc.stdout)
        assert_equal(missing_repo_payload["duplicates"], [], "missing repo duplicates")
        assert_equal(missing_repo_payload["schema"], None, "missing repo schema")
        assert_true(
            missing_repo_payload["errors"]
            and "does not exist" in missing_repo_payload["errors"][0],
            "missing repo failure reason",
        )
        print("OK: missing repo returns structured JSON")


if __name__ == "__main__":
    main()
