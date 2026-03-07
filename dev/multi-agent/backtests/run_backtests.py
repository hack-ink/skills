from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from broker_sim import (
    BrokerSimulator,
    assert_dispatch_contract,
    is_path_overlap,
    load_json,
)

BACKTESTS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = BACKTESTS_DIR / "scenarios"
E2E_DIR = BACKTESTS_DIR.parent / "e2e"
SINGLE_FAST_PATH_MAX_S = 60


def assert_expectations(
    scenario_id: str,
    expectations: dict,
    wait_any: dict,
    wait_all: dict,
) -> None:
    min_parallel = int(expectations.get("min_max_parallel", 1))
    if wait_any["max_parallel"] < min_parallel:
        raise AssertionError(
            f"{scenario_id}: max_parallel={wait_any['max_parallel']} < {min_parallel}"
        )

    min_lock_conflicts = int(expectations.get("min_lock_conflicts", 0))
    if wait_any["lock_conflicts"] < min_lock_conflicts:
        raise AssertionError(
            f"{scenario_id}: lock_conflicts={wait_any['lock_conflicts']} < {min_lock_conflicts}"
        )

    min_dedup_merged = int(expectations.get("min_dedup_merged", 0))
    if wait_any["dedup_merged"] < min_dedup_merged:
        raise AssertionError(
            f"{scenario_id}: dedup_merged={wait_any['dedup_merged']} < {min_dedup_merged}"
        )

    min_retry_count = int(expectations.get("min_retry_count", 0))
    if wait_any["retry_count"] < min_retry_count:
        raise AssertionError(
            f"{scenario_id}: retry_count={wait_any['retry_count']} < {min_retry_count}"
        )

    min_reuse_count = int(expectations.get("min_reuse_count", 0))
    if wait_any["reuse_count"] < min_reuse_count:
        raise AssertionError(
            f"{scenario_id}: reuse_count={wait_any['reuse_count']} < {min_reuse_count}"
        )

    min_reuse_count_by_agent = expectations.get("min_reuse_count_by_agent", {})
    if min_reuse_count_by_agent:
        if not isinstance(min_reuse_count_by_agent, dict):
            raise AssertionError(
                f"{scenario_id}: min_reuse_count_by_agent must be an object"
            )
        for agent_type, minimum in min_reuse_count_by_agent.items():
            if agent_type not in wait_any["reuse_count_by_agent"]:
                raise AssertionError(
                    f"{scenario_id}: unknown agent_type in min_reuse_count_by_agent: "
                    f"{agent_type!r}"
                )
            if wait_any["reuse_count_by_agent"][agent_type] < int(minimum):
                raise AssertionError(
                    f"{scenario_id}: reuse_count_by_agent[{agent_type!r}]="
                    f"{wait_any['reuse_count_by_agent'][agent_type]} < {minimum}"
                )

    expected_dispatch_count = expectations.get("expected_dispatch_count")
    if expected_dispatch_count is not None and wait_any["dispatch_count"] != int(
        expected_dispatch_count
    ):
        raise AssertionError(
            f"{scenario_id}: dispatch_count={wait_any['dispatch_count']} != {expected_dispatch_count}"
        )

    speedup_s = wait_all["makespan_s"] - wait_any["makespan_s"]
    min_speedup = int(expectations.get("min_wait_any_speedup_s", 0))
    if speedup_s < min_speedup:
        raise AssertionError(
            f"{scenario_id}: wait-any speedup={speedup_s}s < {min_speedup}s"
        )

    expected_wait_any = expectations.get("expected_wait_any_makespan_s")
    if expected_wait_any is not None and wait_any["makespan_s"] != int(expected_wait_any):
        raise AssertionError(
            f"{scenario_id}: wait_any makespan={wait_any['makespan_s']} != {expected_wait_any}"
        )

    expected_wait_all = expectations.get("expected_wait_all_makespan_s")
    if expected_wait_all is not None and wait_all["makespan_s"] != int(expected_wait_all):
        raise AssertionError(
            f"{scenario_id}: wait_all makespan={wait_all['makespan_s']} != {expected_wait_all}"
        )

    expected_ids = expectations.get("expected_completed_slice_ids")
    if expected_ids is not None:
        expected_set = sorted(set(expected_ids))
        actual_set = sorted(set(wait_any["completed_slice_ids"]))
        if actual_set != expected_set:
            raise AssertionError(
                f"{scenario_id}: completed slices mismatch: expected={expected_set}, got={actual_set}"
            )


def derive_route(
    *,
    tiny_clear_low_risk: bool,
    t_max_s: int,
) -> str:
    if tiny_clear_low_risk and t_max_s <= SINGLE_FAST_PATH_MAX_S:
        return "single"
    return "multi"


