# Multi-Agent Backtests (Deterministic)

This directory contains deterministic routing and broker scheduling backtests for the two-state protocol.

The simulator covers scheduler behaviors that fixture/schema checks cannot prove:

- route selection for `single` and `multi`
- wait-any replenishment vs wait-all wave scheduling
- write-lock enforcement for overlapping builder ownership
- handoff dedup merge behavior
- retry handling for failed attempts
- observable concurrency

## Run

From the repo root:

```sh
python3 dev/multi-agent/backtests/run_backtests.py
```

Or run the full smoke gate:

```sh
python3 dev/multi-agent/e2e/run_smoke.py
```

## Scenario layout

Each scenario folder contains:

- `scenario.json`: scenario kind, deterministic inputs, and expectations
- `dispatches.initial.json`: initial ticket board for scheduler scenarios
- `handoff.*.json`: deterministic handoff payload fixtures for scheduler scenarios
- `MANUAL.md`: manual replay/inspection notes when a scenario needs them
