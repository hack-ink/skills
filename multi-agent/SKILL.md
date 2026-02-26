---
name: multi-agent
description: Use when a task requires multi-agent execution with Main (Director)/Auditor/Orchestrator and leaf-role routing (Coder for coding, Operator for non-coding) with schema-validated outputs.
---

# Codex Multi-Agent Protocol

## Objective

Provide a reliable, auditable slow-path workflow for multi-agent execution: explicit routing, explicit ownership, evidence-backed verification, and two-phase review (spec -> quality).

## When to use

- The task is non-trivial and benefits from delegated work or review gates (especially multi-slice repo changes or parallel read-only research).
- You need the Director/Auditor/Orchestrator/leaf-agent protocol with schema-validated outputs.
- The Director is uncertain and wants fast, parallel research with evidence and review gates before answering.

## Inputs

- The task goal, scope, and constraints (including "no-go" areas).
- The intended routing decision and task kind (for example: `write`, `read_only`).
- Ownership paths/scopes per slice (files, repos, or `web:` scopes).
- The minimum verification evidence that will be accepted for completion.

## Hard gates (non-negotiable)

- Short-circuit if `dispatch-preflight.routing_decision != "multi_agent"` (no leaf spawns).
- Enforce the spawn allowlist (protocol types only; no built-ins).
- Enforce the depth=2 spawn topology:
  - Director (main) spawns `auditor` and `orchestrator` as peers.
  - Orchestrator spawns leaf agents: `operator`, `coder_spark` (primary), `coder_codex` (fallback only).
  - Auditor and leaf roles spawn no agents.
- Enforce no same-level or cross-level spawns:
  - Director must not spawn leaf roles and must not replace itself.
  - Orchestrator must never spawn `director`, `auditor`, or `orchestrator`.
  - Auditor and leaf roles must never spawn any agents.
- Enforce continuity: for a given `ssot_id`, keep the same Auditor + Orchestrator pairing. If blocked, spawn new coding/research leaf slices under that same Orchestrator.
- Enforce the repo-write gate: only coders (spawned via `coder_spark` or fallback `coder_codex`) may implement repo changes (no file edits by Orchestrator/Operator/Auditor).
- Enforce spec-first review, evidence-first completion, and stop on `blocked=true`.
- Close completed leaf agents to avoid thread starvation.

## How to use

1. Read the operational playbook: `multi-agent/references/WORKFLOWS.md`.

## Outputs

- A schema-valid set of payloads that includes evidence fields (verification and integration evidence).

## Notes

- Schemas are structural; invariants are enforced via workflow rules and evidence requirements.
- Depth is capped at 2: Director -> (Auditor | Orchestrator) -> leaf.
- `write` vs `read_only` are workflow/output-schema variants, not additional agent roles. Orchestrator must never spawn another Orchestrator; choose the Orchestrator output schema based on whether the task changes repo state.
- `routing_mode` is pinned by the packaged schemas; if you change it, update schemas and operational workflow rules together.
- Protocol v2 requires `protocol_version="2.0"` and a `dispatch-preflight` that includes sizing + routing. Non-multi-agent routing must short-circuit.
