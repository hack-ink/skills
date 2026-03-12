#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
FORMATTER = REPO_ROOT / "plan-writing" / "scripts" / "format_plan_contract.py"
VALIDATOR = REPO_ROOT / "plan-writing" / "scripts" / "validate_plan_contract.py"
READER = REPO_ROOT / "plan-execution" / "scripts" / "read_plan_contract.py"
WRITER_HELPER = REPO_ROOT / "plan-writing" / "scripts" / "plan_contract.py"
READER_HELPER = REPO_ROOT / "plan-execution" / "scripts" / "plan_contract.py"


def run(
    cmd: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=False,
        text=True,
        input=input_text,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(cmd)}\n"
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


def build_contract() -> dict[str, object]:
    return {
        "spec": {
            "schema": "plan/1",
            "plan_id": "plan-execution-smoke",
            "goal": "Exercise the plan/1 execution reader.",
            "success_criteria": ["The reader consumes the saved contract without inference."],
            "constraints": ["Keep the smoke self-contained."],
            "defaults": {"owner": "main-thread"},
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Stage contract",
                    "status": "pending",
                    "objective": "Create a valid saved contract.",
                    "inputs": ["User request"],
                    "outputs": ["Saved plan file"],
                    "verification": ["python3 dev/plan-writing/run_smoke.py"],
                    "depends_on": [],
                },
                {
                    "id": "task-2",
                    "title": "Run execution",
                    "status": "pending",
                    "objective": "Consume the saved plan and advance state.",
                    "inputs": ["Saved plan file"],
                    "outputs": ["Execution state"],
                    "verification": ["python3 dev/plan-execution/run_smoke.py"],
                    "depends_on": ["task-1"],
                },
            ],
            "replan_policy": {
                "owner": "plan-writing",
                "triggers": ["blocked", "verification_failure"],
            },
        },
        "state": {
            "phase": "ready",
            "current_task_id": None,
            "next_task_id": "task-1",
            "blockers": [],
            "evidence": [],
            "last_updated": "2026-03-13T00:00:00Z",
            "replan_reason": None,
            "context_snapshot": {"source": "smoke"},
        },
    }


def write_plan(path: Path, contract: dict[str, object], *, tail: str = "") -> None:
    rendered = run(
        ["python3", str(FORMATTER)],
        input_text=json.dumps(contract) + tail,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered.stdout, encoding="utf-8")