def clone_payload(payload: Any) -> Any:
    return json.loads(json.dumps(payload))


def assert_rejected(
    fn: Callable[[], object], *, label: str, expected_substring: str
) -> None:
    try:
        fn()
    except AssertionError as exc:
        if expected_substring not in str(exc):
            raise AssertionError(
                f"{label}: expected {expected_substring!r} in {exc!s}"
            ) from exc
        return
    raise AssertionError(f"{label}: expected AssertionError")


def count_initial_runnable_dispatches(dispatches: list[dict], *, label: str) -> int:
    locked_builder_paths: list[str] = []
    runnable = 0

    for index, dispatch in enumerate(dispatches):
        slice_id = (
            dispatch.get("slice_id", f"dispatch[{index}]")
            if isinstance(dispatch, dict)
            else f"dispatch[{index}]"
        )
        ownership_paths = assert_dispatch_contract(
            dispatch,
            label=f"{label}: {slice_id}",
        )

        if dispatch.get("dependencies", []):
            continue

        if dispatch["agent_type"] != "builder":
            runnable += 1
            continue

        if any(
            is_path_overlap(left_path, right_path)
            for left_path in ownership_paths
            for right_path in locked_builder_paths
        ):
            continue

        locked_builder_paths.extend(ownership_paths)
        runnable += 1

    return runnable


def run_scheduler_scenario(
    scenario_dir: Path, scenario: dict
) -> tuple[str, dict, dict]:
    scenario_id = scenario["id"]
    expectations = scenario.get("expectations", {})

    wait_any = BrokerSimulator(scenario_dir, scenario, mode="wait_any").run()
    wait_all = BrokerSimulator(scenario_dir, scenario, mode="wait_all").run()

    assert_expectations(scenario_id, expectations, wait_any, wait_all)

    speedup_s = wait_all["makespan_s"] - wait_any["makespan_s"]
    print(
        "PASS: "
        f"{scenario_id} "
        f"wait_any={wait_any['makespan_s']}s "
        f"wait_all={wait_all['makespan_s']}s "
        f"speedup={speedup_s}s "
        f"parallel={wait_any['max_parallel']} "
        f"retry={wait_any['retry_count']} "
        f"reuse={wait_any['reuse_count']} "
        f"dedup={wait_any['dedup_merged']} "
        f"lock_conflicts={wait_any['lock_conflicts']} "
        f"dispatch={wait_any['dispatch_count']}"
    )
    return scenario_id, wait_any, wait_all


def run_routing_scenario(scenario_dir: Path, scenario: dict) -> str:
    del scenario_dir

    scenario_id = scenario["id"]
    route_input = scenario.get("route_input", {})
    expectations = scenario.get("expectations", {})

    t_max_s = route_input.get("t_max_s")
    if not isinstance(t_max_s, int) or t_max_s <= 0:
        raise AssertionError(f"{scenario_id}: route_input.t_max_s must be a positive integer")

    t_why = route_input.get("t_why")
    if not isinstance(t_why, str) or not t_why.strip():
        raise AssertionError(f"{scenario_id}: route_input.t_why must be a non-empty string")

    tiny_clear_low_risk = route_input.get("tiny_clear_low_risk")
    if not isinstance(tiny_clear_low_risk, bool):
        raise AssertionError(
            f"{scenario_id}: route_input.tiny_clear_low_risk must be a boolean"
        )

    dispatch_fixture = route_input.get("dispatch_fixture")
    if dispatch_fixture is not None and not isinstance(dispatch_fixture, str):
        raise AssertionError(
            f"{scenario_id}: route_input.dispatch_fixture must be a string or null"
        )

    actual_route = derive_route(
        tiny_clear_low_risk=tiny_clear_low_risk,
        t_max_s=t_max_s,
    )
    expected_route = expectations.get("expected_route")
    if actual_route != expected_route:
        raise AssertionError(
            f"{scenario_id}: expected route {expected_route!r}, got {actual_route!r}"
        )

    if actual_route == "single":
        if dispatch_fixture is not None:
            raise AssertionError(f"{scenario_id}: single route must not reference a dispatch fixture")
        actual_initial_runnable_count = 0
    else:
        if not dispatch_fixture:
            raise AssertionError(f"{scenario_id}: multi route requires route_input.dispatch_fixture")
        dispatches = load_json(E2E_DIR / dispatch_fixture)
        if not isinstance(dispatches, list):
            raise AssertionError(
                f"{scenario_id}: {dispatch_fixture} must be a JSON array when used for routing"
            )
        actual_initial_runnable_count = count_initial_runnable_dispatches(
            dispatches,
            label=f"{scenario_id}: {dispatch_fixture}",
        )

    expected_initial_runnable_count = expectations.get("expected_initial_runnable_count")
    if (
        not isinstance(expected_initial_runnable_count, int)
        or expected_initial_runnable_count < 0
    ):
        raise AssertionError(
            f"{scenario_id}: expectations.expected_initial_runnable_count must be a "
            "non-negative integer"
        )
    if actual_initial_runnable_count != expected_initial_runnable_count:
        raise AssertionError(
            f"{scenario_id}: expected initial_runnable_count={expected_initial_runnable_count}, "
            f"got {actual_initial_runnable_count}"
        )

    print(
        "PASS: "
        f"{scenario_id} "
        f"route={actual_route} "
        f"initial_runnable_count={actual_initial_runnable_count} "
        f"t_max_s={t_max_s} "
        f"tiny_clear_low_risk={str(tiny_clear_low_risk).lower()} "
        f"dispatch_fixture={dispatch_fixture or 'none'}"
    )
    return scenario_id


