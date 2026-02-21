# Protocol Testing Methodology

This document defines a repeatable test suite for the Director/Auditor/Orchestrator/Implementer protocol using the packaged schemas in `schemas/`.

## 1) Preconditions

1. Ensure your working tree includes the latest protocol package updates.
2. Confirm protocol tokens are present across the packaged schema set:
   - `rg -n 'assistant_nested|agent-output\\.auditor|agent-output\\.orchestrator|agent-output\\.implementer' schemas/*.json`
   - Run a second check to confirm legacy routing tokens are absent from the same paths.

Pass criteria:

- Required 4-role protocol tokens appear in packaged schema files.
- Legacy routing labels and assistant-era schema references are absent.

## 2) Schema Validation (Structural)

Run from the skill root (so `schemas/` resolves correctly):

```sh
cd ~/.codex/skills/codex-multi-agent-protocol
```

Then run:

```sh
python3 - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator
files = [
  'schemas/dispatch-preflight.schema.json',
  'schemas/agent-output.auditor.write.schema.json',
  'schemas/agent-output.auditor.read_only.schema.json',
  'schemas/agent-output.orchestrator.write.schema.json',
  'schemas/agent-output.orchestrator.read_only.schema.json',
  'schemas/agent-output.implementer.schema.json',
]
for f in files:
    d = json.loads(Path(f).read_text())
    Draft202012Validator.check_schema(d)
    v = Draft202012Validator(d)
    bad = []
    for i, ex in enumerate(d.get('examples', []), 1):
        errs = list(v.iter_errors(ex))
        if errs:
            bad.append((i, [e.message for e in errs]))
    print(f'{f}:', 'OK' if not bad else f'INVALID {bad}')
PY
```

Pass criteria:

- All six files return `OK`.

## 3) E2E Positive Test (Director -> Auditor -> Orchestrator -> Implementer)

Method:

1. Create two independent sandbox files.
2. Director delegates a write planning subtask to Auditor.
3. Auditor validates and delegates to Orchestrator.
4. Orchestrator spawns multiple Implementer slices in a windowed pattern (`spawn-first -> wait-any -> review -> spawn-next`) with at least 2 overlapping implementers.
5. Orchestrator routes implementer outputs to Auditor.
6. Auditor performs review passes and accepts the result.

Pass criteria:

- Final chain result: `status="done"`, `blocked=false`.
- `routing_mode="assistant_nested"`.
- `parallel_peak_inflight >= 2`.
- `implementer_subtask_ids` is non-empty.
- Every referenced implementer payload is schema-valid and includes required fields (`summary`, `self_check.command`, `self_check.evidence`).
- Orchestrator and Director do not finalize completion before Auditor review verdict.
- `review_loop.policy` is `adaptive_min2_max3_second_pass_stable`.
- `review_loop.auditor_passes` is between 2 and 3 inclusive.
- `review_loop.orchestrator_self_passes >= 2`.
- `validation_evidence` present and non-empty in both Orchestrator and Auditor write outputs.

## 4) Negative Tests

### A) Director skip-level dispatch attempt

Method:

- Director attempts direct dispatch to Orchestrator or Implementer.

Pass criteria:

- Result blocked with explicit skip-level-edge violation.

### B) Auditor skip-level dispatch attempt

Method:

- Auditor attempts direct dispatch to Implementer.

Pass criteria:

- Result blocked with explicit skip-level-edge violation.

### C) Invalid parent stamp

Method:

- Spawn role with invalid `[PARENT:...]` value.

Pass criteria:

- Blocked result with explicit parent-stamp violation reason.

### D) Schema-incomplete implementer payload

Method:

- Provide a payload missing required implementer-schema fields (for example missing `summary` or `self_check.command`).

Pass criteria:

- Auditor returns `status="awaiting_review"`, `blocked=true`.
- `blocking_reason` indicates schema invalidity.

### E) Audit pass bounds

Method:

- Force more than 3 Auditor passes for one write result while risks remain unresolved.

Pass criteria:

- More than 3 Auditor passes must be blocked.
- Fourth pass returns `status="awaiting_review"` with an explicit pass-boundary `blocking_reason`.

### F) Invalid routing mode

Method:

- Feed payload with `routing_mode != "assistant_nested"`.

Pass criteria:

- Schema or runtime checks reject the payload.

### G) Depth-limit enforcement (tool-level)

Method:

- Attempt to spawn a new tool/agent one level deeper than the current max depth at runtime.

Pass criteria:

- Attempt is blocked.
- Runtime output is schema-valid.
- `validation_evidence` is present and non-empty.

## 5) Concurrency Limit Test

Method:

1. Spawn `N` implementers that sleep and return JSON.
2. Increase `N` until spawn fails.
3. Record first failure.
4. Close completed implementers and retry.

Expected:

- Failure at configured thread limit (currently observed: 24).
- Completed implementers hold slots until `close_agent`.
- New spawn succeeds after close.

## 6) Wait-Any Test

Method:

1. Spawn probes with delays (for example 10s, 20s, 30s).
2. Call `wait` on all ids repeatedly.

Pass criteria:

- Early completion returns first when polled in time.
- No forced wait-all behavior while runnable work remains.

## 7) Stall / Timeout Handling Test

Method:

1. Run a long-running action under each role with poll intervals from your active AGENTS protocol section 9.
2. Verify escalation path when timeout threshold is reached.

Pass criteria:

- Escalation uses `send_input(interrupt=true)`.
- Final blocked output has `status="awaiting_review"`.
- `blocking_reason` starts with `timeout:`.
- Output includes non-empty `validation_evidence` where required.

## 8) Result Recording Template

```json
{
	"run_id": "protocol-test-YYYYMMDD-HHMM",
	"schema_validation": "pass|fail",
	"routing_mode_selected": "assistant_nested",
	"e2e_chain": "pass|fail",
	"negative_director_skip_level": "pass|fail",
	"negative_auditor_skip_level": "pass|fail",
	"negative_invalid_parent_stamp": "pass|fail",
	"negative_depth_limit_tool_level": "pass|fail",
	"negative_schema_incomplete_implementer_payload": "pass|fail",
	"negative_audit_pass_bounds": "pass|fail",
	"negative_invalid_routing_mode": "pass|fail",
	"stall_timeout_handling": "pass|fail",
	"concurrency_limit_observed": 24,
	"wait_any_verified": true,
	"notes": []
}
```

## 9) Cleanup

- Remove temporary test artifacts and close remaining test agents.
