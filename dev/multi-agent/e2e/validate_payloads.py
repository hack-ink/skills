import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT = REPO_ROOT / "multi-agent"
E2E_DIR = Path(__file__).resolve().parent
SSOT_ID_RE = re.compile(r"^[a-z][a-z0-9]*-[a-z0-9][a-z0-9-]{7,127}$")
SSOT_ID_UUID_SUFFIX_RE = re.compile(
    r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$"
)
SSOT_ID_HEX_SUFFIX_RE = re.compile(r"[0-9a-f]{8,64}$")
REVIEW_LOOP_POLICY = "adaptive_min2_max5_second_pass_stable"
REVIEW_LOOP_PASSES_MIN = 2
REVIEW_LOOP_PASSES_MAX = 5


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def validate(schema_path: Path, payload: dict, payload_label: str) -> None:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    print(f"OK: {payload_label} against {schema_path.relative_to(ROOT)}")


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_any(predicate, items, label: str) -> None:
    if not any(predicate(x) for x in items):
        raise AssertionError(label)


def assert_ssot_id_format(ssot_id: str) -> None:
    if not SSOT_ID_RE.match(ssot_id):
        raise AssertionError(
            "ssot_id must be ASCII kebab-case and include a scenario prefix, e.g. 'ops-9f2c0d6a1b3e'"
        )

    # Enforce scenario-token convention: scenario-<hash|uuid>.
    # This intentionally rejects date-like suffixes (e.g. ...-2026-02-26) because they collide and are ambiguous in logs.
    suffix_ok = bool(SSOT_ID_UUID_SUFFIX_RE.search(ssot_id))
    if not suffix_ok:
        last_seg = ssot_id.split("-")[-1]
        suffix_ok = bool(SSOT_ID_HEX_SUFFIX_RE.fullmatch(last_seg))
    if not suffix_ok:
        raise AssertionError(
            "ssot_id must end with a UUID or a hex token (8..64 chars), e.g. "
            "'pack-configs-pubfi-cli-9f2c0d6a1b3e' or 'e2e-write-550e8400-e29b-41d4-a716-446655440000'"
        )

    # Disallow epoch-like numeric segments (opaque and easy to misread in logs).
    # Common cases:
    # - seconds since epoch: 10 digits (current era)
    # - milliseconds since epoch: 13 digits
    for seg in ssot_id.split("-")[1:]:
        if seg.isdigit() and len(seg) in (10, 13):
            raise AssertionError(
                "ssot_id must not contain epoch-like numeric segments (10/13 digits)"
            )


def has_token_line(lines: list[str], tokens: tuple[str, ...]) -> bool:
    return any(
        all(token in line for token in tokens)
        for line in [s.lower() for s in lines]
    )


def assert_ssot_invariants_in_text(ssot: dict) -> None:
    constraints = [str(x).lower() for x in ssot.get("constraints", [])]
    decisions = [str(x).lower() for x in ssot.get("decisions", [])]

    if not has_token_line(
        constraints, ("role-scoped", "director", "auditor", "orchestrator")
    ):
        raise AssertionError(
            "dispatch.ssot.constraints must include role-scoped Director spawn allowlist"
        )
    if not has_token_line(
        constraints,
        ("orchestrator", "operator", "coder_spark", "coder_codex"),
    ):
        raise AssertionError(
            "dispatch.ssot.constraints must include role-scoped Orchestrator spawn allowlist"
        )
    if not has_token_line(constraints, ("auditor", "leaf", "spawn", "none")) and not has_token_line(
        constraints, ("auditor", "spawn", "none")
    ):
        raise AssertionError(
            "dispatch.ssot.constraints must include Auditor/leaf no-spawn invariant"
        )
    if not has_token_line(constraints, ("no", "same-level", "spawns")):
        raise AssertionError(
            "dispatch.ssot.constraints must include no same-level spawn invariant"
        )
    if not has_token_line(decisions, ("continuity", "ssot_id", "auditor", "orchestrator")):
        raise AssertionError(
            "dispatch.ssot.decisions must include continuity gate pairing rule"
        )
    if not has_token_line(decisions, ("blocked", "fresh", "leaf", "pair")) and not has_token_line(
        decisions, ("blocked", "existing", "leaf", "pair")
    ) and not has_token_line(decisions, ("blocked", "additional", "leaf", "pair")):
        raise AssertionError(
            "dispatch.ssot.decisions must include blocked-phase rework rule under same pair"
        )


