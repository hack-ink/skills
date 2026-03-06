# E2E Sample Fixtures (vNext)

This directory contains schema-valid **example payloads** for the vNext broker model:

- Broker-only spawning (`max_depth=1`)
- No Orchestrator role
- JSON-only dispatch + JSON-only worker results
- Route fixtures for `single`, `single-deep`, and `multi`

## Validate (repo-local)

From the repo root:

```sh
python3 dev/multi-agent/e2e/run_smoke.py
python3 dev/multi-agent/e2e/validate_broker_e2e.py
python3 dev/multi-agent/e2e/validate_payloads.py
```

## What this proves / doesn’t prove

- Proves: schema validity, ssot_id format (scenario-hash), route-tier fixtures, and fixture invariants (no forbidden roles, no write ownership overlap).
- Does not prove: runtime behavior (actual spawning, `functions.wait`, `close_agent` hygiene).
