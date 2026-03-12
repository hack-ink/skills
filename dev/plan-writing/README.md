# plan-writing (Dev-only)

This directory contains repo-local smoke coverage for the `plan-writing` skill. It stays
outside the installable skill directory so the installed skill only ships its runtime
contract helpers.

## Quick smoke

From the repo root:

```sh
python3 dev/plan-writing/run_smoke.py
```

The smoke validates:

- `format_plan_contract.py` canonicalizes raw `plan/1` JSON into the fenced markdown form
- `validate_plan_contract.py` accepts valid persisted `plan/1` contracts
- duplicate task ids, bad dependencies, and multiple active tasks fail deterministically
- optional trailing markdown context survives normalization without affecting validation
