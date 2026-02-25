# Protocol Testing Methodology

This document defines a repeatable test suite for the Director/Auditor/Orchestrator/leaf-agent protocol using the packaged schemas in `schemas/`.

Operational workflow rules (parallel windowing, spec->quality gates, integration evidence) live in `references/WORKFLOWS.md`.

## Test tiers (recommended)

- **Smoke (default, < 2 min):** Run `python3 references/e2e/run_smoke.py`. Then run sections **1-3** with **2 coders** and a small window (2). This validates schema/examples + fixtures quickly, then validates depth=3 nesting + wait-any behavior without stressing the thread pool.
- **Stress (on-demand, can be slow):** Run sections **5-7** only when you change runtime concurrency settings (`max_threads`, scheduler) or when debugging liveness/timeout issues.

Notes:

- `codex exec` is **not required** to run these tests. It is only useful when you want a **clean, ephemeral, non-interactive** reproduction (e.g., regression runs) and a single captured final JSON output.
- Always **`close_agent` for completed children**. Finished-but-not-closed agents continue consuming thread slots and can make later tasks appear "stuck" due to thread starvation.

## 1) Preconditions

1. Ensure your working tree includes the latest protocol package updates.
2. Confirm the runtime is configured for depth=3 nesting (recommended: `max_depth = 3`).
3. Confirm strict hierarchy for positive tests (no skip-level spawns):
    - Director (main) -> Auditor -> Orchestrator -> (Coder | Operator | Awaiter)
    - Do not use `Director -> Orchestrator` for depth testing (it is forbidden by protocol).
4. Confirm protocol tokens are present across the packaged schema set:
    - `rg -n 'assistant_nested|agent-output\\.auditor|agent-output\\.orchestrator|agent-output\\.(coder|operator)' schemas/*.json`
    - Confirm legacy routing tokens are absent (should return no matches; exit code 1):
        - `rg -n 'assistant_solo|assistant_direct|assistant_router|agent-output\\.director|director-output|auditor-output|orchestrator-output|coder-output' schemas/*.json`
5. Confirm protocol v2 fields are present across the packaged schema set:
    - `rg -n '\"protocol_version\"|\"workflow_mode\"|\"task_kind\"|\"routing_decision\"' schemas/*.json`
