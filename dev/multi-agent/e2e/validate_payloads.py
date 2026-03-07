from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "multi-agent"
SCHEMAS_DIR = SKILL_ROOT / "schemas"
E2E_DIR = Path(__file__).resolve().parent


def load_json(path: Path):
    text = path.read_text()
    stripped = text.strip()
    if stripped.startswith("```") or stripped.endswith("```"):
        raise AssertionError(
            f"{path.name}: worker output must be raw JSON only; code fences are not allowed"
        )
    return json.loads(stripped)


def validate_one(schema_path: Path, payload: dict, label: str) -> None:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    print(f"OK: {label} against {schema_path.relative_to(SKILL_ROOT)}")


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


def is_within(touched: str, allowed_paths: list[str]) -> bool:
    touched = touched.rstrip("/")
    for allowed in allowed_paths:
        normalized = allowed.rstrip("/")
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
    allowed_paths = payload["allowed_paths"]

    if not ownership_paths:
        raise AssertionError(f"{label}: builder slice must declare ownership_paths")
    if not allowed_paths:
        raise AssertionError(f"{label}: builder slice must declare allowed_paths")

    for ownership_path in ownership_paths:
        if not is_within(ownership_path, allowed_paths):
            raise AssertionError(
                f"{label}: ownership path {ownership_path!r} is outside allowed_paths"
            )


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


def assert_no_forbidden_roles(payload: dict, *, label: str) -> None:
    agent_type = payload.get("agent_type")
    role = payload.get("role")
    allowed = {"runner", "builder", "inspector"}

    if role is not None and role not in allowed:
        raise AssertionError(f"{label}: unknown role detected: {role}")
    if agent_type is not None and agent_type not in allowed:
        raise AssertionError(f"{label}: unknown agent_type detected: {agent_type}")


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

    schema_path = SCHEMAS_DIR / "task-dispatch.schema.json"
    for i, payload in enumerate(dispatches, 1):
        assert_no_forbidden_roles(payload, label=f"{path.name}[{i}]")
        validate_one(schema_path, payload, f"{path.name}[{i}]")
        assert_ssot_id_policy(payload["ssot_id"])

    return dispatches


def assert_handoff_requests(
    payload: dict, *, dispatch_schema: Path, label: str
) -> None:
    for i, request in enumerate(payload.get("handoff_requests", []), 1):
        assert_no_forbidden_roles(request, label=f"{label}.handoff_requests[{i}]")
        validate_one(dispatch_schema, request, f"{label}.handoff_requests[{i}]")
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
        assert_builder_path_constraints(payload, label=payload["slice_id"])
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

        if route == "single":
            if not tiny_clear_low_risk:
                raise AssertionError(
                    f"{label}: `single` requires tiny_clear_low_risk=true"
                )
            if (
                initial_runnable_count != 0
                or dispatch_fixture is not None
                or expected_agent_types
            ):
                raise AssertionError(
                    f"{label}: `single` must not spawn or reference dispatch fixtures"
                )
            continue

        if tiny_clear_low_risk:
            raise AssertionError(
                f"{label}: `multi` is only valid when the task is outside the `single` fast path"
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

    if seen_routes != valid_routes:
        raise AssertionError(
            "route_cases.json must cover exactly `single` and `multi`"
        )


def validate_results() -> None:
    runner_schema = SCHEMAS_DIR / "worker-result.runner.schema.json"
    builder_schema = SCHEMAS_DIR / "worker-result.builder.schema.json"
    inspector_schema = SCHEMAS_DIR / "review-result.inspector.schema.json"
    dispatch_schema = SCHEMAS_DIR / "task-dispatch.schema.json"

    results = [
        ("result.runner.json", runner_schema),
        ("result.builder.json", builder_schema),
        ("result.inspector.pass.json", inspector_schema),
        ("result.inspector.block.json", inspector_schema),
        ("result.inspector.needs_evidence.json", inspector_schema),
    ]

    for filename, schema_path in results:
        payload = load_json(E2E_DIR / filename)
        assert_no_forbidden_roles(payload, label=filename)
        assert_json_only_output(payload, E2E_DIR / filename)
        validate_one(schema_path, payload, filename)
        assert_ssot_id_policy(payload["ssot_id"])

        if filename in {"result.runner.json", "result.builder.json"}:
            assert_handoff_requests(
                payload,
                dispatch_schema=dispatch_schema,
                label=filename,
            )

    builder = load_json(E2E_DIR / "result.builder.json")
    for touched_path in builder["changeset"]["touched_paths"]:
        if not is_within(touched_path, builder["allowed_paths"]):
            raise AssertionError(
                "result.builder.json: touched path "
                f"{touched_path!r} is outside allowed_paths"
            )


def assert_dispatch_invariants() -> None:
    read_only = validate_dispatches(
        E2E_DIR / "dispatches.read_only.json", expected_count=16
    )
    if any(d["agent_type"] != "runner" for d in read_only):
        raise AssertionError("read_only dispatches must use agent_type=runner only")
    if any(d["ownership_paths"] for d in read_only):
        raise AssertionError("read_only dispatches must have empty ownership_paths")

    write = validate_dispatches(E2E_DIR / "dispatches.write_mixed.json", expected_count=12)
    builders = [d for d in write if d["agent_type"] == "builder"]
    runners = [d for d in write if d["agent_type"] == "runner"]
    if len(builders) != 6 or len(runners) != 6:
        raise AssertionError(
            "write_mixed dispatches must be exactly 6 builder + 6 runner slices"
        )

    for payload in builders:
        assert_builder_path_constraints(payload, label=payload["slice_id"])
    assert_no_builder_ownership_overlap(builders, label="dispatches.write_mixed.json")

    serial_multi = validate_dispatches(
        E2E_DIR / "dispatches.serial_multi.json", expected_count=2
    )
    assert_multi_ticket_invariants(serial_multi, label="dispatches.serial_multi.json")

    workstreams = validate_dispatches(E2E_DIR / "dispatches.workstreams.json", expected_count=7)
    assert_multi_ticket_invariants(workstreams, label="dispatches.workstreams.json")
    assert_route_cases()


def main() -> None:
    assert_dispatch_invariants()
    validate_results()
    print("OK: fixtures + route cases + invariants (two-state)")


if __name__ == "__main__":
    main()
