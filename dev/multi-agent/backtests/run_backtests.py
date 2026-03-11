from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from broker_sim import BrokerSimulator, assert_dispatch_contract, load_json

BACKTESTS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = BACKTESTS_DIR / "scenarios"
SINGLE_FAST_PATH_MAX_S = 90


def derive_route(*, tiny_clear_low_risk: bool, t_max_s: int) -> str:
    if tiny_clear_low_risk and t_max_s <= SINGLE_FAST_PATH_MAX_S:
        return "single"
    return "multi"


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


def assert_expectations(
    scenario_id: str,
    expectations: dict[str, Any],
    wait_any: dict[str, Any],
    wait_all: dict[str, Any],
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

    min_reuse_count_by_role = expectations.get("min_reuse_count_by_role", {})
    for role, minimum in min_reuse_count_by_role.items():
        actual = wait_any["reuse_count_by_role"].get(role)
        if actual is None:
            raise AssertionError(
                f"{scenario_id}: missing reuse_count_by_role entry for {role!r}"
            )
        if actual < int(minimum):
            raise AssertionError(
                f"{scenario_id}: reuse_count_by_role[{role!r}]={actual} < {minimum}"
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

    expected_ids = expectations.get("expected_completed_ticket_ids")
    if expected_ids is not None:
        actual = sorted(set(wait_any["completed_ticket_ids"]))
        expected = sorted(set(expected_ids))
        if actual != expected:
            raise AssertionError(
                f"{scenario_id}: completed tickets mismatch: expected={expected}, got={actual}"
            )

    expected_terminal_status = expectations.get("expected_terminal_status_by_ticket", {})
    for ticket_id, expected_status in expected_terminal_status.items():
        actual_status = wait_any["completed_status_by_ticket"].get(ticket_id)
        if actual_status != expected_status:
            raise AssertionError(
                f"{scenario_id}: completed_status_by_ticket[{ticket_id!r}]={actual_status!r} != {expected_status!r}"
            )

    for index, pair in enumerate(expectations.get("must_start_after_done", []), 1):
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(value, str) and value for value in pair)
        ):
            raise AssertionError(
                f"{scenario_id}: must_start_after_done[{index}] must be [start_ticket_id, completed_ticket_id]"
            )
        start_ticket_id, completed_ticket_id = pair
        start_index, start_t = find_event_position_and_time(
            wait_any["events"],
            ticket_id=start_ticket_id,
            event_name="start",
            scenario_id=scenario_id,
        )
        done_index, done_t = find_event_position_and_time(
            wait_any["events"],
            ticket_id=completed_ticket_id,
            event_name="done",
            scenario_id=scenario_id,
        )
        if start_t < done_t or (start_t == done_t and start_index <= done_index):
            raise AssertionError(
                f"{scenario_id}: expected {start_ticket_id} to start after {completed_ticket_id} completed"
            )


def find_event_position_and_time(
    events: list[dict[str, Any]],
    *,
    ticket_id: str,
    event_name: str,
    scenario_id: str,
) -> tuple[int, int]:
    for index, event in enumerate(events):
        if event.get("event") == event_name and event.get("ticket_id") == ticket_id:
            timestamp = event.get("t")
            if not isinstance(timestamp, int):
                raise AssertionError(
                    f"{scenario_id}: event {event_name!r} for {ticket_id!r} must have integer t"
                )
            return index, timestamp
    raise AssertionError(
        f"{scenario_id}: missing event {event_name!r} for ticket_id={ticket_id!r}"
    )


def assert_ticket_dependencies(tickets: list[dict[str, Any]], *, label: str) -> None:
    ticket_ids = {ticket["ticket_id"] for ticket in tickets}
    for ticket in tickets:
        for dependency in ticket.get("depends_on", []):
            if dependency not in ticket_ids:
                raise AssertionError(
                    f"{label}: {ticket['ticket_id']} depends on missing ticket_id {dependency!r}"
                )


