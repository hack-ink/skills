# E2E Sample Fixtures (Two-State)

This directory contains schema-valid fixtures and validators for the reset protocol.

## What is covered

- `ticket-dispatch/1` examples for Runner, Builder, and Inspector tickets
- `ticket-result/1` examples for done and blocked results
- route selection fixtures for `single` and `multi`
- repo-local manual-policy validation for `authorized_skills`, policy skill names, and fixed `default_child_policy`
- broker-local recovery expectations for invalid or stalled workers

## Validate

From the repo root:

```sh
python3 dev/multi-agent/e2e/validate_payloads.py
python3 dev/multi-agent/e2e/validate_doc_templates.py
python3 dev/multi-agent/e2e/validate_broker_e2e.py
python3 dev/multi-agent/e2e/run_smoke.py
```

## Limits

These checks prove schema validity, fixture integrity, and doc-template consistency. They do not prove live `functions.wait` behavior by themselves.
