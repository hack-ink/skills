from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

from referencing.exceptions import Unresolvable

from schema_support import (
    SKILL_ROOT,
    load_schema_catalog,
    schema_path_for_id,
    validator_for_id,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_DIR = Path(__file__).resolve().parent
TASK_DISPATCH_SCHEMA_ID = "task-dispatch/1"
RUNNER_RESULT_SCHEMA_ID = "worker-result.runner/1"
BUILDER_RESULT_SCHEMA_ID = "worker-result.builder/1"
INSPECTOR_RESULT_SCHEMA_ID = "review-result.inspector/1"
SINGLE_FAST_PATH_MAX_S = 60

SUPPORTED_EVIDENCE_REQUIREMENTS = {
    "runner": {"analysis", "commands", "files_read"},
    "builder": {"diff", "git_diff", "verification"},
    "inspector": {"review_notes"},
}


def load_json(path: Path):
    text = path.read_text()
    stripped = text.strip()
    if stripped.startswith("```") or stripped.endswith("```"):
        raise AssertionError(
            f"{path.name}: worker output must be raw JSON only; code fences are not allowed"
        )
    return json.loads(stripped)


def validate_one(schema_id: str, payload: dict, label: str) -> None:
    validator = validator_for_id(schema_id)
    validator.validate(payload)
    schema_path = schema_path_for_id(schema_id)
    print(f"OK: {label} against {schema_path.relative_to(SKILL_ROOT)}")


def assert_schema_rejects(schema_id: str, payload: dict, label: str) -> None:
    validator = validator_for_id(schema_id)
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: (list(error.path), error.message),
    )
    if not errors:
        raise AssertionError(f"{label}: expected schema rejection against {schema_id}")
    schema_path = schema_path_for_id(schema_id)
    messages = "; ".join(error.message for error in errors[:3])
    print(
        f"OK: {label} rejected by {schema_path.relative_to(SKILL_ROOT)} ({messages})"
    )


def ssot_parts(ssot_id: str) -> tuple[str, str]:
    if "-" not in ssot_id:
        raise AssertionError("ssot_id must be scenario-hash: <scenario>-<hex>")
    scenario, token = ssot_id.rsplit("-", 1)
    return scenario, token


def assert_ssot_id_policy(ssot_id: str) -> None:
    scenario, token = ssot_parts(ssot_id)
    if not scenario:
        raise AssertionError("ssot_id scenario prefix must be non-empty")
    if not (8 <= len(token) <= 64):
        raise AssertionError("ssot_id token must be hex length 8..64")
    if any(c not in "0123456789abcdef" for c in token):
        raise AssertionError("ssot_id token must be lowercase hex")

    expected = hashlib.sha256(scenario.encode("utf-8")).hexdigest()[: len(token)]
    if token != expected:
        raise AssertionError(
            "ssot_id must use scenario-hash (sha256(scenario) prefix); "
            f"expected {scenario}-{expected}"
        )


def assert_json_only_output(payload: dict, path: Path) -> None:
    if not isinstance(payload, (dict, list)):
        raise AssertionError(f"{path.name}: output must be a JSON object or array")


def dispatch_match_key(payload: dict) -> tuple[str, str, str]:
    return (payload["ssot_id"], payload["task_id"], payload["slice_id"])


def supported_evidence_requirements(agent_type: str) -> set[str]:
    try:
        return SUPPORTED_EVIDENCE_REQUIREMENTS[agent_type]
    except KeyError as exc:
        raise AssertionError(f"unsupported agent_type {agent_type!r}") from exc


def normalize_scope_paths(paths: list[str]) -> list[str]:
    return sorted(path.rstrip("/") for path in paths)


def is_within(touched: str, scope_paths: list[str]) -> bool:
    touched = touched.rstrip("/")
    for scope_path in scope_paths:
        normalized = scope_path.rstrip("/")
        if touched == normalized:
            return True
        if touched.startswith(normalized + "/"):
            return True
    return False


def overlaps(a: str, b: str) -> bool:
    a = a.rstrip("/")
    b = b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def assert_builder_path_constraints(payload: dict, *, label: str) -> None:
    ownership_paths = payload["ownership_paths"]
    if not ownership_paths:
        raise AssertionError(f"{label}: builder slice must declare ownership_paths")


def assert_no_builder_ownership_overlap(builders: list[dict], *, label: str) -> None:
    for i in range(len(builders)):
        left = builders[i]
        for j in range(i + 1, len(builders)):
            right = builders[j]
            for left_path in left["ownership_paths"]:
                for right_path in right["ownership_paths"]:
                    if overlaps(left_path, right_path):
                        raise AssertionError(
                            f"{label}: ownership overlap between builder slices "
                            f"{left['slice_id']} and {right['slice_id']}: "
                            f"{left_path!r} vs {right_path!r}"
                        )


