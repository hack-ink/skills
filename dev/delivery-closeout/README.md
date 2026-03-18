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
- explicit-anchor closeout flow from stdin or a file, so review-approved anchors do not need an empty follow-up commit just to flip `delivery_mode`
- untracked or GitHub-only ref sets read successfully without inventing Linear authority
- typed GitHub mirror refs work without any Git remote lookup
- string refs such as `#123` are rejected
- related-only Linear refs, multiple authority refs, invalid JSON, and wrong schema still stop before sync
