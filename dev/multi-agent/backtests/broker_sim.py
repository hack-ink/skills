from __future__ import annotations

import dataclasses
import functools
import heapq
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROLES = ("runner", "builder", "inspector")
DISPATCH_SCHEMA_ID = "ticket-dispatch/1"
SKILLS_ROOT = Path(__file__).resolve().parents[3]
DISPATCH_SCHEMA_PATH = (
    SKILLS_ROOT / "multi-agent" / "schemas" / "ticket-dispatch.schema.json"
)


@dataclasses.dataclass(order=True)
class InflightItem:
    finish_time: int
    order: int
    ticket_id: str = dataclasses.field(compare=False)
    attempt: int = dataclasses.field(compare=False)
    worker_id: str = dataclasses.field(compare=False)
    dispatch_mode: str = dataclasses.field(compare=False)


@dataclasses.dataclass
class TicketState:
    dispatch: dict[str, Any]
    added_order: int
    status: str = "pending"
    attempts: int = 0
    retries: int = 0
    available_at: int = 0


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


@functools.lru_cache(maxsize=1)
def dispatch_validator() -> Draft202012Validator:
    schema = load_json(DISPATCH_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def normalize_path(path: str) -> str:
    trimmed = path.rstrip("/")
    return trimmed or "/"


def is_path_overlap(left: str, right: str) -> bool:
    left = normalize_path(left)
    right = normalize_path(right)
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def normalize_write_scope(paths: list[str]) -> list[str]:
    return sorted({normalize_path(path) for path in paths})


def _dispatch_validation_sort_key(error: ValidationError) -> tuple[Any, ...]:
    return (
        tuple(str(part) for part in error.absolute_path),
        tuple(str(part) for part in error.absolute_schema_path),
        error.message,
    )


def _format_dispatch_validation_error(error: ValidationError) -> str:
    location = "dispatch"
    for part in error.absolute_path:
        if isinstance(part, int):
            location += f"[{part}]"
        else:
            location += f".{part}"
    return f"{location}: {error.message}"


def assert_dispatch_contract(payload: dict[str, Any], *, label: str) -> list[str]:
    errors = sorted(
        dispatch_validator().iter_errors(payload),
        key=_dispatch_validation_sort_key,
    )
    if errors:
        raise AssertionError(f"{label}: {_format_dispatch_validation_error(errors[0])}")

    if not isinstance(payload, dict):
        raise AssertionError(f"{label}: dispatch must be an object")

    write_scope = normalize_write_scope(payload.get("write_scope", []))
    if payload["role"] == "builder":
        if not write_scope:
            raise AssertionError(f"{label}: builder ticket must declare write_scope")
        return write_scope

    if write_scope:
        raise AssertionError(
            f"{label}: non-builder tickets must omit write_scope or leave it empty"
        )
    return []


class BrokerSimulator:
    def __init__(self, scenario: dict[str, Any], mode: str) -> None:
        if mode not in {"wait_any", "wait_all"}:
            raise ValueError(f"Unsupported mode: {mode}")

        self.scenario = scenario
        self.mode = mode

        scheduler = scenario["scheduler"]
        self.lane_caps: dict[str, int] = {
            role: int(scheduler["lane_caps"].get(role, 0)) for role in ROLES
        }
        self.retry_delay_s = int(scheduler.get("retry_delay_s", 0))
        self.max_retries_by_role: dict[str, int] = {
            role: int(scheduler.get("max_retries_by_role", {}).get(role, 0))
            for role in ROLES
        }

        self.durations_s: dict[str, int] = {
            ticket_id: int(value)
            for ticket_id, value in scenario.get("durations_s", {}).items()
        }
        self.dispatch_overhead_s = int(scenario.get("dispatch_overhead_s", 0))
        self.fail_attempts: dict[str, set[int]] = {
            ticket_id: {int(value) for value in attempts}
            for ticket_id, attempts in scenario.get("fail_attempts", {}).items()
        }
        self.terminal_status_by_ticket: dict[str, str] = {}
        for ticket_id, status in scenario.get("terminal_status_by_ticket", {}).items():
            if status not in {"done", "blocked"}:
                raise AssertionError(
                    f"Unsupported terminal status for {ticket_id!r}: {status!r}"
                )
            self.terminal_status_by_ticket[ticket_id] = status

        self.states: dict[str, TicketState] = {}
        self.inflight: list[InflightItem] = []
        self.time_s = 0
        self.next_added_order = 0
        self.next_inflight_order = 0

        self.retry_count = 0
        self.lock_conflicts = 0
        self.dispatch_count = 0
        self.max_parallel = 0
        self.completed_order: list[str] = []
        self.events: list[dict[str, Any]] = []
        self.status = "running"
        self.blocked_reason: str | None = None

        self.idle_workers: dict[str, list[str]] = {role: [] for role in ROLES}
        self.next_worker_index_by_role: dict[str, int] = {role: 0 for role in ROLES}
        self.spawn_count = 0
        self.reuse_count = 0
        self.spawn_count_by_role: dict[str, int] = {role: 0 for role in ROLES}
        self.reuse_count_by_role: dict[str, int] = {role: 0 for role in ROLES}
        self.dispatch_modes_by_ticket: dict[str, list[str]] = {}

        self._lock_conflict_keys: set[tuple[int, str]] = set()

        self._enqueue_many(scenario.get("tickets", []), source="initial")

    def run(self) -> dict[str, Any]:
        while self.status == "running":
            self._spawn_runnable()

            if self._all_done():
                self.status = "completed"
                break

            if self.mode == "wait_any":
                if not self._step_wait_any():
                    break
            else:
                if not self._step_wait_all():
                    break

        return {
            "mode": self.mode,
            "status": self.status,
            "blocked_reason": self.blocked_reason,
            "makespan_s": self.time_s,
            "max_parallel": self.max_parallel,
            "retry_count": self.retry_count,
            "lock_conflicts": self.lock_conflicts,
            "dispatch_count": self.dispatch_count,
            "spawn_count": self.spawn_count,
            "reuse_count": self.reuse_count,
            "spawn_count_by_role": dict(self.spawn_count_by_role),
            "reuse_count_by_role": dict(self.reuse_count_by_role),
            "dispatch_modes_by_ticket": {
                ticket_id: list(modes)
                for ticket_id, modes in self.dispatch_modes_by_ticket.items()
            },
            "completed_ticket_ids": list(self.completed_order),
            "completed_status_by_ticket": {
                ticket_id: state.status
                for ticket_id, state in self.states.items()
                if self._is_terminal_state(state.status)
            },
            "events": list(self.events),
        }

    def _all_done(self) -> bool:
        return bool(self.states) and all(
            self._is_terminal_state(state.status) for state in self.states.values()
        )

    def _step_wait_any(self) -> bool:
        if not self.inflight:
            return self._mark_blocked_if_stuck()

        item = heapq.heappop(self.inflight)
        self.time_s = max(self.time_s, item.finish_time)
        self._finish_item(item)
        return True

    def _step_wait_all(self) -> bool:
        if not self.inflight:
            return self._mark_blocked_if_stuck()

        current_wave: list[InflightItem] = []
        while self.inflight:
            current_wave.append(heapq.heappop(self.inflight))

        for item in current_wave:
            self.time_s = max(self.time_s, item.finish_time)
            self._finish_item(item)
        return True

    def _mark_blocked_if_stuck(self) -> bool:
        pending_states = [
            state for state in self.states.values() if state.status == "pending"
        ]
        if pending_states:
            next_available_at = min(state.available_at for state in pending_states)
            if next_available_at > self.time_s:
                self.time_s = next_available_at
                return True

            pending = [state.dispatch["ticket_id"] for state in pending_states]
            self.status = "blocked"
            self.blocked_reason = f"no runnable tickets: {', '.join(sorted(pending))}"
            return False

        self.status = "completed"
        return False

    def _spawn_runnable(self) -> None:
        lane_counts = self._current_lane_counts()

        while True:
            started = False
            for state in self._pending_states():
                dispatch = state.dispatch
                ticket_id = dispatch["ticket_id"]
                role = dispatch["role"]

                if state.available_at > self.time_s:
                    continue
                if lane_counts[role] >= self.lane_caps[role]:
                    continue
                if not self._dependencies_satisfied(dispatch):
                    continue
                if role == "builder" and self._has_lock_conflict(dispatch):
                    conflict_key = (self.time_s, ticket_id)
                    if conflict_key not in self._lock_conflict_keys:
                        self.lock_conflicts += 1
                        self._lock_conflict_keys.add(conflict_key)
                    continue

                lane_counts[role] += 1
                started = True
                self._start_ticket(state)

            if not started:
                break

    def _pending_states(self) -> list[TicketState]:
        return sorted(
            (state for state in self.states.values() if state.status == "pending"),
            key=lambda state: (
                state.available_at,
                state.added_order,
                state.dispatch["ticket_id"],
            ),
        )

    def _current_lane_counts(self) -> dict[str, int]:
        counts = {role: 0 for role in ROLES}
        for item in self.inflight:
            role = self.states[item.ticket_id].dispatch["role"]
            counts[role] += 1
        return counts

    def _dependencies_satisfied(self, dispatch: dict[str, Any]) -> bool:
        for dependency in dispatch.get("depends_on", []):
            dependency_state = self.states.get(dependency)
            if dependency_state is None or dependency_state.status != "done":
                return False
        return True

    def _has_lock_conflict(self, dispatch: dict[str, Any]) -> bool:
        candidate_scope = normalize_write_scope(dispatch.get("write_scope", []))
        if not candidate_scope:
            return False

        for item in self.inflight:
            inflight_dispatch = self.states[item.ticket_id].dispatch
            if inflight_dispatch["role"] != "builder":
                continue
            inflight_scope = normalize_write_scope(inflight_dispatch.get("write_scope", []))
            for left in candidate_scope:
                for right in inflight_scope:
                    if is_path_overlap(left, right):
                        return True
        return False

    def _start_ticket(self, state: TicketState) -> None:
        dispatch = state.dispatch
        ticket_id = dispatch["ticket_id"]
        role = dispatch["role"]
        duration_s = self.durations_s.get(ticket_id)
        if duration_s is None:
            raise AssertionError(f"Missing duration for ticket_id={ticket_id!r}")

        worker_id, dispatch_mode = self._acquire_worker(role)
        state.status = "running"
        state.attempts += 1

        self.dispatch_count += 1
        self.dispatch_modes_by_ticket.setdefault(ticket_id, []).append(dispatch_mode)

        finish_time = self.time_s + self.dispatch_overhead_s + duration_s
        heapq.heappush(
            self.inflight,
            InflightItem(
                finish_time=finish_time,
                order=self.next_inflight_order,
                ticket_id=ticket_id,
                attempt=state.attempts,
                worker_id=worker_id,
                dispatch_mode=dispatch_mode,
            ),
        )
        self.next_inflight_order += 1
        self.max_parallel = max(self.max_parallel, len(self.inflight))
        self.events.append(
            {
                "event": "start",
                "ticket_id": ticket_id,
                "role": role,
                "worker_id": worker_id,
                "dispatch_mode": dispatch_mode,
                "t": self.time_s,
            }
        )

    def _finish_item(self, item: InflightItem) -> None:
        state = self.states[item.ticket_id]
        dispatch = state.dispatch
        role = dispatch["role"]
        failed_attempts = self.fail_attempts.get(item.ticket_id, set())

        if item.attempt in failed_attempts:
            max_retries = self.max_retries_by_role.get(role, 0)
            if state.retries < max_retries:
                state.status = "pending"
                state.retries += 1
                state.available_at = self.time_s + self.retry_delay_s
                self.retry_count += 1
                self._release_worker(role, item.worker_id)
                self.events.append(
                    {
                        "event": "retry",
                        "ticket_id": item.ticket_id,
                        "role": role,
                        "worker_id": item.worker_id,
                        "t": self.time_s,
                    }
                )
                return

            state.status = self.terminal_status_by_ticket.get(item.ticket_id, "blocked")
            self.completed_order.append(item.ticket_id)
            self._release_worker(role, item.worker_id)
            self.events.append(
                {
                    "event": "blocked",
                    "ticket_id": item.ticket_id,
                    "role": role,
                    "worker_id": item.worker_id,
                    "t": self.time_s,
                }
            )
            return

        state.status = self.terminal_status_by_ticket.get(item.ticket_id, "done")
        self.completed_order.append(item.ticket_id)
        self._release_worker(role, item.worker_id)
        self.events.append(
            {
                "event": "done",
                "ticket_id": item.ticket_id,
                "role": role,
                "worker_id": item.worker_id,
                "t": self.time_s,
            }
        )

    def _acquire_worker(self, role: str) -> tuple[str, str]:
        idle = self.idle_workers[role]
        if idle:
            worker_id = idle.pop(0)
            self.reuse_count += 1
            self.reuse_count_by_role[role] += 1
            return worker_id, "reuse"

        self.next_worker_index_by_role[role] += 1
        worker_id = f"{role}-w{self.next_worker_index_by_role[role]}"
        self.spawn_count += 1
        self.spawn_count_by_role[role] += 1
        return worker_id, "spawn"

    def _release_worker(self, role: str, worker_id: str) -> None:
        if worker_id in self.idle_workers[role]:
            return
        self.idle_workers[role].append(worker_id)

    def _enqueue_many(self, tickets: list[dict[str, Any]], *, source: str) -> None:
        for index, ticket in enumerate(tickets, 1):
            if not isinstance(ticket, dict):
                raise AssertionError(f"{source}[{index}]: ticket must be an object")

            assert_dispatch_contract(
                ticket,
                label=f"{source}.{ticket.get('ticket_id', f'ticket[{index}]')}",
            )

            ticket_id = ticket["ticket_id"]
            if ticket_id in self.states:
                raise AssertionError(f"{source}: duplicate ticket_id {ticket_id!r}")

            self.states[ticket_id] = TicketState(
                dispatch=json.loads(json.dumps(ticket)),
                added_order=self.next_added_order,
            )
            self.next_added_order += 1

    @staticmethod
    def _is_terminal_state(status: str) -> bool:
        return status in {"done", "blocked"}