def assert_known_dispatch_agent_type(payload: dict, *, label: str) -> None:
    agent_type = payload.get("agent_type")
    allowed = {"runner", "builder", "inspector"}

    if agent_type is not None and agent_type not in allowed:
        raise AssertionError(f"{label}: unknown agent_type detected: {agent_type}")


def canonical_result_agent_type(payload: dict, *, label: str) -> str:
    agent_type = payload.get("agent_type")
    role = payload.get("role")
    allowed = {"runner", "builder", "inspector"}

    if agent_type is None and role is None:
        raise AssertionError(f"{label}: result must provide agent_type or legacy role")
    if agent_type is not None and agent_type not in allowed:
        raise AssertionError(f"{label}: unknown agent_type detected: {agent_type}")
    if role is not None and role not in allowed:
        raise AssertionError(f"{label}: unknown legacy role detected: {role}")
    if agent_type is not None and role is not None and agent_type != role:
        raise AssertionError(
            f"{label}: agent_type and legacy role must agree when both are present"
        )

    return agent_type or role


def assert_dispatch_ownership_semantics(payload: dict, *, label: str) -> None:
    agent_type = payload["agent_type"]
    ownership_paths = payload.get("ownership_paths", [])
    if agent_type == "builder":
        assert_builder_path_constraints(
            {"ownership_paths": ownership_paths}, label=label
        )
        return
    if ownership_paths:
        raise AssertionError(
            f"{label}: non-builder slices must omit ownership_paths or leave them empty"
        )


def assert_supported_evidence_requirements(
    agent_type: str, requirements: list[str], *, label: str
) -> None:
    unsupported = sorted(set(requirements) - supported_evidence_requirements(agent_type))
    if unsupported:
        raise AssertionError(
            f"{label}: unsupported evidence_requirements for {agent_type}: {unsupported}"
        )


def payload_satisfies_evidence_requirement(
    payload: dict, *, agent_type: str, requirement: str
) -> bool:
    if agent_type == "runner":
        evidence = payload.get("evidence", {})
        if requirement == "analysis":
            return bool(evidence.get("analysis"))
        if requirement == "commands":
            return bool(evidence.get("commands"))
        if requirement == "files_read":
            return bool(evidence.get("files_read"))
    elif agent_type == "builder":
        evidence = payload.get("evidence", {})
        if requirement == "diff":
            return bool(evidence.get("diff_summary"))
        if requirement == "git_diff":
            return bool(evidence.get("git_diff_summary"))
        if requirement == "verification":
            return bool(payload.get("verification"))
    elif agent_type == "inspector":
        if requirement == "review_notes":
            return bool(payload.get("review_notes"))

    return False


def assert_result_satisfies_requirements(
    payload: dict,
    requirements: list[str],
    *,
    agent_type: str,
    label: str,
) -> None:
    assert_supported_evidence_requirements(
        agent_type, requirements, label=f"{label}.evidence_requirements"
    )
    missing = [
        requirement
        for requirement in requirements
        if not payload_satisfies_evidence_requirement(
            payload, agent_type=agent_type, requirement=requirement
        )
    ]
    if missing:
        raise AssertionError(
            f"{label}: missing evidence payload for requirements {missing}"
        )


def result_requires_final_evidence(payload: dict, *, agent_type: str) -> bool:
    status = payload.get("status")
    if agent_type in {"runner", "builder"} and status in {"blocked", "partial"}:
        return False
    return True


def assert_unique_slice_ids(dispatches: list[dict], *, label: str) -> None:
    slice_ids = [d["slice_id"] for d in dispatches]
    if len(slice_ids) != len(set(slice_ids)):
        duplicates = sorted({sid for sid in slice_ids if slice_ids.count(sid) > 1})
        raise AssertionError(f"{label}: duplicate slice_id(s): {', '.join(duplicates)}")


def assert_dependency_targets_exist(dispatches: list[dict], *, label: str) -> None:
    slice_ids = {d["slice_id"] for d in dispatches}
    for d in dispatches:
        for dep in d.get("dependencies", []):
            if dep not in slice_ids:
                raise AssertionError(
                    f"{label}: {d['slice_id']} depends on missing slice_id {dep!r}"
                )