6. (Recommended for stress runs) Confirm open-files limits are not at the macOS default:
    - `launchctl limit maxfiles`
    - `ulimit -Sn` and `ulimit -Hn`
    - If soft is `256`, expect high-concurrency `exec_command` runs to be flaky or fail with `os error 24`.
    - Note: `launchctl limit` can be higher than the per-shell soft limit (`ulimit -Sn`). Prefer checking both.
    - If you see `os error 24` even with a high `max_threads`, fix the open-files limits (don't rely on protocol-level throttling).
7. (Recommended for stress runs) Ensure no other long-running Codex sessions are consuming agent threads:
    - `ps -Ao pid,etime,command | rg '\\bcodex( resume)?\\b'`
    - Close/exit other interactive sessions before trying to saturate `max_threads`.

Pass criteria:

- Required protocol tokens appear in packaged schema files (auditor, orchestrator, coder, operator).
- Legacy routing labels and assistant-era schema references are absent.

## 2) Schema Validation (Structural)

Run from the skill root (so `schemas/` resolves correctly). If you are editing this repo directly, run from the repo root and prefix paths with `codex-multi-agent-protocol/`.

```sh
cd /path/to/codex-multi-agent-protocol
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
  'schemas/agent-output.coder.schema.json',
  'schemas/agent-output.operator.schema.json',
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

- All seven files return `OK`.

## 3) E2E Positive Test (v2 chain: Director -> Auditor -> Orchestrator -> Coder)

Goal:

- Exercise **windowed** parallel dispatch (`wait_any`) with ownership lock.
- Exercise **spec -> quality** audit phases.
- Exercise Orchestrator **integration evidence** (`integration_report`).

### Setup

1. Create a run dir and two independent sandbox files:
    - `RUN_DIR=$(mktemp -d)`
    - `printf 'a\n' > \"$RUN_DIR/a.txt\"`
    - `printf 'b\n' > \"$RUN_DIR/b.txt\"`
2. Produce a v2 `dispatch-preflight` with:
    - `protocol_version="2.0"`
    - `routing_mode="assistant_nested"`
    - `routing_decision="multi_agent"`
    - `review_policy.phase_order=["spec","quality"]`
    - `parallel_policy.wait_strategy="wait_any"`, `parallel_policy.conflict_policy="ownership_lock"`, `parallel_policy.window_size=2`
3. Execute the chain in your runtime:
    - Director delegates to Auditor
    - Auditor delegates to Orchestrator
    - Orchestrator runs **2+ coders** in a **windowed** pattern (`spawn-first -> wait-any -> review -> spawn-next`)
    - Orchestrator closes coders; Auditor closes Orchestrator; Director closes Auditor

### Artifacts to capture

Save the final JSON payloads for:

- Dispatch preflight: `dispatch-preflight.json`
- Each coder payload: `coder-*.json` (at least 2)
- Orchestrator write payload: `orchestrator-write.json`
- Auditor write payload: `auditor-write.json`

### Validation

1. Validate each payload against the packaged schemas:

```sh
python3 - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

def validate(schema_path: str, payload_path: str) -> None:
    schema = json.loads(Path(schema_path).read_text())
    payload = json.loads(Path(payload_path).read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    print("OK:", payload_path, "against", schema_path)

# Adjust payload paths as needed.
validate("schemas/dispatch-preflight.schema.json", "dispatch-preflight.json")
validate("schemas/agent-output.orchestrator.write.schema.json", "orchestrator-write.json")
validate("schemas/agent-output.auditor.write.schema.json", "auditor-write.json")
PY
```

2. Confirm runtime invariants (not just schema):

- Orchestrator uses `conflict_policy="ownership_lock"` and does not run overlapping `ownership_paths` concurrently.
- `parallel_peak_inflight >= 2` (smoke target: 2).
- Orchestrator write payload includes `dispatch_plan`, `review_phases`, and `integration_report` with non-empty evidence.
- Auditor write payload has exactly two `audit_phases` in order: spec first, quality second.

Optional quick check:

- Validate the bundled sample fixtures and invariants: `python3 references/e2e/validate_payloads.py`

Pass criteria:

- Final chain result: `status="done"`, `blocked=false`.
- `routing_mode="assistant_nested"`.
- `parallel_peak_inflight >= 2`.
- `coder_subtask_ids` is non-empty.
- Every referenced coder payload is schema-valid and includes required v2 fields (`protocol_version`, `workflow_mode`, `task_contract`, `verification_steps`).
- Orchestrator and Director do not finalize completion before Auditor review verdict.
- `review_loop.policy` is `adaptive_min2_max3_second_pass_stable`.
- `review_loop.auditor_passes` is between 2 and 3 inclusive.
- `review_loop.orchestrator_self_passes >= 2`.
- Orchestrator write output includes `dispatch_plan`, `review_phases`, and `integration_report` with non-empty evidence.
- Auditor write output includes `audit_phases` (spec first, quality second) and a populated `diff_review` (or `not_applicable` with evidence).

## 4) Negative Tests

### A) Director skip-level dispatch attempt

Method:

- Director attempts direct dispatch to Orchestrator or Coder.

Pass criteria:

- Result blocked with explicit skip-level-edge violation.

### B) Auditor skip-level dispatch attempt

Method:

- Auditor attempts direct dispatch to Coder.

Pass criteria:

- Result blocked with explicit skip-level-edge violation.

### C) Same-level spawn attempt

Method:

- Auditor attempts to spawn another Auditor, or Orchestrator attempts to spawn another Orchestrator.

Pass criteria:

- Result blocked with explicit hierarchy violation.

### D) Invalid parent stamp

Method:

- Spawn role with invalid `[PARENT:...]` value.

Pass criteria:

- Blocked result with explicit parent-stamp violation reason.

### E) Schema-incomplete coder payload

Method:

- Provide a payload missing required coder-schema fields (for example missing `task_contract` or `verification_steps`).

Pass criteria:

- Auditor returns `status="awaiting_review"`, `blocked=true`.
- `blocking_reason` indicates schema invalidity.

### F) Audit pass bounds

Method:

- Force more than 3 Auditor passes for one write result while risks remain unresolved.

Pass criteria:

- More than 3 Auditor passes must be blocked.
- Fourth pass returns `status="awaiting_review"` with an explicit pass-boundary `blocking_reason`.

### G) Invalid routing mode

Method:

- Feed payload with `routing_mode != "assistant_nested"`.

Pass criteria:

- Schema or runtime checks reject the payload.

### H) Depth-limit enforcement (tool-level)

Method:

- Attempt to spawn a new tool/agent one level deeper than the current max depth at runtime.

Pass criteria:

- Attempt is blocked.
- Runtime output is schema-valid.
- `validation_evidence` is present and non-empty.

### I) Routing short-circuit (non-multi-agent)

Method:

- Provide a `dispatch-preflight` with `routing_decision` set to `micro_solo` or `single_agent`.
- Attempt to proceed with spawning coders anyway.

Pass criteria:

- Chain must short-circuit: no coder spawns.
- Output indicates blocked/redirected routing with explicit reason.

### J) Ownership overlap in parallel slices

Method:

- Orchestrator attempts to run two concurrent coders with overlapping `ownership_paths`.

Pass criteria:

- Result is blocked (Orchestrator or Auditor) with an explicit ownership/conflict-policy violation.

## 5) Concurrency Limit Test

Method:

1. Spawn `N` Operators that sleep and return JSON (preferred; no repo writes).
2. Increase `N` until spawn fails.
3. Record first failure.
4. Close completed leaf agents and retry.

Expected:

- Failure at the configured thread limit (`max_threads`).
- Completed leaf agents hold slots until `close_agent`.
- New spawn succeeds after close.

Practical guidance:

- Run this as **Stress** only (it can take minutes and will amplify any missing `close_agent` hygiene).
- If you see slowdowns, first confirm no completed agents are left unclosed (thread starvation).
- Always pass a non-empty `message` to `spawn_agent` (omit it and you may get a tool-level failure that looks like a concurrency issue).

## 5b) Mixed-Depth Fill Test (depth1/2/3 mix)

Purpose:

- Validate nested spawning (depth=3) while saturating `max_threads` with a mixed topology.

Method (example for `max_threads=32`; substitute your configured `max_threads`):

1. Director spawns 4 Auditors total:
    - 1x Auditor root (will spawn orchestrators)
    - 3x idle Auditors (depth1 leaves)
2. Auditor root spawns 4 Orchestrators:
    - ORCH_IDLE spawns 0 leaf agents (depth2 leaf)
    - ORCH_A spawns 8 Operators (op_1..op_8)
    - ORCH_B spawns 8 Operators (op_9..op_16)
    - ORCH_C spawns 8 Operators (op_17..op_24)
3. Each Operator runs one short marker command (no need for agent_id env vars):
    - `bash -lc 'echo \"label=op_N\" > <run_dir>/op_N.txt; date >> <run_dir>/op_N.txt; ulimit -Sn >> <run_dir>/op_N.txt'`
4. After the target population is reached, attempt 1 extra spawn (e.g. from ORCH_C). Record the exact failure text.
5. Close all leaf agents, then orchestrators, then auditors.

Pass criteria:

- Exactly `max_threads` live subagents are reached (example: `4 + 4 + 24 = 32`).
- Extra spawn fails with `agent thread limit reached (max 32)` (or equivalent runtime message; value depends on your config).
- All marker files exist under the run dir.

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
	"negative_schema_incomplete_coder_payload": "pass|fail",
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
