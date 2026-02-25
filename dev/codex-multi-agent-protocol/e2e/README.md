# E2E Sample Fixtures (v2)

This directory contains minimal, schema-valid **example payloads** for the protocol v2 E2E test.

It includes:

- A `write` workflow suite (`*-write.json`)
- A non-write ops workflow suite (`*-research.json` + `operator-*.json`) (filenames kept for compatibility)

## Validate

From the repo root:

```sh
cd /path/to/hack-ink/skills
python3 dev/codex-multi-agent-protocol/e2e/run_smoke.py
python3 dev/codex-multi-agent-protocol/e2e/validate_payloads.py
```

## Notes

- These fixtures validate schema shape and required fields.
- `validate_payloads.py` also enforces cross-payload invariants (ID alignment, coder set consistency, allowed_paths containment) and runs a small negative suite to ensure the invariant checks actually fail when they should.
- They do not prove runtime behavior (actual spawning, wait-any, close_agent hygiene).
