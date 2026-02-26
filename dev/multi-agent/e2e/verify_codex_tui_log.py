#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass

from jsonschema import Draft202012Validator


ROOT_SPAWN_ALLOWLIST = {"auditor", "orchestrator"}
LEAF_SPAWN_ALLOWLIST = {"operator", "coder_spark", "coder_codex"}

THREAD_ID_RE = re.compile(r"thread_id=([0-9a-f-]{36})\s*$")
TOOLCALL_RE = re.compile(r"ToolCall: (\w+)\s+(\{.*\})\s+thread_id=")


@dataclass(frozen=True)
class ToolCall:
    lineno: int
    nesting: int
    caller_thread_id: str
    tool: str
    payload: dict


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Verify Codex TUI log invariants for a multi-agent ssot_id."
    )
    p.add_argument("--ssot-id", required=True, help="ssot_id to filter on")
    p.add_argument(
        "--log-path",
        default=os.path.expanduser("~/.codex/log/codex-tui.log"),
        help="Path to codex-tui.log (default: ~/.codex/log/codex-tui.log)",
    )
    p.add_argument(
        "--validate-leaf-dispatch",
        action="store_true",
        help="Validate leaf spawn_agent message JSON against schemas/leaf-dispatch.schema.json",
    )
    return p.parse_args(argv)


def read_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def parse_toolcalls(lines: list[str]) -> list[ToolCall]:
    out: list[ToolCall] = []
    for i, line in enumerate(lines, 1):
        if "ToolCall:" not in line:
            continue
        m_tid = THREAD_ID_RE.search(line)
        m_tool = TOOLCALL_RE.search(line)
        if not m_tid or not m_tool:
            continue
        tool = m_tool.group(1)
        raw = m_tool.group(2)
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        prefix = line.split("ToolCall:", 1)[0]
        nesting = prefix.count("session_loop{thread_id=")
        out.append(
            ToolCall(
                lineno=i,
                nesting=nesting,
                caller_thread_id=m_tid.group(1),
                tool=tool,
                payload=payload,
            )
        )
    return out


