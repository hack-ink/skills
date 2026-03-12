# delivery-prepare (Dev-only)

This directory contains repo-local smoke coverage for the `delivery-prepare` skill. It
stays outside the installable skill directory so the installed skill only ships its runtime
contract and helper scripts.

## Quick smoke

From the repo root:

```sh
python3 dev/delivery-prepare/run_smoke.py
```

The smoke validates:

- `build_delivery_contract.py` fails when `--authority-linear-ref` is missing
- `build_delivery_contract.py` fails when `--delivery-mode` is missing
- `build_delivery_contract.py` emits `delivery/1` typed refs
- `validate_delivery_contract.py` rejects invalid authority, mode, and ref shapes
- `validate_delivery_contract.py` accepts valid `delivery/1` contracts