def validate_dispatches(path: Path, expected_count: int) -> list[dict]:
    dispatches = load_json(path)
    if not isinstance(dispatches, list):
        raise AssertionError(f"{path.name} must be a JSON array")
    if len(dispatches) != expected_count:
        raise AssertionError(
            f"{path.name}: expected {expected_count} items, got {len(dispatches)}"
        )

    assert_unique_slice_ids(dispatches, label=path.name)
    assert_dependency_targets_exist(dispatches, label=path.name)

    for i, payload in enumerate(dispatches, 1):
        assert_known_dispatch_agent_type(payload, label=f"{path.name}[{i}]")
        validate_one(TASK_DISPATCH_SCHEMA_ID, payload, f"{path.name}[{i}]")
        assert_dispatch_ownership_semantics(payload, label=f"{path.name}[{i}]")
        assert_supported_evidence_requirements(
            payload["agent_type"],
            payload.get("evidence_requirements", []),
            label=f"{path.name}[{i}]",
        )
        assert_ssot_id_policy(payload["ssot_id"])

    return dispatches


def assert_handoff_requests(
    payload: dict, *, dispatch_schema_id: str, label: str
) -> None:
    requests = payload.get("handoff_requests", [])
    handoff_ids = [request["slice_id"] for request in requests]
    if len(handoff_ids) != len(set(handoff_ids)):
        duplicates = sorted(
            {slice_id for slice_id in handoff_ids if handoff_ids.count(slice_id) > 1}
        )
        raise AssertionError(
            f"{label}.handoff_requests: duplicate slice_id(s): {', '.join(duplicates)}"
        )

    for i, request in enumerate(requests, 1):
        assert_known_dispatch_agent_type(request, label=f"{label}.handoff_requests[{i}]")
        validate_one(dispatch_schema_id, request, f"{label}.handoff_requests[{i}]")
        assert_dispatch_ownership_semantics(
            request, label=f"{label}.handoff_requests[{i}]"
        )
        assert_supported_evidence_requirements(
            request["agent_type"],
            request.get("evidence_requirements", []),
            label=f"{label}.handoff_requests[{i}]",
        )
        if request["ssot_id"] != payload["ssot_id"]:
            raise AssertionError(
                f"{label}.handoff_requests[{i}]: ssot_id must match parent result"
            )
        if request["task_id"] != payload["task_id"]:
            raise AssertionError(
                f"{label}.handoff_requests[{i}]: task_id must match parent result"
            )
        allowed_dependencies = {
            payload["slice_id"],
            *[
                sibling_id
                for sibling_id in handoff_ids
                if sibling_id != request["slice_id"]
            ],
        }
        for dep in request.get("dependencies", []):
            if dep not in allowed_dependencies:
                raise AssertionError(
                    f"{label}.handoff_requests[{i}]: dependency {dep!r} must target "
                    "the parent slice or a sibling handoff slice"
                )
        assert_ssot_id_policy(request["ssot_id"])


def assert_multi_ticket_invariants(dispatches: list[dict], *, label: str) -> None:
    if not all(d["slice_id"].startswith("multi--") for d in dispatches):
        bad = [d["slice_id"] for d in dispatches if not d["slice_id"].startswith("multi--")]
        raise AssertionError(
            f"{label}: slice_id must start with `multi--`: " + ", ".join(bad)
        )

    builders = [d for d in dispatches if d["agent_type"] == "builder"]
    runners = [d for d in dispatches if d["agent_type"] == "runner"]

    if not builders or not runners:
        raise AssertionError(f"{label} must include runner and builder slices")

    for payload in builders:
        assert_dispatch_ownership_semantics(payload, label=payload["slice_id"])
    assert_no_builder_ownership_overlap(builders, label=label)


def count_initial_runnable_dispatches(dispatches: list[dict]) -> int:
    locked_builder_paths: list[str] = []
    runnable = 0

    for dispatch in dispatches:
        if dispatch.get("dependencies"):
            continue

        if dispatch["agent_type"] != "builder":
            runnable += 1
            continue

        ownership_paths = dispatch.get("ownership_paths", [])
        if any(
            overlaps(left_path, right_path)
            for left_path in ownership_paths
            for right_path in locked_builder_paths
        ):
            continue

        locked_builder_paths.extend(ownership_paths)
        runnable += 1

    return runnable


def is_single_fast_path(*, tiny_clear_low_risk: bool, t_max_s: int) -> bool:
    return tiny_clear_low_risk and t_max_s <= SINGLE_FAST_PATH_MAX_S


