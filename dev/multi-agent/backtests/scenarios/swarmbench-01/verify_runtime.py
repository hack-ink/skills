from __future__ import annotations

import copy
import sys
from pathlib import Path

SCENARIO_DIR = Path(__file__).resolve().parent
BACKTESTS_DIR = SCENARIO_DIR.parents[1]
if str(BACKTESTS_DIR) not in sys.path:
    sys.path.insert(0, str(BACKTESTS_DIR))

from broker_sim import BrokerSimulator, load_json  # noqa: E402
from run_backtests import assert_expectations  # noqa: E402

SCENARIO_FILE = SCENARIO_DIR / "scenario.json"
INITIAL_FILE = SCENARIO_DIR / "dispatches.initial.json"
RUNTIME_FILE = SCENARIO_DIR / "dispatches.runtime.json"


def build_runtime_scenario() -> dict:
    scenario = copy.deepcopy(load_json(SCENARIO_FILE))
    scenario["files"]["initial_dispatches"] = RUNTIME_FILE.name
    return scenario


def assert_runtime_dispatches_match_initial() -> None:
    initial = load_json(INITIAL_FILE)
    runtime = load_json(RUNTIME_FILE)
    initial_ids = [dispatch["slice_id"] for dispatch in initial]
    runtime_ids = [dispatch["slice_id"] for dispatch in runtime]
    if runtime_ids != initial_ids:
        raise AssertionError(
            "dispatches.runtime.json must preserve initial slice order; "
            f"expected={initial_ids}, got={runtime_ids}"
        )


def assert_runtime_replay_passes() -> None:
    runtime_scenario = build_runtime_scenario()
    wait_any = BrokerSimulator(SCENARIO_DIR, runtime_scenario, mode="wait_any").run()
    wait_all = BrokerSimulator(SCENARIO_DIR, runtime_scenario, mode="wait_all").run()
    assert_expectations(runtime_scenario["id"], runtime_scenario["expectations"], wait_any, wait_all)
    short_worker_ids = wait_any["worker_history_by_slice"].get("sb01--builder-short", [])
    after_short_worker_ids = wait_any["worker_history_by_slice"].get(
        "sb01--builder-after-short", []
    )
    if short_worker_ids[:1] != after_short_worker_ids[:1]:
        raise AssertionError(
            "after_short should reuse the warm worker released by builder-short; "
            f"short={short_worker_ids}, after_short={after_short_worker_ids}"
        )
    after_short_modes = wait_any["dispatch_modes_by_slice"].get("sb01--builder-after-short", [])
    if after_short_modes[:1] != ["reuse"]:
        raise AssertionError(
            "after_short should dispatch via reuse-first warm-worker assignment; "
            f"got {after_short_modes}"
        )


def assert_timebox_mismatch_is_rejected() -> None:
    runtime_scenario = build_runtime_scenario()
    simulator = BrokerSimulator(SCENARIO_DIR, runtime_scenario, mode="wait_any")
    requests = simulator.handoff_requests_by_slice.get("sb01--runner-map", [])
    if len(requests) < 2:
        raise AssertionError("Expected duplicate lock-a handoff requests for dedup checks")

    divergent = copy.deepcopy(requests[1])
    divergent["timebox_minutes"] = int(divergent["timebox_minutes"]) + 1
    simulator.handoff_requests_by_slice["sb01--runner-map"][1] = divergent

    try:
        simulator.run()
    except AssertionError as exc:
        if "timebox_minutes" not in str(exc):
            raise AssertionError(
                "Expected timebox divergence failure during dedup merge, got: "
                + str(exc)
            ) from exc
        return

    raise AssertionError("Expected timebox mismatch to fail dedup merge, but run succeeded")


def main() -> None:
    assert_runtime_dispatches_match_initial()
    assert_runtime_replay_passes()
    assert_timebox_mismatch_is_rejected()
    print("OK: runtime replay + timebox mismatch guard")


if __name__ == "__main__":
    main()
