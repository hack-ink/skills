from __future__ import annotations

from pathlib import Path

from broker_sim import BrokerSimulator, load_json

BACKTESTS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = BACKTESTS_DIR / "scenarios"


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
    t_max_s: int,
    decomposable: bool,
    dev_requires_deeper_inspection: bool,
) -> str:
    if not decomposable and (t_max_s > 90 or dev_requires_deeper_inspection):
        return "single-deep"
    if t_max_s <= 90:
        return "single"
    return "multi"


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

    decomposable = route_input.get("decomposable")
    if not isinstance(decomposable, bool):
        raise AssertionError(f"{scenario_id}: route_input.decomposable must be a boolean")

    dev_requires_deeper_inspection = route_input.get("dev_requires_deeper_inspection", False)
    if not isinstance(dev_requires_deeper_inspection, bool):
        raise AssertionError(
            f"{scenario_id}: route_input.dev_requires_deeper_inspection must be a boolean"
        )

    actual_route = derive_route(
        t_max_s=t_max_s,
        decomposable=decomposable,
        dev_requires_deeper_inspection=dev_requires_deeper_inspection,
    )
    expected_route = expectations.get("expected_route")
    if actual_route != expected_route:
        raise AssertionError(
            f"{scenario_id}: expected route {expected_route!r}, got {actual_route!r}"
        )

    actual_spawn_count = 0 if actual_route != "multi" else 1
    expected_spawn_count = expectations.get("expected_spawn_count")
    if not isinstance(expected_spawn_count, int) or expected_spawn_count < 0:
        raise AssertionError(
            f"{scenario_id}: expectations.expected_spawn_count must be a non-negative integer"
        )
    if actual_spawn_count != expected_spawn_count:
        raise AssertionError(
            f"{scenario_id}: expected spawn_count={expected_spawn_count}, got {actual_spawn_count}"
        )

    print(
        "PASS: "
        f"{scenario_id} "
        f"route={actual_route} "
        f"spawn_count={actual_spawn_count} "
        f"t_max_s={t_max_s} "
        f"decomposable={str(decomposable).lower()} "
        f"dev_requires_deeper_inspection={str(dev_requires_deeper_inspection).lower()}"
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
