# review-loop (Dev-only)

This directory contains development-only artifacts for the shared `review-loop` skill.

## Quick smoke

From the repo root:

```sh
python3 dev/review-loop/run_smoke.py
```

The smoke validates the checked-in bounded review -> fix -> verify -> re-review contract, including head-SHA binding, adversarial review, and three-round escalation.
