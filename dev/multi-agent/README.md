# multi-agent (Dev-only)

This directory contains development-only artifacts for the installable `multi-agent` skill.

The current dev harness covers only the reset protocol:

- `ticket-dispatch/1`
- `ticket-result/1`
- broker-local follow-up generation, salvage, and review-gate bookkeeping
- manual-policy-aware `authorized_skills` enforcement against the repo-local child-skill policy, including known-skill validation

## Quick smoke

From the repo root:

```sh
python3 dev/multi-agent/e2e/run_smoke.py
```

## Contents

- `e2e/`: schema fixtures, markdown template validation, and interactive Broker doc checks
- `backtests/`: deterministic routing and scheduler simulations for the new protocol, using inline scenario tickets
- `BROKER_E2E.md`: manual runtime checklist for live Broker sessions