def assert_route_case_contract(payload: dict, *, label: str) -> None:
    route = payload["route"]
    t_max_s = payload["t_max_s"]
    tiny_clear_low_risk = payload["tiny_clear_low_risk"]
    initial_runnable_count = payload["initial_runnable_count"]
    dispatch_fixture = payload["dispatch_fixture"]
    expected_agent_types = payload["expected_agent_types"]

    single_fast_path = is_single_fast_path(
        tiny_clear_low_risk=tiny_clear_low_risk,
        t_max_s=t_max_s,
    )

    if route == "single":
        if not single_fast_path:
            raise AssertionError(
                f"{label}: `single` requires tiny_clear_low_risk=true and "
                f"t_max_s<={SINGLE_FAST_PATH_MAX_S}"
            )
        if (
            initial_runnable_count != 0
            or dispatch_fixture is not None
            or expected_agent_types
        ):
            raise AssertionError(
                f"{label}: `single` must not spawn or reference dispatch fixtures"
            )
        return

    if single_fast_path:
        raise AssertionError(
            f"{label}: `multi` is only valid when the task is outside the "
            f"`single` fast path (tiny_clear_low_risk=true and "
            f"t_max_s<={SINGLE_FAST_PATH_MAX_S})"
        )
    if initial_runnable_count <= 0:
        raise AssertionError(
            f"{label}: `multi` must expose at least one initially runnable slice"
        )
    if not dispatch_fixture:
        raise AssertionError(f"{label}: `multi` must reference a dispatch fixture")

    dispatches = load_json(E2E_DIR / dispatch_fixture)
    if not isinstance(dispatches, list):
        raise AssertionError(f"{label}: {dispatch_fixture} must be a JSON array")
    actual_initial_runnable_count = count_initial_runnable_dispatches(dispatches)
    if actual_initial_runnable_count != initial_runnable_count:
        raise AssertionError(
            f"{label}: initial_runnable_count={initial_runnable_count} does not match "
            f"{dispatch_fixture} initially runnable count {actual_initial_runnable_count}"
        )

    actual_agent_types = sorted({dispatch["agent_type"] for dispatch in dispatches})
    if sorted(expected_agent_types) != actual_agent_types:
        raise AssertionError(
            f"{label}: expected agent types {sorted(expected_agent_types)} != "
            f"{actual_agent_types} from {dispatch_fixture}"
        )


def assert_route_cases() -> None:
    route_cases = load_json(E2E_DIR / "route_cases.json")
    if not isinstance(route_cases, list):
        raise AssertionError("route_cases.json must be a JSON array")
    if len(route_cases) < 3:
        raise AssertionError(
            "route_cases.json must include at least one `single` case and multiple `multi` cases"
        )

    seen_ids: set[str] = set()
    seen_routes: set[str] = set()
    valid_routes = {"single", "multi"}

    for index, payload in enumerate(route_cases, 1):
        label = f"route_cases.json[{index}]"
        if not isinstance(payload, dict):
            raise AssertionError(f"{label}: route case must be a JSON object")

        scenario_id = payload.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise AssertionError(f"{label}: scenario_id must be a non-empty string")
        if scenario_id in seen_ids:
            raise AssertionError(f"{label}: duplicate scenario_id {scenario_id!r}")
        seen_ids.add(scenario_id)

        route = payload.get("route")
        if route not in valid_routes:
            raise AssertionError(f"{label}: route must be one of {sorted(valid_routes)}")
        seen_routes.add(route)

        t_max_s = payload.get("t_max_s")
        if not isinstance(t_max_s, int) or t_max_s <= 0:
            raise AssertionError(f"{label}: t_max_s must be a positive integer")

        t_why = payload.get("t_why")
        if not isinstance(t_why, str) or not t_why.strip():
            raise AssertionError(f"{label}: t_why must be a non-empty string")

        tiny_clear_low_risk = payload.get("tiny_clear_low_risk")
        if not isinstance(tiny_clear_low_risk, bool):
            raise AssertionError(f"{label}: tiny_clear_low_risk must be a boolean")

        initial_runnable_count = payload.get("initial_runnable_count")
        if not isinstance(initial_runnable_count, int) or initial_runnable_count < 0:
            raise AssertionError(
                f"{label}: initial_runnable_count must be a non-negative integer"
            )

        dispatch_fixture = payload.get("dispatch_fixture")
        if dispatch_fixture is not None and not isinstance(dispatch_fixture, str):
            raise AssertionError(f"{label}: dispatch_fixture must be a string or null")

        expected_agent_types = payload.get("expected_agent_types")
        if not isinstance(expected_agent_types, list) or any(
            not isinstance(agent_type, str) for agent_type in expected_agent_types
        ):
            raise AssertionError(f"{label}: expected_agent_types must be a list of strings")

        assert_route_case_contract(payload, label=label)

    if seen_routes != valid_routes:
        raise AssertionError(
            "route_cases.json must cover exactly `single` and `multi`"
        )


