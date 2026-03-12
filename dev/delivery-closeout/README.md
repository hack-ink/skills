# delivery-closeout (Dev-only)

This directory contains repo-local smoke coverage for the `delivery-closeout` skill. It
stays outside the installable skill directory so the installed skill only ships its runtime
contract and helper script.

## Quick smoke

From the repo root:

```sh
python3 dev/delivery-closeout/run_smoke.py
```

The smoke validates:

- happy-path producer/consumer flow from `delivery-prepare/scripts/build_delivery_contract.py`
  into `delivery-closeout/scripts/read_delivery_contract.py`
- typed GitHub mirror refs work without any Git remote lookup
- string refs such as `#123` are rejected
- GitHub-only ref sets, multiple authority refs, invalid JSON, wrong schema, and empty
  refs all stop before sync
