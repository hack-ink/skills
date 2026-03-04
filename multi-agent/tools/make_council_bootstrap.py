#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys


SCENARIO_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def make_ssot_id(scenario: str, hex_len: int = 12) -> str:
    scenario = scenario.strip()
    if not SCENARIO_RE.fullmatch(scenario):
        raise ValueError(
            "scenario must be ASCII kebab-case, e.g. 'pack-configs-pubfi-cli'"
        )
    if hex_len < 8 or hex_len > 64:
        raise ValueError("--hex-len must be 8..64")
    token = hashlib.sha256(scenario.encode("utf-8")).hexdigest()[:hex_len]
    return f"{scenario}-{token}"


def make_dispatch(
    *,
    ssot_id: str,
    task_id: str,
    slice_id: str,
    agent_type: str,
    slice_kind: str,
    timebox_minutes: int,
    dependencies: list[str] | None = None,
    goal: str,
    acceptance: list[str],
    constraints: list[str],
    evidence_requirements: list[str],
    allowed_paths: list[str] | None = None,
    ownership_paths: list[str] | None = None,
) -> dict:
    return {
        "schema": "task-dispatch/1",
        "ssot_id": ssot_id,
        "task_id": task_id,
        "slice_id": slice_id,
        "agent_type": agent_type,
        "slice_kind": slice_kind,
        "timebox_minutes": timebox_minutes,
        "allowed_paths": allowed_paths or [],
        "ownership_paths": ownership_paths or [],
        "dependencies": dependencies or [],
        "task_contract": {
            "goal": goal,
            "acceptance": acceptance,
            "constraints": constraints,
            "no_touch": [],
        },
        "evidence_requirements": evidence_requirements,
    }


def build_council_bootstrap(
    scenario: str,
    task_id: str,
    supervisor_count: int,
    depend_on_supervisors: bool,
    include_auditor: bool,
    include_operator_mapper: bool,
    supervisor_timebox: int,
    operator_timebox: int,
    auditor_timebox: int,
    hex_len: int,
) -> list[dict]:
    ssot_id = make_ssot_id(scenario, hex_len=hex_len)
    prefix = f"{scenario}-council"
    dispatches: list[dict] = []
    supervisor_ids = [f"{prefix}-supervisor-{i:02d}" for i in range(1, supervisor_count + 1)]
    operator_auditor_dependencies = (
        supervisor_ids if depend_on_supervisors else []
    )

    for i in range(1, supervisor_count + 1):
        dispatches.append(
            make_dispatch(
                ssot_id=ssot_id,
                task_id=task_id,
                slice_id=f"{prefix}-supervisor-{i:02d}",
                agent_type="supervisor",
                slice_kind="work",
                timebox_minutes=supervisor_timebox,
                goal=(
                    f"Draft a supervisor plan for the overall task stream {task_id}, "
                    f"including write ownership boundaries and dependencies."
                ),
                acceptance=[
                    "Emit a dispatch plan in task-dispatch/1 format.",
                    "Set disjoint ownership for all write slices in the returned plan.",
                    "Express critical dependencies and blockers clearly.",
                ],
                constraints=[
                    "Read-only planning for the given scenario.",
                    "No repo writes.",
                    "Keep role and action scope within task contracts.",
                ],
                evidence_requirements=["dispatch_plan"],
            )
        )

    if include_operator_mapper:
        dispatches.append(
            make_dispatch(
                ssot_id=ssot_id,
                task_id=task_id,
                slice_id=f"{prefix}-operator-mapper",
                agent_type="operator",
                slice_kind="work",
                timebox_minutes=operator_timebox,
                dependencies=operator_auditor_dependencies,
                goal="Map ownership boundaries and dependency risks for safe parallel scheduling.",
                acceptance=[
                    "Return ownership map and collision risks.",
                    "Recommend a practical parallel dispatch order.",
                ],
                constraints=[
                    "Read-only investigation.",
                    "No repository content modifications.",
                ],
                evidence_requirements=["commands", "analysis"],
            )
        )

    if include_auditor:
        dispatches.append(
            make_dispatch(
                ssot_id=ssot_id,
                task_id=task_id,
                slice_id=f"{prefix}-auditor-pre-mortem",
                agent_type="auditor",
                slice_kind="review",
                timebox_minutes=auditor_timebox,
                dependencies=operator_auditor_dependencies,
                goal="Run a pre-mortem protocol review of planned dispatch topology.",
                acceptance=[
                    "Flag high coupling risks, ownership clashes, and sequencing hazards.",
                    "Recommend changes needed before downstream worker dispatch.",
                ],
                constraints=[
                    "Review-only output.",
                    "No repository edits.",
                ],
                evidence_requirements=["review_notes"],
            )
        )

    return dispatches


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate council-bootstrap task-dispatch fixtures."
    )
    parser.add_argument("scenario", help="Scenario slug, e.g. pack-configs-pubfi-cli")
    parser.add_argument("--task-id", default="council-route", help="Task identifier.")
    parser.add_argument(
        "--supervisor-count",
        type=int,
        default=2,
        help="Number of supervisor planning waves.",
    )
    parser.add_argument(
        "--supervisor-timebox-minutes",
        type=int,
        default=10,
        help="timebox for supervisor plan slices.",
    )
    parser.add_argument(
        "--no-operator-mapper",
        action="store_false",
        dest="operator_mapper",
        default=True,
        help="Disable operator mapper slice.",
    )
    parser.add_argument(
        "--operator-timebox-minutes",
        type=int,
        default=6,
        help="timebox for operator mapper slice.",
    )
    parser.add_argument(
        "--no-auditor",
        action="store_false",
        dest="auditor",
        default=True,
        help="Disable auditor pre-mortem slice.",
    )
    parser.add_argument(
        "--auditor-timebox-minutes",
        type=int,
        default=8,
        help="timebox for auditor pre-mortem slice.",
    )
    parser.add_argument(
        "--depend-on-supervisors",
        action="store_true",
        help=(
            "If set, operator/auditor slices depend on every supervisor slice."
            " Useful for conservative serialization; default keeps the bootstrap wave parallel."
        ),
    )
    parser.add_argument(
        "--format",
        default="array",
        choices=("array", "ndjson"),
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Write output to file; '-' prints to stdout.",
    )
    parser.add_argument(
        "--hex-len",
        type=int,
        default=12,
        help="Hex length for scenario hash in ssot_id.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        _ = make_ssot_id(args.scenario, args.hex_len)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.supervisor_count < 1:
        print("ERROR: --supervisor-count must be >= 1", file=sys.stderr)
        return 2

    dispatches = build_council_bootstrap(
        scenario=args.scenario,
        task_id=args.task_id,
        supervisor_count=args.supervisor_count,
        depend_on_supervisors=args.depend_on_supervisors,
        include_auditor=args.auditor,
        include_operator_mapper=args.operator_mapper,
        supervisor_timebox=args.supervisor_timebox_minutes,
        operator_timebox=args.operator_timebox_minutes,
        auditor_timebox=args.auditor_timebox_minutes,
        hex_len=args.hex_len,
    )

    if args.format == "array":
        payload = json.dumps(dispatches, indent=2, sort_keys=False)
    else:
        payload = "\n".join(json.dumps(item, sort_keys=False) for item in dispatches)

    if args.output == "-":
        print(payload)
    else:
        with open(args.output, "w", encoding="utf-8") as fp:
            fp.write(payload)
            if args.format == "array":
                fp.write("\n")
            else:
                fp.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