def lookup_matching_dispatch(
    payload: dict, dispatches_by_key: dict[tuple[str, str, str], dict], *, label: str
) -> dict:
    key = dispatch_match_key(payload)
    dispatch = dispatches_by_key.get(key)
    if dispatch is None:
        raise AssertionError(
            f"{label}: no matching dispatch for "
            f"ssot_id={payload['ssot_id']!r}, task_id={payload['task_id']!r}, "
            f"slice_id={payload['slice_id']!r}"
        )
    return dispatch


def assert_result_matches_dispatch(
    payload: dict,
    dispatches_by_key: dict[tuple[str, str, str], dict],
    *,
    label: str,
) -> None:
    agent_type = canonical_result_agent_type(payload, label=label)
    dispatch = lookup_matching_dispatch(payload, dispatches_by_key, label=label)
    if dispatch["agent_type"] != agent_type:
        raise AssertionError(
            f"{label}: matching dispatch must use agent_type={agent_type}"
        )

    if result_requires_final_evidence(payload, agent_type=agent_type):
        assert_result_satisfies_requirements(
            payload,
            dispatch.get("evidence_requirements", []),
            agent_type=agent_type,
            label=label,
        )

    if agent_type != "builder":
        return

    work_package_id = payload.get("work_package_id")
    if work_package_id is None:
        if not builder_schema_accepts_true_legacy_result():
            raise AssertionError(
                f"{label}: work_package_id is required by the current /1 builder compatibility contract"
            )
    elif work_package_id != dispatch["work_package_id"]:
        raise AssertionError(
            f"{label}: work_package_id must match the originating dispatch"
        )

    result_scope = normalize_scope_paths(payload["ownership_paths"])
    dispatch_scope = normalize_scope_paths(dispatch.get("ownership_paths", []))
    if result_scope != dispatch_scope:
        raise AssertionError(
            f"{label}: ownership_paths must match the originating dispatch"
        )

    if payload.get("status") in {"blocked", "partial"}:
        return

    for touched_path in payload["changeset"]["touched_paths"]:
        if not is_within(touched_path, dispatch["ownership_paths"]):
            raise AssertionError(
                f"{label}: touched path "
                f"{touched_path!r} is outside dispatch ownership_paths"
            )


def make_legacy_role_result(payload: dict) -> dict:
    legacy = json.loads(json.dumps(payload))
    agent_type = legacy.pop("agent_type", None)
    if agent_type is None:
        raise AssertionError("legacy compatibility payload requires canonical agent_type")
    legacy["role"] = agent_type
    return legacy


def clone_payload(payload: dict) -> dict:
    return json.loads(json.dumps(payload))


@lru_cache(maxsize=1)
def builder_schema_accepts_true_legacy_result() -> bool:
    legacy_builder = make_legacy_role_result(load_json(E2E_DIR / "result.builder.json"))
    legacy_builder.pop("work_package_id", None)
    validator = validator_for_id(BUILDER_RESULT_SCHEMA_ID)
    return not any(validator.iter_errors(legacy_builder))


def assert_rejected(
    action,
    *,
    label: str,
    expected_substring: str,
) -> None:
    try:
        action()
    except AssertionError as exc:
        message = str(exc)
        if expected_substring not in message:
            raise AssertionError(
                f"{label}: expected rejection containing {expected_substring!r}, got {message!r}"
            ) from exc
        print(f"OK: {label} rejected ({message})")
        return
    raise AssertionError(f"{label}: expected rejection containing {expected_substring!r}")