def iter_scenarios() -> list[tuple[str, dict[str, Any]]]:
    scenarios: list[tuple[str, dict[str, Any]]] = []
    for scenario_path in sorted(SCENARIOS_DIR.rglob("scenario.json")):
        scenario = load_json(scenario_path)
        scenario_id = str(scenario_path.parent.relative_to(SCENARIOS_DIR))
        scenarios.append((scenario_id, scenario))
    if not scenarios:
        raise AssertionError(f"No scenario.json files found under {SCENARIOS_DIR}")
    return scenarios


def assert_schema_regressions() -> None:
    builder_valid = {
        "schema": "ticket-dispatch/1",
        "run_id": "regression",
        "ticket_id": "builder-write",
        "role": "builder",
        "objective": "Edit the owned scope.",
        "acceptance": ["Owned paths only."],
        "timebox_minutes": 10,
        "write_scope": ["src/app/"],
    }
    assert_dispatch_contract(builder_valid, label="regression.builder_valid")

    invalid_builder = json.loads(json.dumps(builder_valid))
    del invalid_builder["write_scope"]
    assert_rejected(
        lambda: assert_dispatch_contract(
            invalid_builder, label="regression.builder_missing_write_scope"
        ),
        label="regression.builder_missing_write_scope",
        expected_substring="write_scope",
    )

    invalid_runner = {
        "schema": "ticket-dispatch/1",
        "run_id": "regression",
        "ticket_id": "runner-bad-scope",
        "role": "runner",
        "objective": "Read the repo.",
        "acceptance": ["No writes."],
        "timebox_minutes": 5,
        "write_scope": ["src/app/"],
    }
    assert_rejected(
        lambda: assert_dispatch_contract(
            invalid_runner, label="regression.runner_write_scope"
        ),
        label="regression.runner_write_scope",
        expected_substring="write_scope",
    )

    print("PASS: regression.dispatch_contract")


def main() -> None:
    assert_schema_regressions()

    for scenario_id, scenario in iter_scenarios():
        route_case = scenario["route_case"]
        derived_route = derive_route(
            tiny_clear_low_risk=bool(route_case["tiny_clear_low_risk"]),
            t_max_s=int(route_case["t_max_s"]),
        )
        expected_route = route_case["expected_route"]
        if derived_route != expected_route:
            raise AssertionError(
                f"{scenario_id}: derived route {derived_route!r} != {expected_route!r}"
            )

        tickets = scenario.get("tickets", [])
        if expected_route == "single":
            if tickets:
                raise AssertionError(
                    f"{scenario_id}: single-route scenarios must not define broker tickets"
                )
            print(f"PASS: {scenario_id} (single)")
            continue

        if not tickets:
            raise AssertionError(f"{scenario_id}: multi scenario must define tickets")
        for index, ticket in enumerate(tickets, 1):
            assert_dispatch_contract(ticket, label=f"{scenario_id}.tickets[{index}]")
        assert_ticket_dependencies(tickets, label=scenario_id)

        wait_any = BrokerSimulator(scenario, mode="wait_any").run()
        wait_all = BrokerSimulator(scenario, mode="wait_all").run()
        if wait_any["status"] not in {"completed", "blocked"}:
            raise AssertionError(
                f"{scenario_id}: unexpected wait_any status {wait_any['status']!r}"
            )
        if wait_all["status"] not in {"completed", "blocked"}:
            raise AssertionError(
                f"{scenario_id}: unexpected wait_all status {wait_all['status']!r}"
            )
        assert_expectations(
            scenario_id,
            scenario.get("expectations", {}),
            wait_any,
            wait_all,
        )
        print(
            f"PASS: {scenario_id} "
            f"(wait_any={wait_any['makespan_s']}s, wait_all={wait_all['makespan_s']}s)"
        )

    print("OK: deterministic backtests cover the reset protocol")


if __name__ == "__main__":
    main()