def fail(msg: str) -> "Never":  # type: ignore[name-defined]
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    lines = read_lines(args.log_path)
    calls = parse_toolcalls(lines)

    spawn_calls = [c for c in calls if c.tool == "spawn_agent"]
    wait_calls = [c for c in calls if c.tool == "wait"]

    # Fast-fail: if we can see any nested spawn that mentions this ssot_id and is not a leaf role,
    # it's almost certainly an illegal same-level or cross-level spawn (e.g., Orchestrator spawning Orchestrator).
    ssot_tagged_spawns = [
        c for c in spawn_calls if args.ssot_id in str(c.payload.get("message", ""))
    ]
    illegal_ssot_nested_spawns = [
        c
        for c in ssot_tagged_spawns
        if c.nesting >= 2 and c.payload.get("agent_type") not in LEAF_SPAWN_ALLOWLIST
    ]
    if illegal_ssot_nested_spawns:
        bad = illegal_ssot_nested_spawns[0]
        fail(
            "detected non-leaf spawn_agent nested under a session_loop for this ssot_id "
            f"(line {bad.lineno}, nesting={bad.nesting}, agent_type={bad.payload.get('agent_type')!r})"
        )

    leaf_dispatch_validator: Draft202012Validator | None = None
    if args.validate_leaf_dispatch:
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "..",
            "multi-agent",
            "schemas",
            "leaf-dispatch.schema.json",
        )
        schema_path = os.path.normpath(schema_path)
        try:
            schema = json.loads(open(schema_path, "r", encoding="utf-8").read())
        except Exception as e:
            fail(f"failed to load leaf-dispatch schema at {schema_path!r}: {e}")
        Draft202012Validator.check_schema(schema)
        leaf_dispatch_validator = Draft202012Validator(schema)

    # Identify the root Director thread_id for this ssot_id by finding root-level spawn messages
    # that contain the ssot_id (this is the only reliable linkage without ToolResult ids).
    root_markers = [
        c for c in spawn_calls if c.nesting == 1 and args.ssot_id in str(c.payload.get("message", ""))
    ]
    if not root_markers:
        fail(f"no root-level spawn_agent ToolCall lines found containing ssot_id={args.ssot_id!r}")

    # Restrict the scan range to this run: from the first ssot-tagged root spawn to the next root-level
    # spawn_agent after the last ssot-tagged root spawn.
    start = root_markers[0]
    root_thread_id = start.caller_thread_id
    last_marker = root_markers[-1]
    next_root_spawn = next((c for c in spawn_calls if c.nesting == 1 and c.lineno > last_marker.lineno), None)
    end_line = next_root_spawn.lineno if next_root_spawn else (len(lines) + 1)
    in_range = [c for c in calls if start.lineno <= c.lineno < end_line]

    def is_nested_under_root(c: ToolCall) -> bool:
        if c.nesting < 2:
            return False
        line = lines[c.lineno - 1]
        return f"session_loop{{thread_id={root_thread_id}}}:session_loop{{thread_id=" in line

    root_spawns = [c for c in in_range if c.tool == "spawn_agent" and c.nesting == 1]
    nested_spawns = [
        c for c in in_range if c.tool == "spawn_agent" and is_nested_under_root(c)
    ]
    nested_waits = [c for c in in_range if c.tool == "wait" and is_nested_under_root(c)]

    # Depth guard:
    # In codex-tui.log, nesting counts include the root Director session_loop, so a depth=2 leaf
    # action often shows up as nesting==3 (Director -> Orchestrator -> Leaf). Treat nesting>3 as
    # a depth overflow (depth>=3), and separately forbid spawn_agent at nesting>=3.
    too_deep = [c for c in in_range if is_nested_under_root(c) and c.nesting > 3]
    if too_deep:
        bad = too_deep[0]
        fail(
            "detected nesting>3 (depth overflow) under root thread "
            f"(line {bad.lineno}, nesting={bad.nesting}, tool={bad.tool!r})"
        )
    illegal_leaf_spawns = [
        c
        for c in in_range
        if is_nested_under_root(c) and c.tool == "spawn_agent" and c.nesting >= 3
    ]
    if illegal_leaf_spawns:
        bad = illegal_leaf_spawns[0]
        fail(
            "detected spawn_agent at nesting>=3 (leaf/cross-level spawn) under root thread "
            f"(line {bad.lineno}, nesting={bad.nesting}, agent_type={bad.payload.get('agent_type')!r})"
        )

    # Root spawns should only be auditor/orchestrator.
    for c in root_spawns:
        agent_type = c.payload.get("agent_type")
        if agent_type not in ROOT_SPAWN_ALLOWLIST:
            fail(
                "root-level spawn_agent must be auditor/orchestrator only; got "
                f"{agent_type!r} (line {c.lineno})"
            )
    root_types = {c.payload.get("agent_type") for c in root_spawns}
    if "auditor" not in root_types or "orchestrator" not in root_types:
        fail(
            "expected Director to spawn both 'auditor' and 'orchestrator' at root "
            f"for ssot_id={args.ssot_id!r}; got root agent_types={sorted(t for t in root_types if t)!r}"
        )

    # Nested spawns under this root thread should only be leaf.
    if not nested_spawns:
        fail("expected at least one nested spawn_agent under the root thread (leaf dispatch)")
    nested_spawn_callers = {c.caller_thread_id for c in nested_spawns}
    if len(nested_spawn_callers) != 1:
        bad = sorted(nested_spawns, key=lambda c: c.lineno)[0]
        fail(
            "expected all nested leaf spawn_agent calls to originate from a single depth-1 thread "
            f"(Orchestrator). Got callers={sorted(nested_spawn_callers)!r} (example line {bad.lineno})"
        )
    leaf_spawner_thread_id = next(iter(nested_spawn_callers))
    for c in nested_spawns:
        agent_type = c.payload.get("agent_type")
        if agent_type not in LEAF_SPAWN_ALLOWLIST:
            fail(
                "nested spawn_agent under root thread must be leaf only; got "
                f"{agent_type!r} (line {c.lineno})"
            )
        if leaf_dispatch_validator is not None:
            msg = c.payload.get("message", "")
            try:
                dispatch = json.loads(msg)
            except Exception:
                fail(
                    "leaf spawn_agent message must be JSON when --validate-leaf-dispatch is set; "
                    f"line {c.lineno} agent_type={agent_type!r}"
                )
            errs = list(leaf_dispatch_validator.iter_errors(dispatch))
            if errs:
                fail(
                    "leaf dispatch JSON failed schema validation; "
                    f"line {c.lineno} first_error={errs[0].message!r}"
                )
            if dispatch.get("leaf_agent_type") != agent_type:
                fail(
                    "leaf dispatch JSON leaf_agent_type must match spawn_agent agent_type; "
                    f"line {c.lineno} leaf_agent_type={dispatch.get('leaf_agent_type')!r} agent_type={agent_type!r}"
                )
            if dispatch.get("ssot_id") != args.ssot_id:
                fail(
                    "leaf dispatch JSON ssot_id must match --ssot-id; "
                    f"line {c.lineno} ssot_id={dispatch.get('ssot_id')!r}"
                )

    # Heuristic windowing check: at least one nested `wait` call under this root thread.
    if not nested_waits:
        fail("expected at least one nested ToolCall: wait under the root thread (windowing)")
    wait_callers = {c.caller_thread_id for c in nested_waits}
    if leaf_spawner_thread_id not in wait_callers:
        bad = sorted(nested_waits, key=lambda c: c.lineno)[0]
        fail(
            "expected the leaf-spawning depth-1 thread to also call wait (windowing loop). "
            f"leaf_spawner_thread_id={leaf_spawner_thread_id!r} wait_callers={sorted(wait_callers)!r} "
            f"(example wait line {bad.lineno})"
        )

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