def validate_results(dispatches_by_key: dict[tuple[str, str, str], dict]) -> None:
    results = [
        ("result.runner.json", RUNNER_RESULT_SCHEMA_ID),
        ("result.builder.json", BUILDER_RESULT_SCHEMA_ID),
        ("result.inspector.pass.json", INSPECTOR_RESULT_SCHEMA_ID),
        ("result.inspector.block.json", INSPECTOR_RESULT_SCHEMA_ID),
        ("result.inspector.needs_evidence.json", INSPECTOR_RESULT_SCHEMA_ID),
    ]

    for filename, schema_id in results:
        payload = load_json(E2E_DIR / filename)
        canonical_result_agent_type(payload, label=filename)
        assert_json_only_output(payload, E2E_DIR / filename)
        validate_one(schema_id, payload, filename)
        assert_ssot_id_policy(payload["ssot_id"])

        if filename in {"result.runner.json", "result.builder.json"}:
            assert_handoff_requests(
                payload,
                dispatch_schema_id=TASK_DISPATCH_SCHEMA_ID,
                label=filename,
            )

        legacy_payload = make_legacy_role_result(payload)
        canonical_result_agent_type(legacy_payload, label=f"{filename}.legacy_role")
        validate_one(schema_id, legacy_payload, f"{filename}.legacy_role")
        assert_ssot_id_policy(legacy_payload["ssot_id"])

        if filename in {"result.runner.json", "result.builder.json"}:
            assert_handoff_requests(
                legacy_payload,
                dispatch_schema_id=TASK_DISPATCH_SCHEMA_ID,
                label=f"{filename}.legacy_role",
            )

        assert_result_matches_dispatch(
            payload,
            dispatches_by_key,
            label=filename,
        )
        assert_result_matches_dispatch(
            legacy_payload,
            dispatches_by_key,
            label=f"{filename}.legacy_role",
        )

    builder = load_json(E2E_DIR / "result.builder.json")
    true_legacy_builder = make_legacy_role_result(builder)
    true_legacy_builder.pop("work_package_id", None)
    if builder_schema_accepts_true_legacy_result():
        canonical_result_agent_type(
            true_legacy_builder,
            label="result.builder.json.true_legacy_role",
        )
        validate_one(
            BUILDER_RESULT_SCHEMA_ID,
            true_legacy_builder,
            "result.builder.json.true_legacy_role",
        )
        assert_result_matches_dispatch(
            true_legacy_builder,
            dispatches_by_key,
            label="result.builder.json.true_legacy_role",
        )
    else:
        assert_schema_rejects(
            BUILDER_RESULT_SCHEMA_ID,
            true_legacy_builder,
            "result.builder.json.true_legacy_role",
        )


