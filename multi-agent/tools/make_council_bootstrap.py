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
    ownership_paths: list[str] | None = None,
) -> dict:
    dispatch = {
        "schema": "task-dispatch/1",
        "ssot_id": ssot_id,
        "task_id": task_id,
        "slice_id": slice_id,
        "agent_type": agent_type,
        "slice_kind": slice_kind,
        "timebox_minutes": timebox_minutes,
        "dependencies": dependencies or [],
        "task_contract": {
            "goal": goal,
            "acceptance": acceptance,
            "constraints": constraints,
        },
        "evidence_requirements": evidence_requirements,
    }
    if ownership_paths is not None:
        dispatch["ownership_paths"] = ownership_paths
    return dispatch


def build_council_bootstrap(
    scenario: str,
    task_id: str,
    depend_on_runner: bool,
    include_inspector: bool,
    include_runner_mapper: bool,
    runner_timebox: int,
    inspector_timebox: int,
    hex_len: int,
) -> list[dict]:
    ssot_id = make_ssot_id(scenario, hex_len=hex_len)
    prefix = f"{scenario}-council"
    dispatches: list[dict] = []

    runner_slice_id = ""
    if include_runner_mapper:
        runner_slice_id = f"{prefix}-runner-mapper"
        dispatches.append(
            make_dispatch(
                ssot_id=ssot_id,
                task_id=task_id,
                slice_id=runner_slice_id,
                agent_type="runner",
                slice_kind="work",
                timebox_minutes=runner_timebox,
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

    followup_dependencies: list[str] = []
    if depend_on_runner and runner_slice_id:
        followup_dependencies = [runner_slice_id]

    if include_inspector:
        dispatches.append(
            make_dispatch(
                ssot_id=ssot_id,
                task_id=task_id,
                slice_id=f"{prefix}-inspector-pre-mortem",
                agent_type="inspector",
                slice_kind="review",
                timebox_minutes=inspector_timebox,
                dependencies=followup_dependencies,
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
        "--no-runner-mapper",
        action="store_false",
        dest="runner_mapper",
        default=True,
        help="Disable runner mapper slice.",
    )
    parser.add_argument(
        "--runner-timebox-minutes",
        type=int,
        default=6,
        help="timebox for runner mapper slice.",
    )
    parser.add_argument(
        "--no-inspector",
        action="store_false",
        dest="inspector",
        default=True,
        help="Disable inspector pre-mortem slice.",
    )
    parser.add_argument(
        "--inspector-timebox-minutes",
        type=int,
        default=8,
        help="timebox for inspector pre-mortem slice.",
    )
    parser.add_argument(
        "--depend-on-runner",
        action="store_true",
        help=(
            "If set, inspector depends on runner mapper. "
            "Default keeps the bootstrap wave parallel."
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

    if not (args.runner_mapper or args.inspector):
        print(
            "ERROR: at least one slice must be enabled (runner mapper or inspector)",
            file=sys.stderr,
        )
        return 2

    dispatches = build_council_bootstrap(
        scenario=args.scenario,
        task_id=args.task_id,
        depend_on_runner=args.depend_on_runner,
        include_inspector=args.inspector,
        include_runner_mapper=args.runner_mapper,
        runner_timebox=args.runner_timebox_minutes,
        inspector_timebox=args.inspector_timebox_minutes,
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
            fp.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