def is_within_allowed_paths(touched: str, allowed_paths: list[str]) -> bool:
    for allowed in allowed_paths:
        if touched == allowed or touched.startswith(allowed.rstrip("/") + "/"):
            return True
    return False


def assert_dispatch_preflight_invariants(dispatch: dict) -> None:
    assert_equal(dispatch["protocol_version"], "2.0", "dispatch.protocol_version")
    assert_equal(dispatch["routing_mode"], "assistant_nested", "dispatch.routing_mode")
    assert_equal(
        dispatch["routing_decision"], "multi_agent", "dispatch.routing_decision"
    )
    assert_ssot_id_format(dispatch["ssot_id"])
    assert_equal(
        dispatch["review_policy"]["phase_order"],
        ["spec", "quality"],
        "dispatch.review_policy.phase_order",
    )
    assert_equal(
        dispatch["review_policy"]["auditor_passes_target"],
        2,
        "dispatch.review_policy.auditor_passes_target",
    )
    assert_equal(
        dispatch["review_policy"]["auditor_passes_max"],
        5,
        "dispatch.review_policy.auditor_passes_max",
    )
    assert_equal(
        dispatch["parallel_policy"]["conflict_policy"],
        "ownership_lock",
        "dispatch.parallel_policy.conflict_policy",
    )
    assert_equal(
        dispatch["parallel_policy"]["wait_strategy"],
        "functions.wait",
        "dispatch.parallel_policy.wait_strategy",
    )
    assert_ssot_invariants_in_text(dispatch["ssot"])


def assert_orchestrator_invariants(orchestrator: dict, suite_name: str) -> None:
    if orchestrator.get("parallel_peak_inflight", 0) < 2:
        raise AssertionError("Expected orchestrator.parallel_peak_inflight >= 2")

    window_size = orchestrator["dispatch_plan"]["windowing"]["window_size"]
    if orchestrator["parallel_peak_inflight"] < window_size:
        raise AssertionError(
            "Expected orchestrator.parallel_peak_inflight >= dispatch_plan.windowing.window_size"
        )

    phases = orchestrator.get("review_phases", [])
    assert_any(
        lambda p: p.get("phase") == "dispatch_safety" and p.get("status") == "pass",
        phases,
        "Expected a passing review_phases entry for phase=dispatch_safety",
    )
    if suite_name == "write":
        assert_any(
            lambda p: p.get("phase") == "integration" and p.get("status") == "pass",
            phases,
            "Expected a passing review_phases entry for phase=integration",
        )
    else:
        assert_any(
            lambda p: p.get("phase") == "finalization" and p.get("status") == "pass",
            phases,
            "Expected a passing review_phases entry for phase=finalization",
        )

    slices = orchestrator["dispatch_plan"]["slices"]
    review_loop = orchestrator["review_loop"]
    assert_equal(
        review_loop["policy"],
        REVIEW_LOOP_POLICY,
        "orchestrator.review_loop.policy",
    )
    self_passes = review_loop["self_passes"]
    if not (REVIEW_LOOP_PASSES_MIN <= self_passes <= REVIEW_LOOP_PASSES_MAX):
        raise AssertionError(
            "orchestrator.review_loop.self_passes must be between "
            f"{REVIEW_LOOP_PASSES_MIN} and {REVIEW_LOOP_PASSES_MAX} inclusive"
        )

    if suite_name != "write":
        if orchestrator.get("coder_subtask_ids"):
            raise AssertionError(
                "Expected orchestrator.coder_subtask_ids to be empty for read_only workflows"
            )
        if any(
            s.get("leaf_agent_type") in {"coder_spark", "coder_codex"} for s in slices
        ):
            raise AssertionError(
                "Expected dispatch_plan.slices[*].leaf_agent_type == 'operator' for read_only workflows"
            )

    ownership_sets = [set(s["ownership_paths"]) for s in slices]
    for i in range(len(ownership_sets)):
        for j in range(i + 1, len(ownership_sets)):
            overlap = ownership_sets[i].intersection(ownership_sets[j])
            if overlap:
                raise AssertionError(
                    f"Ownership overlap between slices: {sorted(overlap)}"
                )


