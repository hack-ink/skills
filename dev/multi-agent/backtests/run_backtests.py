from __future__ import annotations

from pathlib import Path

from broker_sim import BrokerSimulator, load_json

BACKTESTS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = BACKTESTS_DIR / "scenarios"
E2E_DIR = BACKTESTS_DIR.parent / "e2e"


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
) -> str:
    if tiny_clear_low_risk:
        return "single"
    return "multi"


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
            left_path == right_path
            or left_path.startswith(right_path.rstrip("/") + "/")
            or right_path.startswith(left_path.rstrip("/") + "/")
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
        actual_initial_runnable_count = count_initial_runnable_dispatches(dispatches)

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
