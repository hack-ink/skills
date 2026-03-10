#!/usr/bin/env python3

import csv
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COVERAGE = REPO_ROOT / "codebase-review" / "check-review-coverage.py"
CLOSEOUT = REPO_ROOT / "codebase-review" / "check-review-closeout.py"


def run(cmd, cwd: Path, *, check: bool = True, env=None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    if check and proc.returncode != 0:
        cmd_text = " ".join(cmd)
        raise AssertionError(
            f"command failed: {cmd_text}\n"
            f"cwd: {cwd}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def assert_in(needle: str, haystack: str, message: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"{message}: missing {needle!r}\n--- output ---\n{haystack}")


def rewrite_csv(path: Path, row_index: int, field: str, value: str) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = rows[0].keys()
    rows[row_index][field] = value
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="codebase-review-smoke-") as tmp_dir:
        temp_root = Path(tmp_dir)
        repo_root = temp_root / "repo"
        review_root = repo_root / "review"
        repo_root.mkdir()

        run(["git", "init", "-b", "main"], cwd=repo_root)
        run(["git", "config", "user.name", "Smoke Test"], cwd=repo_root)
        run(["git", "config", "user.email", "smoke@example.com"], cwd=repo_root)

        write_text(repo_root / "src" / "auth.py", "print('ok')\n")
        run(["git", "add", "src/auth.py"], cwd=repo_root)
        run(["git", "commit", "-m", "init"], cwd=repo_root)
        print("OK: created temp repository for codebase-review smoke")

        blob_sha = run(["git", "rev-parse", "HEAD:src/auth.py"], cwd=repo_root).stdout.strip()
        write_text(review_root / "scope-files.txt", "src/auth.py\n")
        write_text(
            review_root / "ledger.csv",
            "reviewed_file,blob_sha,status,reviewer,reviewed_at,notes\n"
            f"src/auth.py,{blob_sha},approved,alice,2026-03-10T00:00:00Z,ok\n",
        )
        write_text(
            review_root / "findings-backlog.csv",
            "file,line,signature,severity,confidence,severity_rationale,impact,likelihood,exposure,triage_state,due_date,mitigation_plan,accepted_risk_reason,accepted_risk_approver,verified_at,owner,notes,decision_ref\n"
            "src/auth.py,10,auth-check,Medium,medium,Needs follow-up,3,3,3,in-review,2026-03-20,Add a regression test,,,,alice,tracked,\n"
            "src/auth.py,42,auth-bypass,High,high,Accepted risk path,5,4,4,accepted_risk,2026-03-21,Document exception,compat gate,bob,2026-03-10T00:00:00Z,alice,ok,decision-log.md#ADR-0001\n",
        )
        write_text(
            review_root / "slice-plan.csv",
            "slice_id,focus,scope_glob,owner,reviewer,risk_score,depends_on,wip_state,wip,planned_start,planned_end,notes\n"
            "S-001,auth,src/*.py,alice,bob,80,,active,1,2026-03-10,2026-03-11,\n",
        )
        write_text(
            review_root / "risk-register.csv",
            "risk_id,area,owner,evidence,impact,likelihood,exposure,risk_score,status,slice_id,related_files,decision_ref,mitigation_notes\n"
            "R-001,auth,alice,Recent incident,5,4,4,80,mitigated,S-001,src/*.py,decision-log.md#ADR-0001,Mitigated before closeout\n",
        )

        coverage_ok = run(
            [
                "python3",
                str(COVERAGE),
                "--repo-root",
                str(repo_root),
                "--scope-file",
                "review/scope-files.txt",
                "--ledger",
                "review/ledger.csv",
                "--min-coverage",
                "100",
            ],
            cwd=REPO_ROOT,
        )
        assert_in("COVERAGE_OK", coverage_ok.stdout, "coverage smoke should pass")
        print("OK: coverage gate passes with approved current-SHA ledger")

        rewrite_csv(review_root / "ledger.csv", 0, "status", "pending")
        coverage_fail = run(
            [
                "python3",
                str(COVERAGE),
                "--repo-root",
                str(repo_root),
                "--scope-file",
                "review/scope-files.txt",
                "--ledger",
                "review/ledger.csv",
                "--min-coverage",
                "100",
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        assert_equal(coverage_fail.returncode, 1, "coverage smoke should fail with non-approved ledger")
        assert_in("COVERAGE_FAIL", coverage_fail.stdout, "coverage failure marker")
        print("OK: coverage gate fails when the ledger row is not approved")

        rewrite_csv(review_root / "ledger.csv", 0, "status", "approved")
        closeout_ok = run(
            [
                "python3",
                str(CLOSEOUT),
                "--repo-root",
                str(repo_root),
                "--ledger",
                "review/ledger.csv",
                "--findings",
                "review/findings-backlog.csv",
                "--slice-plan",
                "review/slice-plan.csv",
                "--risk-register",
                "review/risk-register.csv",
            ],
            cwd=REPO_ROOT,
        )
        assert_in("CLOSEOUT_OK", closeout_ok.stdout, "closeout smoke should pass")
        print("OK: closeout gate passes with complete structured artifacts")

        rewrite_csv(review_root / "findings-backlog.csv", 0, "mitigation_plan", "")
        closeout_fail = run(
            [
                "python3",
                str(CLOSEOUT),
                "--repo-root",
                str(repo_root),
                "--ledger",
                "review/ledger.csv",
                "--findings",
                "review/findings-backlog.csv",
                "--slice-plan",
                "review/slice-plan.csv",
                "--risk-register",
                "review/risk-register.csv",
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        assert_equal(closeout_fail.returncode, 1, "closeout smoke should fail without mitigation_plan")
        assert_in("CLOSEOUT_FAIL", closeout_fail.stdout, "closeout failure marker")
        print("OK: closeout gate fails when a Medium finding lacks mitigation_plan")


if __name__ == "__main__":
    main()