def assert_auditor_invariants(auditor: dict) -> None:
    assert_equal(auditor["verdict"], "PASS", "auditor.verdict")
    review_loop = auditor["review_loop"]
    assert_equal(
        review_loop["policy"],
        REVIEW_LOOP_POLICY,
        "auditor.review_loop.policy",
    )
    auditor_passes = review_loop["auditor_passes"]
    if not (REVIEW_LOOP_PASSES_MIN <= auditor_passes <= REVIEW_LOOP_PASSES_MAX):
        raise AssertionError(
            "auditor.review_loop.auditor_passes must be between "
            f"{REVIEW_LOOP_PASSES_MIN} and {REVIEW_LOOP_PASSES_MAX} inclusive"
        )
    orch_passes = review_loop["orchestrator_self_passes"]
    if not (REVIEW_LOOP_PASSES_MIN <= orch_passes <= REVIEW_LOOP_PASSES_MAX):
        raise AssertionError(
            "auditor.review_loop.orchestrator_self_passes must be between "
            f"{REVIEW_LOOP_PASSES_MIN} and {REVIEW_LOOP_PASSES_MAX} inclusive"
        )
    phases = auditor["audit_phases"]
    # Schema enforces ordering via prefixItems; assert statuses for fixtures.
    assert_equal(phases[0]["phase"], "spec", "auditor.audit_phases[0].phase")
    assert_equal(phases[1]["phase"], "quality", "auditor.audit_phases[1].phase")
    assert_equal(phases[0]["status"], "pass", "auditor.audit_phases[0].status")
    assert_equal(phases[1]["status"], "pass", "auditor.audit_phases[1].status")


def assert_coder_invariants(coder: dict) -> None:
    touched = coder["changeset"]["touched_paths"]
    allowed = coder["allowed_paths"]
    for p in touched:
        if not is_within_allowed_paths(p, allowed):
            raise AssertionError(
                f"Coder touched path outside allowed_paths: {p!r} not within {allowed!r}"
            )


def assert_operator_invariants(operator: dict) -> None:
    contract = operator["task_contract"]
    if contract.get("writes_repo") is not False:
        raise AssertionError("Expected operator.task_contract.writes_repo == false")

    actions = operator.get("actions", [])
    if not actions:
        raise AssertionError("Expected operator.actions to be non-empty")

    for action in actions:
        if not action.get("evidence"):
            raise AssertionError("Expected operator.actions[*].evidence to be non-empty")


def assert_orchestrator_slice_alignment(orchestrator: dict) -> None:
    slices = orchestrator["dispatch_plan"]["slices"]
    slice_leaf_ids = [s["leaf_subtask_id"] for s in slices]
    if len(slice_leaf_ids) != len(set(slice_leaf_ids)):
        raise AssertionError("dispatch_plan.slices leaf_subtask_id values must be unique")

    coder_from_slices = {
        s["leaf_subtask_id"]
        for s in slices
        if s.get("leaf_agent_type") in {"coder_spark", "coder_codex"}
    }
    ops_from_slices = {
        s["leaf_subtask_id"] for s in slices if s.get("leaf_agent_type") == "operator"
    }
    assert_equal(
        set(orchestrator["coder_subtask_ids"]),
        coder_from_slices,
        "orchestrator.coder_subtask_ids vs slices",
    )
    assert_equal(
        set(orchestrator["operator_subtask_ids"]),
        ops_from_slices,
        "orchestrator.operator_subtask_ids vs slices",
    )