def assert_negative_regressions() -> None:
    invalid_runner_scope = clone_payload(
        load_json(SCENARIOS_DIR / "swarmbench-01" / "dispatches.initial.json")[0]
    )
    invalid_runner_scope["ownership_paths"] = ["/tmp/swarmbench-01/invalid-runner-scope"]

    assert_rejected(
        lambda: count_initial_runnable_dispatches(
            [invalid_runner_scope],
            label="regression.routing_non_builder_scope",
        ),
        label="regression.routing_non_builder_scope",
        expected_substring="dispatch.ownership_paths",
    )
    print("PASS: regression.routing_non_builder_scope")

    scenario_dir = SCENARIOS_DIR / "swarmbench-01"
    scenario = load_json(scenario_dir / "scenario.json")
    simulator = BrokerSimulator(scenario_dir, scenario, mode="wait_any")
    simulator.initial_dispatches = [invalid_runner_scope]
    assert_rejected(
        simulator.run,
        label="regression.scheduler_non_builder_scope",
        expected_substring="dispatch.ownership_paths",
    )
    print("PASS: regression.scheduler_non_builder_scope")

    invalid_builder_contract = clone_payload(
        load_json(SCENARIOS_DIR / "swarmbench-01" / "dispatches.initial.json")[2]
    )
    del invalid_builder_contract["work_package_id"]
    assert_rejected(
        lambda: count_initial_runnable_dispatches(
            [invalid_builder_contract],
            label="regression.routing_invalid_builder_contract",
        ),
        label="regression.routing_invalid_builder_contract",
        expected_substring="work_package_id",
    )
    print("PASS: regression.routing_invalid_builder_contract")

    invalid_acceptance_type = clone_payload(
        load_json(SCENARIOS_DIR / "swarmbench-01" / "dispatches.initial.json")[0]
    )
    invalid_acceptance_type["task_contract"]["acceptance"] = "oops"
    simulator = BrokerSimulator(scenario_dir, scenario, mode="wait_any")
    simulator.initial_dispatches = [invalid_acceptance_type]
    assert_rejected(
        simulator.run,
        label="regression.scheduler_invalid_acceptance_type",
        expected_substring="task_contract.acceptance",
    )
    print("PASS: regression.scheduler_invalid_acceptance_type")

    invalid_dependencies_type = clone_payload(
        load_json(SCENARIOS_DIR / "swarmbench-01" / "dispatches.initial.json")[0]
    )
    invalid_dependencies_type["dependencies"] = "oops"
    simulator = BrokerSimulator(scenario_dir, scenario, mode="wait_any")
    simulator.initial_dispatches = [invalid_dependencies_type]
    assert_rejected(
        simulator.run,
        label="regression.scheduler_invalid_dependencies_type",
        expected_substring="dispatch.dependencies",
    )
    print("PASS: regression.scheduler_invalid_dependencies_type")

    if derive_route(
        tiny_clear_low_risk=True,
        t_max_s=SINGLE_FAST_PATH_MAX_S + 1,
    ) != "multi":
        raise AssertionError(
            "regression.route_threshold: over-fast-path t_max_s must force route=multi"
        )
    print(
        "PASS: regression.route_threshold "
        f"single fast path capped at {SINGLE_FAST_PATH_MAX_S}s"
    )

    dedup_scenario = load_json(scenario_dir / "scenario.json")
    dedup_simulator = BrokerSimulator(scenario_dir, dedup_scenario, mode="wait_any")
    dedup_base = clone_payload(load_json(scenario_dir / "dispatches.initial.json")[2])
    dedup_copy = clone_payload(dedup_base)
    dedup_base["work_package_id"] = "pkg-dedup-a"
    dedup_copy["slice_id"] = "sb01--builder-long-copy"
    dedup_copy["work_package_id"] = "pkg-dedup-b"
    dedup_simulator.initial_dispatches = [dedup_base, dedup_copy]
    dedup_simulator.durations_s["sb01--builder-long-copy"] = 1
    dedup_result = dedup_simulator.run()
    if dedup_result["status"] != "completed":
        raise AssertionError(
            "regression.work_package_identity: expected completed run, got "
            f"{dedup_result['status']!r}"
        )
    if dedup_result["dedup_merged"] != 0:
        raise AssertionError(
            "regression.work_package_identity: divergent work_package_id values "
            f"must not merge (dedup_merged={dedup_result['dedup_merged']})"
        )
    completed_ids = set(dedup_result["completed_slice_ids"])
    if {"sb01--builder-long", "sb01--builder-long-copy"} - completed_ids:
        raise AssertionError(
            "regression.work_package_identity: both builder slices must complete when "
            "work_package_id differs"
        )
    print("PASS: regression.work_package_identity")

    retry_scenario = load_json(scenario_dir / "scenario.json")
    retry_simulator = BrokerSimulator(scenario_dir, retry_scenario, mode="wait_any")
    retry_simulator.initial_dispatches = [
        clone_payload(load_json(scenario_dir / "dispatches.initial.json")[1])
    ]
    retry_simulator.max_retries_by_agent["runner"] = 0
    retry_result = retry_simulator.run()
    if retry_result["status"] != "blocked":
        raise AssertionError(
            "regression.retry_exhausted: expected blocked run, got "
            f"{retry_result['status']!r}"
        )
    if "retry exhausted" not in (retry_result["blocked_reason"] or ""):
        raise AssertionError(
            "regression.retry_exhausted: blocked_reason must mention retry exhaustion"
        )
    print("PASS: regression.retry_exhausted")

    deadlock_scenario = load_json(scenario_dir / "scenario.json")
    deadlock_simulator = BrokerSimulator(scenario_dir, deadlock_scenario, mode="wait_any")
    deadlock_dispatch = clone_payload(load_json(scenario_dir / "dispatches.initial.json")[0])
    deadlock_dispatch["dependencies"] = ["missing-slice"]
    deadlock_simulator.initial_dispatches = [deadlock_dispatch]
    deadlock_result = deadlock_simulator.run()
    if deadlock_result["status"] != "blocked":
        raise AssertionError(
            "regression.dependency_deadlock: expected blocked run, got "
            f"{deadlock_result['status']!r}"
        )
    if "dependency deadlock" not in (deadlock_result["blocked_reason"] or ""):
        raise AssertionError(
            "regression.dependency_deadlock: blocked_reason must mention dependency deadlock"
        )
    print("PASS: regression.dependency_deadlock")


