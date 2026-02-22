# E2E Sample Fixtures (v2)

This directory contains minimal, schema-valid **example payloads** for the protocol v2 E2E test.

## Validate

From the skill root:

```sh
cd ~/.codex/skills/codex-multi-agent-protocol
python3 references/e2e/validate_payloads.py
```

## Notes

- These fixtures validate schema shape and required fields.
- They do not prove runtime behavior (actual spawning, wait-any, close_agent hygiene).