def assert_cross_payload_invariants(
    dispatch: dict,
    orchestrator: dict,
    auditor: dict,
    coders: list[dict],
    operators: list[dict],
) -> None:
    ssot_id = dispatch["ssot_id"]
    try:
        subtask = next(
            s
            for s in dispatch["subtasks"]
            if s["subtask_id"] == orchestrator["subtask_id"]
        )
    except StopIteration:
        raise AssertionError(
            "dispatch.subtasks does not contain orchestrator.subtask_id"
        ) from None
    task_id = subtask["task_id"]
    subtask_id = subtask["subtask_id"]

    assert_equal(orchestrator["ssot_id"], ssot_id, "orchestrator.ssot_id")
    assert_equal(auditor["ssot_id"], ssot_id, "auditor.ssot_id")
    for coder in coders:
        assert_equal(coder["ssot_id"], ssot_id, "coder.ssot_id")
    for op in operators:
        assert_equal(op["ssot_id"], ssot_id, "operator.ssot_id")

    assert_equal(orchestrator["task_id"], task_id, "orchestrator.task_id")
    assert_equal(auditor["task_id"], task_id, "auditor.task_id")
    for coder in coders:
        assert_equal(coder["task_id"], task_id, "coder.task_id")
    for op in operators:
        assert_equal(op["task_id"], task_id, "operator.task_id")

    assert_equal(orchestrator["subtask_id"], subtask_id, "orchestrator.subtask_id")
    assert_equal(auditor["subtask_id"], subtask_id, "auditor.subtask_id")

    coder_ids = {coder["subtask_id"] for coder in coders}
    assert_equal(
        set(orchestrator["coder_subtask_ids"]),
        coder_ids,
        "orchestrator.coder_subtask_ids",
    )
    assert_equal(
        set(auditor["coder_subtask_ids"]),
        coder_ids,
        "auditor.coder_subtask_ids",
    )

    op_ids = {op["subtask_id"] for op in operators}
    assert_equal(
        set(orchestrator["operator_subtask_ids"]),
        op_ids,
        "orchestrator.operator_subtask_ids",
    )
    assert_equal(
        set(auditor["operator_subtask_ids"]),
        op_ids,
        "auditor.operator_subtask_ids",
    )
    assert_orchestrator_slice_alignment(orchestrator)
    if auditor["review_loop"]["auditor_passes"] > dispatch["review_policy"]["auditor_passes_max"]:
        raise AssertionError(
            "auditor.review_loop.auditor_passes must not exceed dispatch.review_policy.auditor_passes_max"
        )


def assert_negative_invariants_examples(
    *,
    suite_name: str,
    dispatch: dict,
    orchestrator: dict,
    auditor: dict,
    coders: list[dict],
    operators: list[dict],
) -> None:
    # review_loop policy + budget must be enforced.
    bad_orch_policy = json.loads(json.dumps(orchestrator))
    bad_orch_policy["review_loop"]["policy"] = "bad_policy"
    try:
        assert_orchestrator_invariants(bad_orch_policy, suite_name=suite_name)
    except AssertionError:
        pass
    else:
        raise AssertionError("Negative test failed: bad orchestrator review_loop.policy not detected")

    bad_orch_passes = json.loads(json.dumps(orchestrator))
    bad_orch_passes["review_loop"]["self_passes"] = REVIEW_LOOP_PASSES_MAX + 1
    try:
        assert_orchestrator_invariants(bad_orch_passes, suite_name=suite_name)
    except AssertionError:
        pass
    else:
        raise AssertionError("Negative test failed: orchestrator review_loop.self_passes out of range not detected")

    bad_audit_passes = json.loads(json.dumps(auditor))
    bad_audit_passes["review_loop"]["auditor_passes"] = REVIEW_LOOP_PASSES_MAX + 1
    try:
        assert_auditor_invariants(bad_audit_passes)
    except AssertionError:
        pass
    else:
        raise AssertionError("Negative test failed: auditor review_loop.auditor_passes out of range not detected")

    # Ownership overlap must fail.
    bad_orch = json.loads(json.dumps(orchestrator))
    if len(bad_orch["dispatch_plan"]["slices"]) >= 2:
        bad_orch["dispatch_plan"]["slices"][1]["ownership_paths"] = bad_orch[
            "dispatch_plan"
        ]["slices"][0]["ownership_paths"]
        try:
            assert_orchestrator_invariants(bad_orch, suite_name=suite_name)
        except AssertionError:
            pass
        else:
            raise AssertionError("Negative test failed: ownership overlap not detected")

    # parallel_peak_inflight too low must fail.
    bad_orch2 = json.loads(json.dumps(orchestrator))
    bad_orch2["parallel_peak_inflight"] = 1
    try:
        assert_orchestrator_invariants(bad_orch2, suite_name=suite_name)
    except AssertionError:
        pass
    else:
        raise AssertionError(
            "Negative test failed: parallel_peak_inflight < 2 not detected"
        )

    # Coder touched path outside allowed_paths must fail.
    if coders:
        bad_coder = json.loads(json.dumps(coders[0]))
        bad_coder["changeset"]["touched_paths"] = bad_coder["changeset"][
            "touched_paths"
        ] + ["/abs/repo/fixture/outside"]
        try:
            assert_coder_invariants(bad_coder)
        except AssertionError:
            pass
        else:
            raise AssertionError(
                "Negative test failed: coder touched_paths outside allowed_paths not detected"
            )

    # Operator writes_repo must be false.
    if operators:
        bad_op = json.loads(json.dumps(operators[0]))
        bad_op["task_contract"]["writes_repo"] = True
        try:
            assert_operator_invariants(bad_op)
        except AssertionError:
            pass
        else:
            raise AssertionError(
                "Negative test failed: operator writes_repo=true not detected"
            )

    # Orchestrator subtask id lists must match slices.
    bad_orch3 = json.loads(json.dumps(orchestrator))
    if bad_orch3.get("operator_subtask_ids"):
        bad_orch3["operator_subtask_ids"] = bad_orch3["operator_subtask_ids"][:-1]
        try:
            assert_orchestrator_slice_alignment(bad_orch3)
        except AssertionError:
            pass
        else:
            raise AssertionError(
                "Negative test failed: orchestrator operator_subtask_ids mismatch not detected"
            )

    if suite_name != "write":
        # read_only workflows must not dispatch coders.
        bad_orch_ro = json.loads(json.dumps(orchestrator))
        if bad_orch_ro["dispatch_plan"]["slices"]:
            bad_orch_ro["dispatch_plan"]["slices"][0]["leaf_agent_type"] = "coder_spark"
            try:
                assert_orchestrator_invariants(bad_orch_ro, suite_name=suite_name)
            except AssertionError:
                pass
            else:
                raise AssertionError(
                    "Negative test failed: read_only coder dispatch not detected"
                )


