---
name: codex-multi-agent-protocol
description: Protocol package for 4-role Director->Auditor->Orchestrator->Implementer routing with canonical JSON schemas and repeatable validation/testing steps.
---

# Codex Multi-Agent Protocol

## When to use

- Use this skill when defining, validating, or testing 4-role protocol messages across Director, Auditor, Orchestrator, and Implementer.
- Use it when updating runtime protocol schemas and when verifying outputs are structurally schema-valid before acceptance.

## Why this helps

- Provides a single portable package for protocol schemas instead of relying on runtime-only files.
- Keeps structural checks and protocol test procedure in one place so role routing and payload acceptance rules stay consistent.

## How to use

1. Validate schema structure and examples from repository root:
   - `python3 - <<'PY'`
   - Use the script in `references/PROTOCOL_TESTING.md` section 2.
2. If schemas changed, run positive and negative protocol tests described in `references/PROTOCOL_TESTING.md`.
3. Apply runtime updates only after schema validation passes and required protocol tests are green.

## Contents

- `schemas/dispatch-preflight.schema.json`
- `schemas/agent-output.auditor.read_only.schema.json`
- `schemas/agent-output.auditor.write.schema.json`
- `schemas/agent-output.orchestrator.read_only.schema.json`
- `schemas/agent-output.orchestrator.write.schema.json`
- `schemas/agent-output.implementer.schema.json`
- `references/PROTOCOL_TESTING.md`

## Notes

- These schemas are structural. Cross-field/runtime invariants remain enforced by the active AGENTS protocol.
- Keep `routing_mode` as `assistant_nested` unless the protocol SSOT explicitly changes.
