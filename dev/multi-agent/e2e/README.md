# E2E Sample Fixtures (Two-State)

This directory contains schema-valid **example payloads** for the two-state broker model:

- Broker-only spawning (`max_depth=1`)
- No Orchestrator role
- JSON-only dispatch + JSON-only worker results
- Route fixtures for `single` and multiple `multi` shapes

## Validate (repo-local)

From the repo root:

```sh
python3 dev/multi-agent/e2e/run_smoke.py
python3 dev/multi-agent/e2e/validate_broker_e2e.py
python3 dev/multi-agent/e2e/validate_payloads.py
```

## What this proves / doesn’t prove

- Proves: schema validity, ssot_id format (scenario-hash), two-state route fixtures, `/1` worker-result alias acceptance (`agent_type` is canonical, `role` remains accepted as an identity alias), builder work-package binding, handoff dependency/identity validation, evidence-requirement satisfiability, blocked/partial recovery regressions, fail-closed Builder partial checkpoint schema/fixture coverage (`changeset` + `resume_from` + verification state), and fixture invariants (no write ownership overlap).
- Does not prove: live runtime behavior by itself. This e2e directory covers schema/document payload contracts, and the paired backtests (`dev/multi-agent/backtests/run_backtests.py` and `swarmbench-04-salvage`) cover simulator-level salvage continuity, but neither is live proof of real `functions.wait` behavior or `close_agent` hygiene.