def assert_negative_regressions(
    dispatches_by_key: dict[tuple[str, str, str], dict],
) -> None:
    result_mismatch = clone_payload(load_json(E2E_DIR / "result.runner.json"))
    result_mismatch["role"] = "builder"
    assert_rejected(
        lambda: canonical_result_agent_type(
            result_mismatch, label="result.runner.json.role_mismatch"
        ),
        label="result.runner.json.role_mismatch.identity",
        expected_substring="must agree",
    )
    assert_schema_rejects(
        RUNNER_RESULT_SCHEMA_ID,
        result_mismatch,
        "result.runner.json.role_mismatch.schema",
    )

    read_only_dispatch = clone_payload(
        load_json(E2E_DIR / "dispatches.read_only.json")[0]
    )
    read_only_dispatch["ownership_paths"] = ["tmp/"]
    assert_rejected(
        lambda: assert_dispatch_ownership_semantics(
            read_only_dispatch, label="dispatches.read_only.json.non_builder_scope"
        ),
        label="dispatches.read_only.json.non_builder_scope.policy",
        expected_substring="non-builder slices must omit ownership_paths or leave them empty",
    )
    assert_schema_rejects(
        TASK_DISPATCH_SCHEMA_ID,
        read_only_dispatch,
        "dispatches.read_only.json.non_builder_scope.schema",
    )

    builder_mismatch = clone_payload(load_json(E2E_DIR / "result.builder.json"))
    builder_mismatch["work_package_id"] = builder_mismatch["work_package_id"] + "-mismatch"
    assert_rejected(
        lambda: assert_result_matches_dispatch(
            builder_mismatch,
            dispatches_by_key,
            label="result.builder.json.work_package_mismatch",
        ),
        label="result.builder.json.work_package_mismatch",
        expected_substring="work_package_id must match",
    )

    invalid_handoff = clone_payload(load_json(E2E_DIR / "result.runner.json"))
    invalid_handoff["handoff_requests"][0]["dependencies"] = ["missing-slice"]
    assert_rejected(
        lambda: assert_handoff_requests(
            invalid_handoff,
            dispatch_schema_id=TASK_DISPATCH_SCHEMA_ID,
            label="result.runner.json.invalid_handoff_dependency",
        ),
        label="result.runner.json.invalid_handoff_dependency",
        expected_substring="must target the parent slice or a sibling handoff slice",
    )

    blocked_runner_missing_recovery = {
        "schema": "worker-result.runner/1",
        "ssot_id": "e2e-read-04c9d864d719",
        "task_id": "e2e-read_only",
        "slice_id": "runner-01",
        "agent_type": "runner",
        "status": "blocked",
        "summary": "Blocked without recovery contract."
    }
    assert_schema_rejects(
        RUNNER_RESULT_SCHEMA_ID,
        blocked_runner_missing_recovery,
        "result.runner.json.blocked_missing_recovery",
    )

    partial_builder_missing_recovery = {
        "schema": "worker-result.builder/1",
        "ssot_id": "e2e-write-4aeb119f4748",
        "task_id": "e2e-write_mixed",
        "slice_id": "builder-01",
        "work_package_id": "pkg-write-builder-01",
        "agent_type": "builder",
        "status": "partial",
        "summary": "Partial without recovery contract.",
        "ownership_paths": ["multi-agent/schemas/"],
    }
    assert_schema_rejects(
        BUILDER_RESULT_SCHEMA_ID,
        partial_builder_missing_recovery,
        "result.builder.json.partial_missing_recovery",
    )

    tiny_over_cap_single = {
        "scenario_id": "route-single-over-cap",
        "route": "single",
        "t_max_s": 75,
        "t_why": "Still small, but over the verified single fast-path threshold.",
        "tiny_clear_low_risk": True,
        "initial_runnable_count": 0,
        "dispatch_fixture": None,
        "expected_agent_types": [],
    }
    assert_rejected(
        lambda: assert_route_case_contract(
            tiny_over_cap_single,
            label="route_cases.single_over_cap",
        ),
        label="route_cases.single_over_cap",
        expected_substring="t_max_s<=60",
    )

    tiny_fast_multi = {
        "scenario_id": "route-multi-under-cap",
        "route": "multi",
        "t_max_s": 45,
        "t_why": "Tiny fast-path task should not escalate.",
        "tiny_clear_low_risk": True,
        "initial_runnable_count": 1,
        "dispatch_fixture": "dispatches.serial_multi.json",
        "expected_agent_types": ["builder", "runner"],
    }
    assert_rejected(
        lambda: assert_route_case_contract(
            tiny_fast_multi,
            label="route_cases.multi_fast_path",
        ),
        label="route_cases.multi_fast_path",
        expected_substring="outside the `single` fast path",
    )

    blocked_runner = clone_payload(load_json(E2E_DIR / "result.runner.json"))
    blocked_runner["status"] = "blocked"
    blocked_runner["summary"] = "Waiting on a narrowed follow-up slice."
    blocked_runner.pop("evidence", None)
    blocked_runner.pop("next_actions", None)
    blocked_runner["recovery"] = {
        "blocked_reason": "Need a narrower follow-up slice before final evidence can be gathered.",
        "checkpoint": {
            "state": "blocked",
            "last_action": "Mapped the remaining unknowns.",
            "resume_from": "Re-dispatch a narrower read-only slice for the unresolved area.",
            "next_steps": [
                "Confirm the remaining unknown input.",
                "Dispatch the narrowed follow-up slice.",
                "Collect the missing final evidence once the blocker is resolved.",
            ],
        },
    }
    validate_one(
        RUNNER_RESULT_SCHEMA_ID,
        blocked_runner,
        "result.runner.json.blocked_recovery_only",
    )
    assert_result_matches_dispatch(
        blocked_runner,
        dispatches_by_key,
        label="result.runner.json.blocked_recovery_only",
    )

    partial_builder = clone_payload(load_json(E2E_DIR / "result.builder.json"))
    partial_builder["status"] = "partial"
    partial_builder["summary"] = "Applied part of the change set and returned a checkpoint."
    partial_builder.pop("changeset", None)
    partial_builder.pop("evidence", None)
    partial_builder.pop("verification", None)
    partial_builder["recovery"] = {
        "required_evidence": ["verification"],
        "checkpoint": {
            "state": "partial",
            "last_action": "Applied the safe subset inside the owned scope.",
            "resume_from": "Continue the owned builder slice after the remaining blocker clears.",
            "next_steps": [
                "Reopen the owned slice.",
                "Finish the remaining edit.",
                "Capture verification evidence for closeout.",
            ],
        },
    }
    validate_one(
        BUILDER_RESULT_SCHEMA_ID,
        partial_builder,
        "result.builder.json.partial_recovery_only",
    )
    assert_result_matches_dispatch(
        partial_builder,
        dispatches_by_key,
        label="result.builder.json.partial_recovery_only",
    )

    inspector_missing_notes = clone_payload(
        load_json(E2E_DIR / "result.inspector.pass.json")
    )
    inspector_missing_notes["review_notes"] = []
    assert_rejected(
        lambda: assert_result_matches_dispatch(
            inspector_missing_notes,
            dispatches_by_key,
            label="result.inspector.pass.json.missing_review_notes",
        ),
        label="result.inspector.pass.json.missing_review_notes",
        expected_substring="missing evidence payload",
    )

    legacy_builder_missing_work_package = make_legacy_role_result(
        load_json(E2E_DIR / "result.builder.json")
    )
    legacy_builder_missing_work_package.pop("work_package_id", None)
    if builder_schema_accepts_true_legacy_result():
        validate_one(
            BUILDER_RESULT_SCHEMA_ID,
            legacy_builder_missing_work_package,
            "result.builder.json.true_legacy_role.policy",
        )
        assert_result_matches_dispatch(
            legacy_builder_missing_work_package,
            dispatches_by_key,
            label="result.builder.json.true_legacy_role.policy",
        )
    else:
        assert_schema_rejects(
            BUILDER_RESULT_SCHEMA_ID,
            legacy_builder_missing_work_package,
            "result.builder.json.true_legacy_role.policy",
        )
        assert_rejected(
            lambda: assert_result_matches_dispatch(
                legacy_builder_missing_work_package,
                dispatches_by_key,
                label="result.builder.json.true_legacy_role.policy",
            ),
            label="result.builder.json.true_legacy_role.policy",
            expected_substring="work_package_id is required",
        )


