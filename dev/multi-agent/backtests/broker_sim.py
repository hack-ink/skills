from __future__ import annotations

import dataclasses
import functools
import heapq
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

AGENT_TYPES = ("runner", "builder", "inspector")
TASK_DISPATCH_SCHEMA_ID = "task-dispatch/1"
SKILLS_ROOT = Path(__file__).resolve().parents[3]
TASK_DISPATCH_SCHEMA_PATH = (
    SKILLS_ROOT / "multi-agent" / "schemas" / "task-dispatch.schema.json"
)


@dataclasses.dataclass(order=True)
class InflightItem:
    finish_time: int
    order: int
    slice_id: str = dataclasses.field(compare=False)
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
def task_dispatch_validator() -> Draft202012Validator:
    schema = load_json(TASK_DISPATCH_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def merge_unique(base: list[Any], incoming: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[Any] = set()
    for item in [*base, *incoming]:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def normalize_path(path: str) -> str:
    trimmed = path.rstrip("/")
    return trimmed or "/"


def is_path_overlap(left: str, right: str) -> bool:
    left = normalize_path(left)
    right = normalize_path(right)
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def normalize_ownership_paths(paths: list[str]) -> list[str]:
    return sorted({normalize_path(path) for path in paths})


def assert_dispatch_ownership_semantics(
    payload: dict[str, Any], *, label: str
) -> list[str]:
    ownership_paths = normalize_ownership_paths(payload.get("ownership_paths", []))
    if payload["agent_type"] == "builder":
        if not ownership_paths:
            raise AssertionError(f"{label}: builder slice must declare ownership_paths")
        return ownership_paths
    if ownership_paths:
        raise AssertionError(
            f"{label}: non-builder slices must omit ownership_paths or leave them empty"
        )
    return []


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
        task_dispatch_validator().iter_errors(payload),
        key=_dispatch_validation_sort_key,
    )
    if errors:
        raise AssertionError(f"{label}: {_format_dispatch_validation_error(errors[0])}")

    if not isinstance(payload, dict):
        raise AssertionError(f"{label}: dispatch must be an object")
    return assert_dispatch_ownership_semantics(payload, label=label)


class BrokerSimulator:
    def __init__(self, scenario_dir: Path, scenario: dict[str, Any], mode: str) -> None:
        if mode not in {"wait_any", "wait_all"}:
            raise ValueError(f"Unsupported mode: {mode}")

        self.scenario_dir = scenario_dir
        self.scenario = scenario
        self.mode = mode

        scheduler = scenario["scheduler"]
        self.lane_caps: dict[str, int] = {
            key: int(value)
            for key, value in scheduler["lane_caps"].items()
            if key in AGENT_TYPES
        }
        for agent in AGENT_TYPES:
            self.lane_caps.setdefault(agent, 0)

        self.retry_delay_s = int(scheduler["retry_delay_s"])
        self.max_retries_by_agent: dict[str, int] = {
            key: int(value) for key, value in scheduler["max_retries_by_agent"].items()
        }

        self.durations_s: dict[str, int] = {
            key: int(value) for key, value in scenario["durations_s"].items()
        }
        self.dispatch_overhead_s = int(scenario.get("dispatch_overhead_s", 0))
        self.fail_attempts: dict[str, set[int]] = {
            key: {int(v) for v in values}
            for key, values in scenario.get("fail_attempts", {}).items()
        }

        files = scenario["files"]
        self.initial_dispatches = load_json(self.scenario_dir / files["initial_dispatches"])
        self.handoff_requests_by_slice: dict[str, list[dict[str, Any]]] = {
            slice_id: load_json(self.scenario_dir / relative_path)
            for slice_id, relative_path in files["handoff_requests"].items()
        }

        self.states: dict[str, TicketState] = {}
        self.fingerprint_to_slice: dict[str, str] = {}
        self.aliases: dict[str, str] = {}
        self.inflight: list[InflightItem] = []

        self.time_s = 0
        self.next_added_order = 0
        self.next_inflight_order = 0

        self.retry_count = 0
        self.dedup_merged = 0
        self.lock_conflicts = 0
        self.dispatch_count = 0
        self.max_parallel = 0
        self.completed_order: list[str] = []
        self.events: list[dict[str, Any]] = []
        self.status = "running"
        self.blocked_reason: str | None = None

        self.idle_workers: dict[str, list[str]] = {agent: [] for agent in AGENT_TYPES}
        self.next_worker_index_by_agent: dict[str, int] = {
            agent: 0 for agent in AGENT_TYPES
        }
        self.spawn_count = 0
        self.reuse_count = 0
        self.spawn_count_by_agent: dict[str, int] = {
            agent: 0 for agent in AGENT_TYPES
        }
        self.reuse_count_by_agent: dict[str, int] = {
            agent: 0 for agent in AGENT_TYPES
        }
        self.worker_history_by_slice: dict[str, list[str]] = {}
        self.dispatch_modes_by_slice: dict[str, list[str]] = {}

        self._lock_conflict_keys: set[tuple[int, str]] = set()

    def run(self) -> dict[str, Any]:
        self._enqueue_many(self.initial_dispatches, source="initial")

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
            "dedup_merged": self.dedup_merged,
            "lock_conflicts": self.lock_conflicts,
            "dispatch_count": self.dispatch_count,
            "spawn_count": self.spawn_count,
            "reuse_count": self.reuse_count,
            "spawn_count_by_agent": dict(self.spawn_count_by_agent),
            "reuse_count_by_agent": dict(self.reuse_count_by_agent),
            "worker_history_by_slice": {
                slice_id: list(history)
                for slice_id, history in self.worker_history_by_slice.items()
            },
            "dispatch_modes_by_slice": {
                slice_id: list(modes)
                for slice_id, modes in self.dispatch_modes_by_slice.items()
            },
            "completed_slice_ids": list(self.completed_order),
            "event_count": len(self.events),
        }

    def _all_done(self) -> bool:
        return bool(self.states) and all(s.status == "done" for s in self.states.values())

    def _step_wait_any(self) -> bool:
        if self.inflight:
            item = heapq.heappop(self.inflight)
            self.time_s = item.finish_time
            return self._finish_item(item)

        self._advance_time_or_block()
        return self.status != "blocked"

    def _step_wait_all(self) -> bool:
        if not self.inflight:
            self._advance_time_or_block()
            return self.status != "blocked"

        wave_size = len(self.inflight)
        wave = [heapq.heappop(self.inflight) for _ in range(wave_size)]
        for item in wave:
            self.time_s = item.finish_time
            if not self._finish_item(item):
                return False
        return True

    def _advance_time_or_block(self) -> None:
        pending = [s for s in self.states.values() if s.status == "pending"]
        if not pending:
            raise AssertionError("No inflight workers and no pending tickets before completion")

        future_times = [s.available_at for s in pending if s.available_at > self.time_s]
        if future_times:
            self.time_s = min(future_times)
            return

        dependency_blocked: list[str] = []
        lock_blocked: list[str] = []
        capacity_blocked: list[str] = []
        for state in pending:
            dispatch = state.dispatch
            slice_id = dispatch["slice_id"]
            if not self._dependencies_met(dispatch["dependencies"]):
                dependency_blocked.append(slice_id)
                continue
            if dispatch["agent_type"] == "builder" and self._has_lock_conflict(dispatch):
                lock_blocked.append(slice_id)
                continue
            if self.lane_caps[dispatch["agent_type"]] <= 0:
                capacity_blocked.append(slice_id)
                continue

            raise AssertionError(
                f"Scheduler expected runnable ticket before blocked state: {slice_id}"
            )

        if dependency_blocked:
            reason = "dependency deadlock: " + ", ".join(sorted(dependency_blocked))
        elif lock_blocked:
            reason = "lock deadlock: " + ", ".join(sorted(lock_blocked))
        elif capacity_blocked:
            reason = "lane capacity prevents dispatch: " + ", ".join(
                sorted(capacity_blocked)
            )
        else:
            blocked_ids = [s.dispatch["slice_id"] for s in pending]
            reason = (
                "scheduler blocked with pending tickets and no inflight work: "
                + ", ".join(sorted(blocked_ids))
            )
        self._mark_blocked(reason)

    def _spawn_runnable(self) -> None:
        while True:
            lane_counts = self._lane_counts()
            spawned_any = False

            for state in self._runnable_states():
                dispatch = state.dispatch
                slice_id = dispatch["slice_id"]
                agent_type = dispatch["agent_type"]

                if lane_counts[agent_type] >= self.lane_caps[agent_type]:
                    continue

                if agent_type == "builder" and self._has_lock_conflict(dispatch):
                    conflict_key = (self.time_s, slice_id)
                    if conflict_key not in self._lock_conflict_keys:
                        self._lock_conflict_keys.add(conflict_key)
                        self.lock_conflicts += 1
                    continue

                self._start_ticket(state)
                lane_counts[agent_type] += 1
                spawned_any = True

            if not spawned_any:
                return

    def _runnable_states(self) -> list[TicketState]:
        runnable: list[TicketState] = []
        for state in self.states.values():
            if state.status != "pending":
                continue
            if state.available_at > self.time_s:
                continue

            if not self._dependencies_met(state.dispatch["dependencies"]):
                continue

            runnable.append(state)

        return sorted(
            runnable,
            key=lambda s: (s.available_at, s.added_order, s.dispatch["slice_id"]),
        )

    def _dependencies_met(self, dependencies: list[str]) -> bool:
        for dep in dependencies:
            dep_id = self.aliases.get(dep, dep)
            state = self.states.get(dep_id)
            if state is None or state.status != "done":
                return False
        return True

    def _lane_counts(self) -> dict[str, int]:
        counts = {agent: 0 for agent in AGENT_TYPES}
        for item in self.inflight:
            agent_type = self.states[item.slice_id].dispatch["agent_type"]
            counts[agent_type] += 1
        return counts

    def _has_lock_conflict(self, dispatch: dict[str, Any]) -> bool:
        target_paths = dispatch.get("ownership_paths", [])
        if not target_paths:
            return False

        for item in self.inflight:
            inflight_dispatch = self.states[item.slice_id].dispatch
            if inflight_dispatch["agent_type"] != "builder":
                continue
            for target in target_paths:
                for active in inflight_dispatch.get("ownership_paths", []):
                    if is_path_overlap(target, active):
                        return True
        return False

    def _start_ticket(self, state: TicketState) -> None:
        dispatch = state.dispatch
        slice_id = dispatch["slice_id"]
        agent_type = dispatch["agent_type"]

        duration_s = self.durations_s.get(slice_id)
        if duration_s is None:
            raise AssertionError(f"Missing duration for slice_id={slice_id}")

        worker_id, dispatch_mode = self._acquire_worker(agent_type)
        state.status = "inflight"
        state.attempts += 1
        self.dispatch_count += 1
        self.worker_history_by_slice.setdefault(slice_id, []).append(worker_id)
        self.dispatch_modes_by_slice.setdefault(slice_id, []).append(dispatch_mode)

        self.next_inflight_order += 1
        finish_time = self.time_s + self.dispatch_overhead_s + duration_s
        item = InflightItem(
            finish_time=finish_time,
            order=self.next_inflight_order,
            slice_id=slice_id,
            attempt=state.attempts,
            worker_id=worker_id,
            dispatch_mode=dispatch_mode,
        )
        heapq.heappush(self.inflight, item)

        self.max_parallel = max(self.max_parallel, len(self.inflight))
        self.events.append(
            {
                "t": self.time_s,
                "event": "start",
                "slice_id": slice_id,
                "attempt": state.attempts,
                "worker_id": worker_id,
                "dispatch_mode": dispatch_mode,
                "mode": self.mode,
            }
        )

    def _finish_item(self, item: InflightItem) -> bool:
        state = self.states[item.slice_id]
        dispatch = state.dispatch
        slice_id = dispatch["slice_id"]
        agent_type = dispatch["agent_type"]

        fail_attempts = self.fail_attempts.get(slice_id, set())
        if item.attempt in fail_attempts:
            max_retries = self.max_retries_by_agent.get(agent_type, 0)
            if state.retries >= max_retries:
                state.status = "blocked"
                self._mark_blocked(
                    f"retry exhausted: {slice_id} at attempt {item.attempt}"
                )
                return False

            state.retries += 1
            state.status = "pending"
            state.available_at = self.time_s + self.retry_delay_s
            self.retry_count += 1
            self._release_worker(agent_type, item.worker_id)
            self.events.append(
                {
                    "t": self.time_s,
                    "event": "retry",
                    "slice_id": slice_id,
                    "attempt": item.attempt,
                    "worker_id": item.worker_id,
                    "next_available_at": state.available_at,
                    "mode": self.mode,
                }
            )
            return True

        state.status = "done"
        state.available_at = self.time_s
        self.completed_order.append(slice_id)
        self._release_worker(agent_type, item.worker_id)
        self.events.append(
            {
                "t": self.time_s,
                "event": "done",
                "slice_id": slice_id,
                "attempt": item.attempt,
                "worker_id": item.worker_id,
                "mode": self.mode,
            }
        )

        handoff_payloads = self.handoff_requests_by_slice.get(slice_id, [])
        if handoff_payloads:
            self._enqueue_many(handoff_payloads, source=slice_id)
        return True

    def _acquire_worker(self, agent_type: str) -> tuple[str, str]:
        idle_workers = self.idle_workers[agent_type]
        if idle_workers:
            worker_id = idle_workers.pop(0)
            self.reuse_count += 1
            self.reuse_count_by_agent[agent_type] += 1
            return worker_id, "reuse"

        self.next_worker_index_by_agent[agent_type] += 1
        worker_id = f"{agent_type}-w{self.next_worker_index_by_agent[agent_type]}"
        self.spawn_count += 1
        self.spawn_count_by_agent[agent_type] += 1
        return worker_id, "spawn"

    def _release_worker(self, agent_type: str, worker_id: str) -> None:
        if worker_id in self.idle_workers[agent_type]:
            return
        self.idle_workers[agent_type].append(worker_id)

    def _mark_blocked(self, reason: str) -> None:
        if self.status == "blocked":
            return
        self.status = "blocked"
        self.blocked_reason = reason
        self.events.append(
            {
                "t": self.time_s,
                "event": "blocked",
                "reason": reason,
                "mode": self.mode,
            }
        )

    def _enqueue_many(self, payloads: list[dict[str, Any]], source: str) -> None:
        if not isinstance(payloads, list):
            raise AssertionError(f"{source}: expected list of dispatch payloads")
        for payload in payloads:
            self._enqueue_one(payload, source=source)

    def _enqueue_one(self, payload: dict[str, Any], source: str) -> None:
        dispatch = self._normalize_dispatch(payload)
        raw_slice_id = dispatch["slice_id"]
        slice_id = self.aliases.get(raw_slice_id, raw_slice_id)
        dispatch["slice_id"] = slice_id

        current = self.states.get(slice_id)
        if current is not None:
            self._assert_merge_compatible(current.dispatch, dispatch, source=source)
            self._merge_additive_fields(current.dispatch, dispatch)
            self.dedup_merged += 1
            return

        fingerprint = self._fingerprint(dispatch)
        if fingerprint in self.fingerprint_to_slice:
            canonical_id = self.fingerprint_to_slice[fingerprint]
            canonical = self.states[canonical_id]
            self._assert_merge_compatible(canonical.dispatch, dispatch, source=source)
            self._merge_additive_fields(canonical.dispatch, dispatch)
            if raw_slice_id != canonical_id:
                self.aliases[raw_slice_id] = canonical_id
                self._rewrite_dependencies(raw_slice_id, canonical_id)
            self.dedup_merged += 1
            return

        state = TicketState(
            dispatch=dispatch,
            added_order=self.next_added_order,
            status="pending",
            attempts=0,
            retries=0,
            available_at=0,
        )
        self.next_added_order += 1

        self.states[slice_id] = state
        self.fingerprint_to_slice[fingerprint] = slice_id

    def _normalize_dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert_dispatch_contract(payload, label=f"dispatch {payload.get('slice_id', '<unknown>')}")

        dispatch = json.loads(json.dumps(payload))
        dispatch.setdefault("slice_kind", "work")

        dispatch["ownership_paths"] = normalize_ownership_paths(
            dispatch.get("ownership_paths", [])
        )

        deps = [self.aliases.get(dep, dep) for dep in dispatch.get("dependencies", [])]
        dispatch["dependencies"] = sorted(set(deps))

        contract = dispatch.get("task_contract")
        for key in ("acceptance", "constraints"):
            contract[key] = merge_unique(contract.get(key, []), [])
        dispatch["task_contract"] = contract

        dispatch["evidence_requirements"] = merge_unique(
            dispatch.get("evidence_requirements", []),
            [],
        )

        return dispatch

    def _assert_merge_compatible(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
        *,
        source: str,
    ) -> None:
        keys = [
            "schema",
            "ssot_id",
            "task_id",
            "agent_type",
            "slice_kind",
            "work_package_id",
            "timebox_minutes",
            "ownership_paths",
        ]
        for key in keys:
            if current.get(key) != incoming.get(key):
                raise AssertionError(
                    f"{source}: cannot merge divergent field {key!r} for {current['slice_id']}"
                )

    def _merge_additive_fields(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
    ) -> None:
        current["dependencies"] = merge_unique(
            current.get("dependencies", []), incoming.get("dependencies", [])
        )
        current["dependencies"] = sorted({self.aliases.get(d, d) for d in current["dependencies"]})

        current_contract = current.setdefault("task_contract", {})
        incoming_contract = incoming.get("task_contract", {})

        if (
            current_contract.get("goal")
            and incoming_contract.get("goal")
            and current_contract["goal"] != incoming_contract["goal"]
        ):
            raise AssertionError(
                f"Divergent task_contract.goal for {current['slice_id']} during dedup merge"
            )

        for key in ("acceptance", "constraints"):
            current_contract[key] = merge_unique(
                current_contract.get(key, []), incoming_contract.get(key, [])
            )

        current["evidence_requirements"] = merge_unique(
            current.get("evidence_requirements", []),
            incoming.get("evidence_requirements", []),
        )

    def _rewrite_dependencies(self, alias_id: str, canonical_id: str) -> None:
        for state in self.states.values():
            deps = [canonical_id if dep == alias_id else dep for dep in state.dispatch["dependencies"]]
            state.dispatch["dependencies"] = sorted(set(deps))

    def _fingerprint(self, dispatch: dict[str, Any]) -> str:
        payload = {
            "schema": dispatch["schema"],
            "ssot_id": dispatch["ssot_id"],
            "task_id": dispatch["task_id"],
            "agent_type": dispatch["agent_type"],
            "slice_kind": dispatch["slice_kind"],
            "work_package_id": dispatch.get("work_package_id"),
            "dependencies": dispatch["dependencies"],
            "ownership_paths": dispatch["ownership_paths"],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