def main() -> None:
    scenario_dirs = sorted(
        path for path in SCENARIOS_DIR.iterdir() if (path / "scenario.json").exists()
    )
    if not scenario_dirs:
        raise AssertionError(f"No scenario.json files found under {SCENARIOS_DIR}")

    scheduler_results: dict[str, tuple[dict, dict]] = {}
    for scenario_dir in scenario_dirs:
        scenario = load_json(scenario_dir / "scenario.json")
        scenario_kind = scenario.get("kind", "scheduler")
        if scenario_kind == "routing":
            run_routing_scenario(scenario_dir, scenario)
            continue
        if scenario_kind != "scheduler":
            raise AssertionError(f"{scenario['id']}: unsupported scenario kind {scenario_kind!r}")

        scenario_id, wait_any, wait_all = run_scheduler_scenario(scenario_dir, scenario)
        scheduler_results[scenario_id] = (wait_any, wait_all)

    assert_negative_regressions()

    if "swarmbench-02-micro" in scheduler_results and "swarmbench-02-pack" in scheduler_results:
        micro_wait_any = scheduler_results["swarmbench-02-micro"][0]["makespan_s"]
        pack_wait_any = scheduler_results["swarmbench-02-pack"][0]["makespan_s"]
        if (micro_wait_any - pack_wait_any) < 10:
            raise AssertionError(
                "cross-scenario regression failed: "
                f"micro wait_any={micro_wait_any}s should be at least 10s slower than "
                f"pack wait_any={pack_wait_any}s"
            )

    print(f"OK: backtests ({len(scenario_dirs)} scenarios)")


if __name__ == "__main__":
    main()