def assert_schema_registry_resolution() -> None:
    resolver = load_schema_catalog().registry.resolver()
    shared_refs = [
        "worker-result.builder/task-dispatch/1",
        "worker-result.runner/task-dispatch/1",
    ]

    for ref in shared_refs:
        resolved = resolver.lookup(ref)
        resolved_schema_id = resolved.contents.get("$id")
        if resolved_schema_id != TASK_DISPATCH_SCHEMA_ID:
            raise AssertionError(
                f"{ref}: expected {TASK_DISPATCH_SCHEMA_ID}, got {resolved_schema_id!r}"
            )
        print(f"OK: schema registry resolves {ref} -> {resolved_schema_id}")

    malformed_ref = "malformed/task-dispatch/1"
    try:
        resolver.lookup(malformed_ref)
    except Unresolvable:
        print(f"OK: schema registry rejects malformed prefix ({malformed_ref})")
        return

    raise AssertionError(
        f"{malformed_ref}: expected malformed prefix lookup to fail"
    )


def extend_dispatch_index(
    dispatches_by_key: dict[tuple[str, str, str], dict], dispatches: list[dict], *, label: str
) -> None:
    for dispatch in dispatches:
        key = dispatch_match_key(dispatch)
        existing = dispatches_by_key.get(key)
        if existing is not None:
            raise AssertionError(
                f"{label}: duplicate dispatch match key {key!r} across fixtures"
            )
        dispatches_by_key[key] = dispatch


def assert_dispatch_invariants() -> dict[tuple[str, str, str], dict]:
    dispatches_by_key: dict[tuple[str, str, str], dict] = {}

    read_only = validate_dispatches(
        E2E_DIR / "dispatches.read_only.json", expected_count=16
    )
    if any(d["agent_type"] != "runner" for d in read_only):
        raise AssertionError("read_only dispatches must use agent_type=runner only")
    if any(d.get("ownership_paths", []) for d in read_only):
        raise AssertionError("read_only dispatches must have empty ownership_paths")
    extend_dispatch_index(dispatches_by_key, read_only, label="dispatches.read_only.json")

    write = validate_dispatches(E2E_DIR / "dispatches.write_mixed.json", expected_count=12)
    builders = [d for d in write if d["agent_type"] == "builder"]
    runners = [d for d in write if d["agent_type"] == "runner"]
    if len(builders) != 6 or len(runners) != 6:
        raise AssertionError(
            "write_mixed dispatches must be exactly 6 builder + 6 runner slices"
        )

    for payload in builders:
        assert_dispatch_ownership_semantics(payload, label=payload["slice_id"])
    assert_no_builder_ownership_overlap(builders, label="dispatches.write_mixed.json")
    extend_dispatch_index(dispatches_by_key, write, label="dispatches.write_mixed.json")

    serial_multi = validate_dispatches(
        E2E_DIR / "dispatches.serial_multi.json", expected_count=2
    )
    assert_multi_ticket_invariants(serial_multi, label="dispatches.serial_multi.json")
    extend_dispatch_index(
        dispatches_by_key, serial_multi, label="dispatches.serial_multi.json"
    )

    workstreams = validate_dispatches(E2E_DIR / "dispatches.workstreams.json", expected_count=7)
    assert_multi_ticket_invariants(workstreams, label="dispatches.workstreams.json")
    extend_dispatch_index(dispatches_by_key, workstreams, label="dispatches.workstreams.json")
    assert_route_cases()
    return dispatches_by_key


def main() -> None:
    dispatches_by_key = assert_dispatch_invariants()
    validate_results(dispatches_by_key)
    assert_negative_regressions(dispatches_by_key)
    assert_schema_registry_resolution()
    print("OK: fixtures + route cases + invariants (two-state)")


if __name__ == "__main__":
    main()
