# Multi-Agent Backtests (Deterministic)

This directory contains deterministic backtests for the reset protocol.

The simulator covers:

- two-state route selection
- wait-any scheduling with role lane caps
- Builder `write_scope` locking
- Inspector gate ordering
- broker-local salvage handling for stalled workers

## Run

From the repo root:

```sh
python3 dev/multi-agent/backtests/run_backtests.py
```

The scenarios live under `dev/multi-agent/backtests/scenarios/` and use inline
`initial_tickets` plus reset-protocol metadata only. No separate handoff or
dispatch fixture files remain in the active scenario format.
