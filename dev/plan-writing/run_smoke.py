#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
FORMATTER = REPO_ROOT / "plan-writing" / "scripts" / "format_plan_contract.py"
VALIDATOR = REPO_ROOT / "plan-writing" / "scripts" / "validate_plan_contract.py"


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
            "plan_id": "plan-writing-smoke",
            "goal": "Exercise the plan/1 formatter and validator.",
            "success_criteria": ["The contract is valid and machine-readable."],
            "constraints": ["Keep the smoke self-contained."],
            "defaults": {"owner": "main-thread"},
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Create contract",
                    "status": "pending",
                    "objective": "Create a valid initial contract.",
                    "inputs": ["User request"],
                    "outputs": ["Saved plan file"],
                    "verification": ["python3 dev/plan-writing/run_smoke.py"],
                    "depends_on": [],
                },
                {
                    "id": "task-2",
                    "title": "Consume contract",
                    "status": "pending",
                    "objective": "Verify the reader can consume the saved contract.",
                    "inputs": ["Saved plan file"],
                    "outputs": ["Reader result"],
                    "verification": ["python3 dev/plan-execution/run_smoke.py"],
                    "depends_on": ["task-1"],
                },
            ],
            "replan_policy": {
                "owner": "plan-writing",
                "triggers": ["blocked", "contradictory_state"],
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


def main() -> None:
    raw_contract = json.dumps(build_contract())
    formatted = run(
        ["python3", str(FORMATTER)],
        input_text=raw_contract,
    )
    assert_true(
        formatted.stdout.startswith("```json\n{\n  \"spec\""),
        "formatter should emit a fenced JSON block first",
    )
    print("OK: formatter emits canonical fenced markdown")

    validate_formatted = run(
        ["python3", str(VALIDATOR)],
        input_text=formatted.stdout,
    )
    assert_equal(validate_formatted.stdout.strip(), "OK", "validator should accept formatted output")
    print("OK: validator accepts canonical fenced markdown")

    with_tail = formatted.stdout + "\n## Non-authoritative context\n\nThis prose is ignored.\n"
    reformatted = run(
        ["python3", str(FORMATTER)],
        input_text=with_tail,
    )
    assert_true(
        "## Non-authoritative context" in reformatted.stdout,
        "formatter should preserve trailing markdown context",
    )
    print("OK: formatter preserves trailing markdown context")

    wrong_fence = (
        "```text\n"
        + json.dumps(build_contract(), indent=2)
        + "\n```\n"
    )
    wrong_fence_proc = run(
        ["python3", str(VALIDATOR)],
        input_text=wrong_fence,
        check=False,
    )
    assert_equal(wrong_fence_proc.returncode, 2, "non-json fenced blocks should fail")
    assert_true(
        "```json fenced block" in wrong_fence_proc.stderr,
        "wrong fence failure should mention the json fence requirement",
    )
    print("OK: non-json fenced blocks are rejected")

    duplicate_ids = build_contract()
    duplicate_ids["spec"]["tasks"][1]["id"] = "task-1"  # type: ignore[index]
    duplicate_proc = run(
        ["python3", str(VALIDATOR)],
        input_text=json.dumps(duplicate_ids),
        check=False,
    )
    assert_equal(duplicate_proc.returncode, 2, "duplicate task ids should fail")
    assert_true(
        "duplicates an existing task id" in duplicate_proc.stderr,
        "duplicate id failure should mention the duplicated task id",
    )
    print("OK: duplicate task ids are rejected")

    bad_dependency = build_contract()
    bad_dependency["spec"]["tasks"][1]["depends_on"] = ["missing-task"]  # type: ignore[index]
    bad_dependency_proc = run(
        ["python3", str(VALIDATOR)],
        input_text=json.dumps(bad_dependency),
        check=False,
    )
    assert_equal(bad_dependency_proc.returncode, 2, "unknown dependencies should fail")
    assert_true(
        "references unknown task id" in bad_dependency_proc.stderr,
        "bad dependency failure should mention the missing task",
    )
    print("OK: unknown dependencies are rejected")

    non_executable_next = build_contract()
    non_executable_next["state"]["next_task_id"] = "task-2"  # type: ignore[index]
    non_executable_next_proc = run(
        ["python3", str(VALIDATOR)],
        input_text=json.dumps(non_executable_next),
        check=False,
    )
    assert_equal(non_executable_next_proc.returncode, 2, "ready next task must be executable")
    assert_true(
        "reference an executable task" in non_executable_next_proc.stderr,
        "non-executable next task failure should mention the executable-task invariant",
    )
    print("OK: ready next tasks with unsatisfied dependencies are rejected")

    multiple_active = build_contract()
    multiple_active["spec"]["tasks"][0]["status"] = "in_progress"  # type: ignore[index]
    multiple_active["spec"]["tasks"][1]["status"] = "in_progress"  # type: ignore[index]
    multiple_active["state"]["phase"] = "executing"  # type: ignore[index]
    multiple_active["state"]["current_task_id"] = "task-1"  # type: ignore[index]
    multiple_active["state"]["next_task_id"] = "task-2"  # type: ignore[index]
    multiple_active_proc = run(
        ["python3", str(VALIDATOR)],
        input_text=json.dumps(multiple_active),
        check=False,
    )
    assert_equal(multiple_active_proc.returncode, 2, "multiple active tasks should fail")
    assert_true(
        "at most one task with status 'in_progress'" in multiple_active_proc.stderr,
        "multiple active task failure should mention the in-progress invariant",
    )
    print("OK: multiple active tasks are rejected")


if __name__ == "__main__":
    main()