def main() -> None:
    suites = [
        {
            "name": "write",
            "payloads": {
                "dispatch-preflight.json": "schemas/dispatch-preflight.schema.json",
                "orchestrator-write.json": "schemas/agent-output.orchestrator.write.schema.json",
                "auditor-write.json": "schemas/agent-output.auditor.write.schema.json",
                "coder-1.json": "schemas/agent-output.coder.schema.json",
                "coder-2.json": "schemas/agent-output.coder.schema.json",
                "operator-write-1.json": "schemas/agent-output.operator.schema.json",
            },
            "orchestrator_payload": "orchestrator-write.json",
            "auditor_payload": "auditor-write.json",
            "dispatch_payload": "dispatch-preflight.json",
            "coder_payloads": ["coder-1.json", "coder-2.json"],
            "operator_payloads": ["operator-write-1.json"],
        },
        {
            "name": "non_write_ops",
            "payloads": {
                "dispatch-preflight-research.json": "schemas/dispatch-preflight.schema.json",
                "orchestrator-read_only-research.json": "schemas/agent-output.orchestrator.read_only.schema.json",
                "auditor-read_only-research.json": "schemas/agent-output.auditor.read_only.schema.json",
                "operator-1.json": "schemas/agent-output.operator.schema.json",
                "operator-2.json": "schemas/agent-output.operator.schema.json",
            },
            "orchestrator_payload": "orchestrator-read_only-research.json",
            "auditor_payload": "auditor-read_only-research.json",
            "dispatch_payload": "dispatch-preflight-research.json",
            "coder_payloads": [],
            "operator_payloads": ["operator-1.json", "operator-2.json"],
        },
    ]

    for suite in suites:
        loaded: dict[str, dict] = {}
        for payload_name, schema_rel in suite["payloads"].items():
            payload = load_json(E2E_DIR / payload_name)
            loaded[payload_name] = payload
            validate(ROOT / schema_rel, payload, payload_name)

        dispatch = loaded[suite["dispatch_payload"]]
        orchestrator = loaded[suite["orchestrator_payload"]]
        auditor = loaded[suite["auditor_payload"]]
        coders = [loaded[p] for p in suite.get("coder_payloads", [])]
        operators = [loaded[p] for p in suite["operator_payloads"]]

        assert_dispatch_preflight_invariants(dispatch)
        assert_orchestrator_invariants(orchestrator, suite_name=suite["name"])
        assert_auditor_invariants(auditor)
        for coder in coders:
            assert_coder_invariants(coder)
        for op in operators:
            assert_operator_invariants(op)
        assert_cross_payload_invariants(
            dispatch, orchestrator, auditor, coders, operators
        )

        if suite["name"] == "write":
            assert_negative_invariants_examples(
                suite_name=suite["name"],
                dispatch=dispatch,
                orchestrator=orchestrator,
                auditor=auditor,
                coders=coders,
                operators=operators,
            )
        else:
            assert_negative_invariants_examples(
                suite_name=suite["name"],
                dispatch=dispatch,
                orchestrator=orchestrator,
                auditor=auditor,
                coders=coders,
                operators=operators,
            )

        print(f"OK: invariants ({suite['name']})")


if __name__ == "__main__":
    main()
