#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


SCHEMA = "plan/1"
PHASES = {
    "planning",
    "ready",
    "executing",
    "blocked",
    "needs_replan",
    "done",
}
TASK_STATUSES = {
    "pending",
    "in_progress",
    "blocked",
    "done",
    "cancelled",
}
TOP_LEVEL_KEYS = {"spec", "state"}
SPEC_KEYS = {
    "schema",
    "plan_id",
    "goal",
    "success_criteria",
    "constraints",
    "defaults",
    "tasks",
    "replan_policy",
}
TASK_KEYS = {
    "id",
    "title",
    "status",
    "objective",
    "inputs",
    "outputs",
    "verification",
    "depends_on",
}
REPLAN_POLICY_KEYS = {"owner", "triggers"}
STATE_KEYS = {
    "phase",
    "current_task_id",
    "next_task_id",
    "blockers",
    "evidence",
    "last_updated",
    "replan_reason",
    "context_snapshot",
}
FENCE_RE = re.compile(
    r"^\s*```(?P<lang>[^\n]*)\n(?P<body>.*?)\n```(?P<tail>[\s\S]*)\Z",
    re.S,
)


@dataclass(frozen=True)
class ContractParseResult:
    ok: bool
    contract: dict[str, Any] | None
    tail: str
    errors: list[str]
    migration_required: bool


