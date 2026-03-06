# multi-agent (Dev-only)

This directory contains development-only artifacts for the `multi-agent` skill (tests, fixtures, and methodology docs). It is intentionally kept **outside** the installable skill directory so installations do not include test content.

## Quick smoke

From the repo root:

```sh
python3 dev/multi-agent/e2e/run_smoke.py
```

This smoke entrypoint validates the installable JSON templates, the dev Broker routing doc, route fixtures, and the deterministic backtests.

## Backtests

Deterministic scheduler simulations live under `dev/multi-agent/backtests/`.

```sh
python3 dev/multi-agent/backtests/run_backtests.py
```

## Docs

- Broker interactive e2e: `dev/multi-agent/BROKER_E2E.md`
- Fixtures + validators: `dev/multi-agent/e2e/`
