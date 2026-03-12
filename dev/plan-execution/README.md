# plan-execution (Dev-only)

This directory contains repo-local smoke coverage for the `plan-execution` skill. It stays
outside the installable skill directory so the installed skill only ships its runtime
reader.

## Quick smoke

From the repo root:

```sh
python3 dev/plan-execution/run_smoke.py
```

The smoke validates:

- a formatted `plan/1` contract produced for `plan-writing` is directly consumable by the
  `plan-execution` reader
- valid contracts can move through `ready`, `executing`, `blocked`, and `needs_replan`
- replanning can preserve accumulated evidence while returning the contract to `ready`
- prose-only plans, missing blocker reasons, and `done` states with unfinished tasks all
  stop deterministically
