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
- The Director is uncertain and wants fast, parallel research with evidence and review gates before answering.
- The user explicitly asks for research/design/comparison work and you want parallel Operator coverage with evidence and review gates.

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
- Decompose leaf slices so they are self-contained (inputs + constraints + evidence). Leaf agents must resolve small unknowns via research and safest reversible defaults (no user questions mid-flight).

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
- For runtime/stress guidance (threads, depth, open-files limits), follow `codex-multi-agent-protocol/references/PROTOCOL_TESTING.md`.
