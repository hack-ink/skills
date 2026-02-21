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
2. Validate schema structure and examples using `references/PROTOCOL_TESTING.md` section 2.
3. If schemas or routing rules changed, run the E2E and negative tests in `references/PROTOCOL_TESTING.md`.

## Contents

- `schemas/dispatch-preflight.schema.json`
- `schemas/agent-output.auditor.read_only.schema.json`
- `schemas/agent-output.auditor.write.schema.json`
- `schemas/agent-output.orchestrator.read_only.schema.json`
- `schemas/agent-output.orchestrator.write.schema.json`
- `schemas/agent-output.implementer.schema.json`
- `references/PROTOCOL_TESTING.md`

## Notes

- These schemas are structural. Cross-field/runtime invariants remain enforced by the active AGENTS protocol (or the protocol section of this skill when it is used).
- Keep `routing_mode` as `assistant_nested` unless the protocol SSOT explicitly changes.
