---
name: codex-multi-agent-protocol
description: Use when a task requires multi-agent execution with Main (Director)/Auditor/Orchestrator and leaf-role routing (Coder for coding, Operator for non-coding) with schema-validated outputs.
---

# Codex Multi-Agent Protocol

## Objective

Provide a reliable, auditable slow-path workflow for multi-agent execution: explicit routing, explicit ownership, evidence-backed verification, and two-phase review (spec -> quality).

## When to use

- The task is non-trivial and benefits from delegated work or review gates (especially multi-slice repo changes or parallel read-only research).
- You need the Director/Auditor/Orchestrator/leaf-agent protocol with schema-validated outputs.
- You are validating or evolving the protocol package (schemas, fixtures, and operational workflow rules).

## Inputs

- The task goal, scope, and constraints (including "no-go" areas).
- The intended routing decision and task kind (for example: `write`, `read_only`).
- Ownership paths/scopes per slice (files, repos, or `web:` scopes).
- The minimum verification evidence that will be accepted for completion.

## Hard gates (non-negotiable)

- If `dispatch-preflight.routing_decision != "multi_agent"`, short-circuit and do not spawn leaf agents.
- Spawn allowlist: when `routing_decision == "multi_agent"`, spawn ONLY protocol agent types (Auditor/Orchestrator/Operator/Coder*) plus `awaiter` (waiting/polling only). Do not spawn built-in/default agent types (for example `worker`, `default`, `explorer`).
- Do not run parallel leaf agents unless independence assessment + ownership lock policy are satisfied.
- Auditor review must be spec-first, then quality. Quality review must not run before spec passes.
- No evidence, no completion: coders must provide `verification_steps`; operators must provide `actions`; orchestrator must provide `integration_report` evidence for write workflows.
- Do not proceed if any reviewer sets `blocked=true`.
- Close completed agents to avoid thread starvation.

## How to use

1. Read the operational playbook: `codex-multi-agent-protocol/references/WORKFLOWS.md`.
2. Use the protocol testing guide: `codex-multi-agent-protocol/references/PROTOCOL_TESTING.md`.
3. Run the smoke suite (schemas + examples + fixtures + invariants):
    - `python3 codex-multi-agent-protocol/references/e2e/run_smoke.py`

## Outputs

- A schema-valid set of payloads that includes evidence fields (verification and integration evidence).
- If evolving the protocol package: updated schemas/fixtures plus a successful run of `references/e2e/validate_payloads.py`.

## Notes

- Schemas are structural; invariants are enforced via workflow rules and fixture validation.
- Keep `routing_mode="assistant_nested"` unless the SSOT explicitly changes.
- Protocol v2 requires `protocol_version="2.0"` and a `dispatch-preflight` that includes sizing + routing. Non-multi-agent routing must short-circuit.

## Concurrency budgets (practical)

There are two independent bottlenecks:

- **Agent threads** (e.g. `max_threads=<N>`): how many subagents can be alive concurrently.
- **Tool/process resources** (FDs, processes, CPU): how many concurrent `exec_command`-style shell actions can run without destabilizing the runner.

Rules of thumb:

- Keep **agent concurrency aggressive** (use windowed dispatch and replenish; aim to saturate `max_threads` when you have independent slices).
    - Recommended default: keep a small reserve for orchestration and review work.
      - Example: `reserve_threads=2`, `window_size = max_threads - reserve_threads`
- Keep **tool concurrency opportunistic**:
    - If `ulimit -Sn` is high (typically `>= 4096`) and tool steps are short, you can usually run many `exec_command` calls concurrently (often up to `max_threads`) without special throttling.
    - Prefer **short** tool steps; avoid long `sleep` inside `exec_command` for stress tests (keep agents alive by not closing them instead).
    - If you see `os error 24` / "Too many open files", treat it as an **environment regression**: re-check `launchctl limit maxfiles` and `ulimit -Sn/-Hn` and fix the limit (don't "paper over" with protocol throttling).

Spawn hygiene:

- Always pass a non-empty initial `message` to `spawn_agent` (some runners fail closed with "Provide one of: message or items" if it's omitted).