def normalize_freeform(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_freeform(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [normalize_freeform(item) for item in value]
    return value


def normalize_string(value: Any, label: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return None
    return value.strip()


def normalize_string_list(
    value: Any,
    label: str,
    errors: list[str],
    *,
    allow_empty: bool,
) -> list[str] | None:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return None
    normalized: list[str] = []
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        normalized_item = normalize_string(item, item_label, errors)
        if normalized_item is None:
            continue
        normalized.append(normalized_item)
    if not allow_empty and not normalized:
        errors.append(f"{label} must be a non-empty array")
    return normalized


def normalize_optional_string(
    value: Any,
    label: str,
    errors: list[str],
) -> str | None:
    if value is None:
        return None
    return normalize_string(value, label, errors)


def expect_exact_keys(
    obj: Any,
    label: str,
    expected_keys: set[str],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    missing = sorted(expected_keys - set(obj))
    extra = sorted(set(obj) - expected_keys)
    if missing:
        errors.append(f"{label} missing keys: {missing}")
    if extra:
        errors.append(f"{label} unexpected keys: {extra}")
    return obj


def validate_replan_policy(value: Any, errors: list[str]) -> dict[str, Any] | None:
    obj = expect_exact_keys(value, "spec.replan_policy", REPLAN_POLICY_KEYS, errors)
    if obj is None:
        return None
    owner = normalize_string(obj.get("owner"), "spec.replan_policy.owner", errors)
    triggers = normalize_string_list(
        obj.get("triggers"),
        "spec.replan_policy.triggers",
        errors,
        allow_empty=False,
    )
    if owner is None or triggers is None:
        return None
    return {
        "owner": owner,
        "triggers": triggers,
    }


def validate_task(task: Any, index: int, errors: list[str]) -> dict[str, Any] | None:
    label = f"spec.tasks[{index}]"
    obj = expect_exact_keys(task, label, TASK_KEYS, errors)
    if obj is None:
        return None

    task_id = normalize_string(obj.get("id"), f"{label}.id", errors)
    title = normalize_string(obj.get("title"), f"{label}.title", errors)
    status = normalize_string(obj.get("status"), f"{label}.status", errors)
    objective = normalize_string(obj.get("objective"), f"{label}.objective", errors)
    inputs = normalize_string_list(obj.get("inputs"), f"{label}.inputs", errors, allow_empty=True)
    outputs = normalize_string_list(
        obj.get("outputs"), f"{label}.outputs", errors, allow_empty=True
    )
    verification = normalize_string_list(
        obj.get("verification"),
        f"{label}.verification",
        errors,
        allow_empty=False,
    )
    depends_on = normalize_string_list(
        obj.get("depends_on"),
        f"{label}.depends_on",
        errors,
        allow_empty=True,
    )
    if status is not None and status not in TASK_STATUSES:
        errors.append(f"{label}.status must be one of: {sorted(TASK_STATUSES)}")

    if None in (
        task_id,
        title,
        status,
        objective,
        inputs,
        outputs,
        verification,
        depends_on,
    ):
        return None

    return {
        "id": task_id,
        "title": title,
        "status": status,
        "objective": objective,
        "inputs": inputs,
        "outputs": outputs,
        "verification": verification,
        "depends_on": depends_on,
    }


def validate_spec(value: Any, errors: list[str]) -> dict[str, Any] | None:
    obj = expect_exact_keys(value, "spec", SPEC_KEYS, errors)
    if obj is None:
        return None

    schema = normalize_string(obj.get("schema"), "spec.schema", errors)
    plan_id = normalize_string(obj.get("plan_id"), "spec.plan_id", errors)
    goal = normalize_string(obj.get("goal"), "spec.goal", errors)
    success_criteria = normalize_string_list(
        obj.get("success_criteria"),
        "spec.success_criteria",
        errors,
        allow_empty=False,
    )
    constraints = normalize_string_list(
        obj.get("constraints"),
        "spec.constraints",
        errors,
        allow_empty=True,
    )
    defaults_obj = obj.get("defaults")
    if not isinstance(defaults_obj, dict):
        errors.append("spec.defaults must be a JSON object")
        defaults = None
    else:
        defaults = normalize_freeform(defaults_obj)
    tasks_obj = obj.get("tasks")
    if not isinstance(tasks_obj, list):
        errors.append("spec.tasks must be an array")
        tasks = None
    else:
        tasks = []
        seen_ids: set[str] = set()
        for index, task in enumerate(tasks_obj):
            normalized_task = validate_task(task, index, errors)
            if normalized_task is None:
                continue
            task_id = normalized_task["id"]
            if task_id in seen_ids:
                errors.append(f"spec.tasks[{index}].id duplicates an existing task id")
                continue
            seen_ids.add(task_id)
            tasks.append(normalized_task)
        if not tasks:
            errors.append("spec.tasks must contain at least one valid task")
        else:
            valid_ids = {task["id"] for task in tasks}
            for index, task in enumerate(tasks):
                for dependency in task["depends_on"]:
                    if dependency not in valid_ids:
                        errors.append(
                            f"spec.tasks[{index}].depends_on references unknown task id {dependency!r}"
                        )
                    if dependency == task["id"]:
                        errors.append(
                            f"spec.tasks[{index}].depends_on must not reference its own task id"
                        )

    replan_policy = validate_replan_policy(obj.get("replan_policy"), errors)
    if schema is not None and schema != SCHEMA:
        errors.append(f"spec.schema must be exactly {SCHEMA!r}")

    if None in (
        schema,
        plan_id,
        goal,
        success_criteria,
        constraints,
        defaults,
        tasks,
        replan_policy,
    ):
        return None

    return {
        "schema": schema,
        "plan_id": plan_id,
        "goal": goal,
        "success_criteria": success_criteria,
        "constraints": constraints,
        "defaults": defaults,
        "tasks": tasks,
        "replan_policy": replan_policy,
    }


def validate_state(
    value: Any,
    tasks: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any] | None:
    obj = expect_exact_keys(value, "state", STATE_KEYS, errors)
    if obj is None:
        return None

    phase = normalize_string(obj.get("phase"), "state.phase", errors)
    current_task_id = normalize_optional_string(
        obj.get("current_task_id"), "state.current_task_id", errors
    )
    next_task_id = normalize_optional_string(
        obj.get("next_task_id"), "state.next_task_id", errors
    )
    blockers = normalize_string_list(
        obj.get("blockers"), "state.blockers", errors, allow_empty=True
    )
    evidence = normalize_string_list(
        obj.get("evidence"), "state.evidence", errors, allow_empty=True
    )
    last_updated = normalize_string(obj.get("last_updated"), "state.last_updated", errors)
    replan_reason = normalize_optional_string(
        obj.get("replan_reason"), "state.replan_reason", errors
    )
    context_snapshot_obj = obj.get("context_snapshot")
    if not isinstance(context_snapshot_obj, dict):
        errors.append("state.context_snapshot must be a JSON object")
        context_snapshot = None
    else:
        context_snapshot = normalize_freeform(context_snapshot_obj)

    if phase is not None and phase not in PHASES:
        errors.append(f"state.phase must be one of: {sorted(PHASES)}")

    if None in (
        phase,
        blockers,
        evidence,
        last_updated,
        context_snapshot,
    ):
        return None

    task_by_id = {task["id"]: task for task in tasks}

    def unsatisfied_dependencies(task_id: str) -> list[str]:
        task = task_by_id[task_id]
        return [
            dependency
            for dependency in task["depends_on"]
            if task_by_id[dependency]["status"] != "done"
        ]

    in_progress_ids = [task["id"] for task in tasks if task["status"] == "in_progress"]
    blocked_ids = [task["id"] for task in tasks if task["status"] == "blocked"]
    pending_ids = [task["id"] for task in tasks if task["status"] == "pending"]
    terminal_statuses = {"done", "cancelled"}

    if len(in_progress_ids) > 1:
        errors.append("spec.tasks may contain at most one task with status 'in_progress'")
    if current_task_id is not None and current_task_id not in task_by_id:
        errors.append("state.current_task_id must reference an existing task id")
    if next_task_id is not None and next_task_id not in task_by_id:
        errors.append("state.next_task_id must reference an existing task id")
    if next_task_id is not None and next_task_id in task_by_id:
        next_status = task_by_id[next_task_id]["status"]
        if next_status in terminal_statuses:
            errors.append("state.next_task_id must not reference a terminal task")
    if current_task_id is not None and current_task_id in task_by_id:
        current_status = task_by_id[current_task_id]["status"]
        if current_status in terminal_statuses:
            errors.append("state.current_task_id must not reference a terminal task")
        elif phase in {"executing", "blocked", "needs_replan"}:
            unsatisfied = unsatisfied_dependencies(current_task_id)
            if unsatisfied:
                errors.append(
                    "state.current_task_id must reference a task whose dependencies are done; "
                    f"unsatisfied dependencies: {unsatisfied}"
                )

    if phase == "planning":
        if in_progress_ids:
            errors.append("state.phase 'planning' cannot have in-progress tasks")
        if blocked_ids:
            errors.append("state.phase 'planning' cannot have blocked tasks")
        if current_task_id is not None:
            errors.append("state.phase 'planning' requires state.current_task_id to be null")
        if blockers:
            errors.append("state.phase 'planning' requires state.blockers to be empty")
        if replan_reason is not None:
            errors.append("state.phase 'planning' requires state.replan_reason to be null")
    elif phase == "ready":
        if in_progress_ids:
            errors.append("state.phase 'ready' cannot have in-progress tasks")
        if blocked_ids:
            errors.append("state.phase 'ready' cannot have blocked tasks")
        if current_task_id is not None:
            errors.append("state.phase 'ready' requires state.current_task_id to be null")
        if blockers:
            errors.append("state.phase 'ready' requires state.blockers to be empty")
        if replan_reason is not None:
            errors.append("state.phase 'ready' requires state.replan_reason to be null")
        if pending_ids:
            if next_task_id is None:
                errors.append("state.phase 'ready' requires state.next_task_id")
            elif task_by_id[next_task_id]["status"] != "pending":
                errors.append("state.phase 'ready' requires state.next_task_id to reference a pending task")
            else:
                unsatisfied = unsatisfied_dependencies(next_task_id)
                if unsatisfied:
                    errors.append(
                        "state.phase 'ready' requires state.next_task_id to reference an executable task; "
                        f"unsatisfied dependencies: {unsatisfied}"
                    )
        else:
            errors.append("state.phase 'ready' requires at least one pending task")
    elif phase == "executing":
        if len(in_progress_ids) != 1:
            errors.append("state.phase 'executing' requires exactly one in-progress task")
        elif current_task_id != in_progress_ids[0]:
            errors.append(
                "state.phase 'executing' requires state.current_task_id to match the in-progress task"
            )
        if blocked_ids:
            errors.append("state.phase 'executing' cannot have blocked tasks")
        if blockers:
            errors.append("state.phase 'executing' requires state.blockers to be empty")
        if replan_reason is not None:
            errors.append("state.phase 'executing' requires state.replan_reason to be null")
    elif phase == "blocked":
        if in_progress_ids:
            errors.append("state.phase 'blocked' cannot have in-progress tasks")
        if not blocked_ids:
            errors.append("state.phase 'blocked' requires at least one blocked task")
        if current_task_id is None:
            errors.append("state.phase 'blocked' requires state.current_task_id")
        elif current_task_id in task_by_id and task_by_id[current_task_id]["status"] != "blocked":
            errors.append(
                "state.phase 'blocked' requires state.current_task_id to reference a blocked task"
            )
        if not blockers:
            errors.append("state.phase 'blocked' requires at least one blocker reason")
    elif phase == "needs_replan":
        if in_progress_ids:
            errors.append("state.phase 'needs_replan' cannot have in-progress tasks")
        if replan_reason is None:
            errors.append("state.phase 'needs_replan' requires state.replan_reason")
        if not blockers and not blocked_ids:
            errors.append(
                "state.phase 'needs_replan' requires blocker evidence or a blocked task"
            )
    elif phase == "done":
        if current_task_id is not None:
            errors.append("state.phase 'done' requires state.current_task_id to be null")
        if next_task_id is not None:
            errors.append("state.phase 'done' requires state.next_task_id to be null")
        if blockers:
            errors.append("state.phase 'done' requires state.blockers to be empty")
        if replan_reason is not None:
            errors.append("state.phase 'done' requires state.replan_reason to be null")
        unfinished = [
            task["id"] for task in tasks if task["status"] not in terminal_statuses
        ]
        if unfinished:
            errors.append(
                "state.phase 'done' requires all tasks to be terminal; unfinished tasks: "
                + ", ".join(unfinished)
            )

    return {
        "phase": phase,
        "current_task_id": current_task_id,
        "next_task_id": next_task_id,
        "blockers": blockers,
        "evidence": evidence,
        "last_updated": last_updated,
        "replan_reason": replan_reason,
        "context_snapshot": context_snapshot,
    }


def validate_contract_object(obj: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    top = expect_exact_keys(obj, "plan/1", TOP_LEVEL_KEYS, errors)
    if top is None:
        return None, errors

    spec = validate_spec(top.get("spec"), errors)
    tasks = spec["tasks"] if spec is not None else []
    state = validate_state(top.get("state"), tasks, errors)
    if spec is None or state is None or errors:
        return None, errors
    return {"spec": spec, "state": state}, errors


def extract_contract_text(
    raw_text: str,
    *,
    require_fence: bool,
) -> tuple[str | None, str, list[str], bool]:
    text = raw_text.lstrip("\ufeff")
    stripped = text.lstrip()
    if not stripped:
        return None, "", ["plan input is empty"], False

    if stripped.startswith("{"):
        if require_fence:
            return (
                None,
                "",
                [
                    "plan file must start with a ```json fenced block; raw JSON must be materialized into the saved markdown container"
                ],
                True,
            )
        return stripped, "", [], False

    if not stripped.startswith("```"):
        if require_fence:
            return (
                None,
                "",
                [
                    "plan file must start with a ```json fenced block; legacy prose-only plans require migration"
                ],
                True,
            )
        return None, "", ["plan input must be raw JSON or start with a fenced JSON block"], False

    match = FENCE_RE.match(stripped)
    if match is None:
        return None, "", ["plan input starts with an unterminated fenced block"], False
    if match.group("lang").strip() != "json":
        return None, "", ["plan file must start with a ```json fenced block"], False
    return match.group("body"), match.group("tail"), [], False


def parse_contract_text(
    raw_text: str,
    *,
    require_fence: bool,
) -> ContractParseResult:
    contract_text, tail, errors, migration_required = extract_contract_text(
        raw_text,
        require_fence=require_fence,
    )
    if contract_text is None:
        return ContractParseResult(
            ok=False,
            contract=None,
            tail="",
            errors=errors,
            migration_required=migration_required,
        )

    try:
        obj = json.loads(contract_text)
    except json.JSONDecodeError as err:
        return ContractParseResult(
            ok=False,
            contract=None,
            tail=tail,
            errors=[f"plan/1 block is not valid JSON: {err}"],
            migration_required=False,
        )

    contract, validation_errors = validate_contract_object(obj)
    if contract is None:
        return ContractParseResult(
            ok=False,
            contract=None,
            tail=tail,
            errors=validation_errors,
            migration_required=False,
        )

    return ContractParseResult(
        ok=True,
        contract=contract,
        tail=tail,
        errors=[],
        migration_required=False,
    )


def render_contract_markdown(contract: dict[str, Any], tail: str = "") -> str:
    normalized_contract, errors = validate_contract_object(contract)
    if normalized_contract is None:
        joined = "; ".join(errors) if errors else "unknown validation error"
        raise ValueError(joined)

    body = json.dumps(normalized_contract, indent=2, ensure_ascii=True)
    rendered = f"```json\n{body}\n```\n"
    trailing = tail.strip()
    if trailing:
        rendered += "\n" + trailing + "\n"
    return rendered