def write_invalid_plan(path: Path, contract: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(contract, indent=2, ensure_ascii=True)
    path.write_text(f"```json\n{body}\n```\n", encoding="utf-8")


def main() -> None:
    assert_equal(
        READER_HELPER.read_text(encoding="utf-8"),
        WRITER_HELPER.read_text(encoding="utf-8"),
        "plan contract helpers should stay byte-identical across the pair",
    )
    print("OK: plan contract helpers stay synchronized across both skills")

    with tempfile.TemporaryDirectory(prefix="plan-execution-smoke-") as tmp_dir:
        temp_root = Path(tmp_dir)
        plan_path = temp_root / "docs" / "plans" / "2026-03-13_plan-execution-smoke.md"

        contract = build_contract()
        write_plan(plan_path, contract)
        validate_ready = run(["python3", str(VALIDATOR), "--path", str(plan_path)])
        assert_equal(validate_ready.stdout.strip(), "OK", "ready contract should validate")
        ready_reader = run(["python3", str(READER), "--path", str(plan_path)])
        ready_payload = json.loads(ready_reader.stdout)
        assert_true(ready_payload["ok"], "reader should accept a valid ready contract")
        assert_equal(ready_payload["phase"], "ready", "reader phase")
        assert_equal(ready_payload["next_task_id"], "task-1", "reader next task")
        print("OK: writer-compatible contract flows directly into reader")

        contract["spec"]["tasks"][0]["status"] = "in_progress"  # type: ignore[index]
        contract["state"]["phase"] = "executing"  # type: ignore[index]
        contract["state"]["current_task_id"] = "task-1"  # type: ignore[index]
        contract["state"]["next_task_id"] = "task-2"  # type: ignore[index]
        contract["state"]["last_updated"] = "2026-03-13T00:05:00Z"  # type: ignore[index]
        write_plan(plan_path, contract)
        executing_payload = json.loads(
            run(["python3", str(READER), "--path", str(plan_path)]).stdout
        )
        assert_equal(executing_payload["phase"], "executing", "executing phase should parse")
        assert_equal(
            executing_payload["current_task_id"],
            "task-1",
            "current task should follow the in-progress task",
        )
        print("OK: executing state is accepted")

        contract["spec"]["tasks"][0]["status"] = "blocked"  # type: ignore[index]
        contract["state"]["phase"] = "blocked"  # type: ignore[index]
        contract["state"]["blockers"] = ["lint command returned a non-zero exit code"]  # type: ignore[index]
        contract["state"]["evidence"] = ["cargo make lint-fix exit 101"]  # type: ignore[index]
        contract["state"]["context_snapshot"] = {"resume_from": "task-1"}  # type: ignore[index]
        contract["state"]["last_updated"] = "2026-03-13T00:10:00Z"  # type: ignore[index]
        write_plan(plan_path, contract)
        blocked_payload = json.loads(
            run(["python3", str(READER), "--path", str(plan_path)]).stdout
        )
        assert_equal(blocked_payload["phase"], "blocked", "blocked phase should parse")
        assert_equal(
            blocked_payload["contract"]["state"]["evidence"],
            ["cargo make lint-fix exit 101"],
            "blocked state should preserve evidence",
        )
        print("OK: blocked state preserves evidence")

        contract["state"]["phase"] = "needs_replan"  # type: ignore[index]
        contract["state"]["replan_reason"] = "task-1 is blocked on a stale verification path"  # type: ignore[index]
        contract["state"]["last_updated"] = "2026-03-13T00:15:00Z"  # type: ignore[index]
        write_plan(plan_path, contract)
        replan_payload = json.loads(
            run(["python3", str(READER), "--path", str(plan_path)]).stdout
        )
        assert_equal(replan_payload["phase"], "needs_replan", "needs_replan should parse")
        assert_equal(
            replan_payload["contract"]["state"]["evidence"],
            ["cargo make lint-fix exit 101"],
            "replan state should preserve prior evidence",
        )
        print("OK: needs_replan preserves evidence")

        contract["spec"]["goal"] = "Exercise replanning while preserving execution evidence."  # type: ignore[index]
        contract["spec"]["tasks"][0]["status"] = "pending"  # type: ignore[index]
        contract["state"]["phase"] = "ready"  # type: ignore[index]
        contract["state"]["current_task_id"] = None  # type: ignore[index]
        contract["state"]["next_task_id"] = "task-1"  # type: ignore[index]
        contract["state"]["blockers"] = []  # type: ignore[index]
        contract["state"]["replan_reason"] = None  # type: ignore[index]
        contract["state"]["last_updated"] = "2026-03-13T00:20:00Z"  # type: ignore[index]
        write_plan(plan_path, contract)
        replay_payload = json.loads(
            run(["python3", str(READER), "--path", str(plan_path)]).stdout
        )
        assert_equal(replay_payload["phase"], "ready", "replanned contract should return to ready")
        assert_equal(
            replay_payload["contract"]["state"]["evidence"],
            ["cargo make lint-fix exit 101"],
            "replanned contract should retain prior execution evidence",
        )
        print("OK: replanning preserves evidence while returning the contract to ready")

        standalone_root = temp_root / "standalone"
        standalone_scripts = standalone_root / "plan-execution" / "scripts"
        standalone_scripts.mkdir(parents=True, exist_ok=True)
        for source in (READER.parent / "read_plan_contract.py", READER.parent / "plan_contract.py"):
            (standalone_scripts / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        standalone_payload = json.loads(
            run(
                ["python3", str(standalone_scripts / "read_plan_contract.py"), "--path", str(plan_path)],
            ).stdout
        )
        assert_true(standalone_payload["ok"], "standalone plan-execution reader should work without plan-writing")
        print("OK: plan-execution reader remains self-contained")

        prose_path = temp_root / "docs" / "plans" / "2026-03-13_legacy.md"
        prose_path.write_text("# Legacy prose plan\n\nNo plan contract lives here.\n", encoding="utf-8")
        prose_proc = run(
            ["python3", str(READER), "--path", str(prose_path)],
            check=False,
        )
        assert_equal(prose_proc.returncode, 2, "prose-only plans should fail")
        prose_payload = json.loads(prose_proc.stdout)
        assert_true(prose_payload["migration_required"], "prose-only plans should request migration")
        print("OK: prose-only plans fail with an explicit migration reason")

        wrong_fence_path = temp_root / "docs" / "plans" / "2026-03-13_wrong-fence.md"
        wrong_fence_path.write_text(
            "```text\n"
            + json.dumps(build_contract(), indent=2)
            + "\n```\n",
            encoding="utf-8",
        )
        wrong_fence_proc = run(
            ["python3", str(READER), "--path", str(wrong_fence_path)],
            check=False,
        )
        assert_equal(wrong_fence_proc.returncode, 2, "non-json fenced plans should fail")
        wrong_fence_payload = json.loads(wrong_fence_proc.stdout)
        assert_true(
            any("```json fenced block" in error for error in wrong_fence_payload["errors"]),
            "wrong fence failure should mention the json fence requirement",
        )
        print("OK: non-json fenced plan files are rejected")

        blocked_without_reason = build_contract()
        blocked_without_reason["spec"]["tasks"][0]["status"] = "blocked"  # type: ignore[index]
        blocked_without_reason["state"]["phase"] = "blocked"  # type: ignore[index]
        blocked_without_reason["state"]["current_task_id"] = "task-1"  # type: ignore[index]
        blocked_without_reason["state"]["next_task_id"] = "task-2"  # type: ignore[index]
        blocked_without_reason["state"]["last_updated"] = "2026-03-13T00:25:00Z"  # type: ignore[index]
        blocked_path = temp_root / "docs" / "plans" / "2026-03-13_blocked-no-reason.md"
        write_invalid_plan(blocked_path, blocked_without_reason)
        blocked_proc = run(
            ["python3", str(READER), "--path", str(blocked_path)],
            check=False,
        )
        assert_equal(blocked_proc.returncode, 2, "blocked plans need blocker reasons")
        blocked_payload = json.loads(blocked_proc.stdout)
        assert_true(
            any("requires at least one blocker reason" in error for error in blocked_payload["errors"]),
            "blocked failure should mention the blocker invariant",
        )
        print("OK: blocked states without blocker reasons are rejected")

        non_executable_ready = build_contract()
        non_executable_ready["state"]["next_task_id"] = "task-2"  # type: ignore[index]
        non_exec_path = temp_root / "docs" / "plans" / "2026-03-13_non-executable-ready.md"
        write_invalid_plan(non_exec_path, non_executable_ready)
        non_exec_proc = run(
            ["python3", str(READER), "--path", str(non_exec_path)],
            check=False,
        )
        assert_equal(non_exec_proc.returncode, 2, "ready plans must point at an executable next task")
        non_exec_payload = json.loads(non_exec_proc.stdout)
        assert_true(
            any("reference an executable task" in error for error in non_exec_payload["errors"]),
            "ready failure should mention the executable-task invariant",
        )
        print("OK: ready states with unresolved next-task dependencies are rejected")

        non_executable_current = build_contract()
        non_executable_current["spec"]["tasks"][1]["status"] = "in_progress"  # type: ignore[index]
        non_executable_current["state"]["phase"] = "executing"  # type: ignore[index]
        non_executable_current["state"]["current_task_id"] = "task-2"  # type: ignore[index]
        non_executable_current["state"]["next_task_id"] = "task-1"  # type: ignore[index]
        non_executable_current["state"]["last_updated"] = "2026-03-13T00:27:00Z"  # type: ignore[index]
        non_current_path = temp_root / "docs" / "plans" / "2026-03-13_non-executable-current.md"
        write_invalid_plan(non_current_path, non_executable_current)
        non_current_proc = run(
            ["python3", str(READER), "--path", str(non_current_path)],
            check=False,
        )
        assert_equal(non_current_proc.returncode, 2, "executing plans must point at an executable current task")
        non_current_payload = json.loads(non_current_proc.stdout)
        assert_true(
            any("dependencies are done" in error for error in non_current_payload["errors"]),
            "current-task failure should mention dependency satisfaction",
        )
        print("OK: executing states with unresolved current-task dependencies are rejected")

        done_with_unfinished = build_contract()
        done_with_unfinished["state"]["phase"] = "done"  # type: ignore[index]
        done_with_unfinished["state"]["current_task_id"] = None  # type: ignore[index]
        done_with_unfinished["state"]["next_task_id"] = None  # type: ignore[index]
        done_with_unfinished["state"]["last_updated"] = "2026-03-13T00:30:00Z"  # type: ignore[index]
        done_path = temp_root / "docs" / "plans" / "2026-03-13_done-invalid.md"
        write_invalid_plan(done_path, done_with_unfinished)
        done_proc = run(
            ["python3", str(READER), "--path", str(done_path)],
            check=False,
        )
        assert_equal(done_proc.returncode, 2, "done states with unfinished tasks should fail")
        done_payload = json.loads(done_proc.stdout)
        assert_true(
            any("requires all tasks to be terminal" in error for error in done_payload["errors"]),
            "done failure should mention unfinished tasks",
        )
        print("OK: done states with unfinished tasks are rejected")


if __name__ == "__main__":
    main()
