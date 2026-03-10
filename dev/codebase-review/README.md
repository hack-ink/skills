# codebase-review (Dev-only)

This directory contains development-only validation for the `codebase-review` skill.
It stays outside the installable skill directory so installations keep only the
runtime gate scripts and templates.

## Quick smoke

From the repo root:

```sh
python3 dev/codebase-review/run_smoke.py
```

This smoke entrypoint creates a temporary Git repository and validates:

- `check-review-coverage.py` with a passing approved/current-SHA ledger row
- `check-review-coverage.py` failure when the ledger status is not approved
- `check-review-closeout.py` with passing structured findings/slice/risk artifacts
- `check-review-closeout.py` failure when a Medium finding lacks `mitigation_plan`
