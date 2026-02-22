---
name: codex-multi-agent-protocol
description: Use when a task requires multi-agent execution with Director/Auditor/Orchestrator/Implementer routing and schema-validated outputs.
---

# Codex Multi-Agent Protocol

## When to use

- Use this skill when a task is non-trivial and benefits from delegated work or review gates (especially repository writes with ambiguity, risk, or multiple slices).
- Use it when validating or evolving the 4-role protocol (schemas, routing, liveness, and acceptance rules).

## Why this helps

- Packages the protocol schemas and test methodology together so validation is deterministic and portable.
- Keeps protocol evolution and regression checks close to the schemas to reduce drift.

## How to use

1. Run all validation steps from the skill root directory (where `schemas/` and `references/` exist):
    - Example: `cd ~/.codex/skills/codex-multi-agent-protocol`
2. Read the operational playbook at `references/WORKFLOWS.md` (routing guardrails, parallel windowing, spec→quality audit phases, integration evidence).
3. Validate schema structure and examples using `references/PROTOCOL_TESTING.md` section 2.
4. If schemas or routing rules changed, run the E2E and negative tests in `references/PROTOCOL_TESTING.md`.

## Contents

- `schemas/dispatch-preflight.schema.json`
- `schemas/agent-output.auditor.read_only.schema.json`
- `schemas/agent-output.auditor.write.schema.json`
- `schemas/agent-output.orchestrator.read_only.schema.json`
- `schemas/agent-output.orchestrator.write.schema.json`
- `schemas/agent-output.implementer.schema.json`
- `references/WORKFLOWS.md`
- `references/PROTOCOL_TESTING.md`

## Notes

- These schemas are structural. Cross-field/runtime invariants remain enforced by the active AGENTS protocol (or the protocol section of this skill when it is used).
- Keep `routing_mode` as `assistant_nested` unless the protocol SSOT explicitly changes.
- Protocol v2 requires `protocol_version="2.0"` and a `dispatch-preflight` that includes task sizing + routing decision. If the routing decision is not `multi_agent`, the protocol must short-circuit (no implementer spawns).

## Concurrency budgets (practical)

There are two independent bottlenecks:

- **Agent threads** (e.g. `max_threads=24`): how many subagents can be alive concurrently.
- **Tool/process resources** (FDs, processes, CPU): how many concurrent `exec_command`-style shell actions can run without destabilizing the runner.

Rules of thumb:

- Keep **agent concurrency aggressive** (use windowed dispatch and replenish; aim to saturate `max_threads` when you have independent slices).
- Keep **tool concurrency opportunistic**:
    - If `ulimit -Sn` is high (typically `>= 4096`) and tool steps are short, you can usually run many `exec_command` calls concurrently (often up to `max_threads`) without special throttling.
    - Prefer **short** tool steps; avoid long `sleep` inside `exec_command` for stress tests (keep agents alive by not closing them instead).
    - If you see `os error 24` / “Too many open files”, treat it as an **environment regression**: re-check `launchctl limit maxfiles` and `ulimit -Sn/-Hn` and fix the limit (don’t “paper over” with protocol throttling).

Spawn hygiene:

- Always pass a non-empty initial `message` to `spawn_agent` (some runners fail closed with “Provide one of: message or items” if it’s omitted).
