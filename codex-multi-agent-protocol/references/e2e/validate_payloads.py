import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = Path(__file__).resolve().parent


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
    assert_equal(
        dispatch["review_policy"]["phase_order"],
        ["spec", "quality"],
        "dispatch.review_policy.phase_order",
    )
    assert_equal(
        dispatch["parallel_policy"]["conflict_policy"],
        "ownership_lock",
        "dispatch.parallel_policy.conflict_policy",
    )
    assert_equal(
        dispatch["parallel_policy"]["wait_strategy"],
        "wait_any",
        "dispatch.parallel_policy.wait_strategy",
    )


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
    ownership_sets = [set(s["ownership_paths"]) for s in slices]
    for i in range(len(ownership_sets)):
        for j in range(i + 1, len(ownership_sets)):
            overlap = ownership_sets[i].intersection(ownership_sets[j])
            if overlap:
                raise AssertionError(
                    f"Ownership overlap between slices: {sorted(overlap)}"
                )


def assert_auditor_invariants(auditor: dict) -> None:
    phases = auditor["audit_phases"]
    # Schema enforces ordering via prefixItems; assert statuses for fixtures.
    assert_equal(phases[0]["phase"], "spec", "auditor.audit_phases[0].phase")
    assert_equal(phases[1]["phase"], "quality", "auditor.audit_phases[1].phase")
    assert_equal(phases[0]["status"], "pass", "auditor.audit_phases[0].status")
    assert_equal(phases[1]["status"], "pass", "auditor.audit_phases[1].status")


def assert_implementer_invariants(implementer: dict) -> None:
    touched = implementer["changeset"]["touched_paths"]
    allowed = implementer["allowed_paths"]
    for p in touched:
        if not is_within_allowed_paths(p, allowed):
            raise AssertionError(
                f"Implementer touched path outside allowed_paths: {p!r} not within {allowed!r}"
            )


def assert_cross_payload_invariants(
    dispatch: dict, orchestrator: dict, auditor: dict, implementers: list[dict]
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
    for impl in implementers:
        assert_equal(impl["ssot_id"], ssot_id, "implementer.ssot_id")

    assert_equal(orchestrator["task_id"], task_id, "orchestrator.task_id")
    assert_equal(auditor["task_id"], task_id, "auditor.task_id")
    for impl in implementers:
        assert_equal(impl["task_id"], task_id, "implementer.task_id")

    assert_equal(orchestrator["subtask_id"], subtask_id, "orchestrator.subtask_id")
    assert_equal(auditor["subtask_id"], subtask_id, "auditor.subtask_id")

    impl_ids = {impl["subtask_id"] for impl in implementers}
    assert_equal(
        set(orchestrator["implementer_subtask_ids"]),
        impl_ids,
        "orchestrator.implementer_subtask_ids",
    )
    assert_equal(
        set(auditor["implementer_subtask_ids"]),
        impl_ids,
        "auditor.implementer_subtask_ids",
    )


def assert_negative_invariants_examples(
    dispatch: dict, orchestrator: dict, implementers: list[dict]
) -> None:
    # Ownership overlap must fail.
    bad_orch = json.loads(json.dumps(orchestrator))
    if len(bad_orch["dispatch_plan"]["slices"]) >= 2:
        bad_orch["dispatch_plan"]["slices"][1]["ownership_paths"] = bad_orch[
            "dispatch_plan"
        ]["slices"][0]["ownership_paths"]
        try:
            assert_orchestrator_invariants(bad_orch, suite_name="write")
        except AssertionError:
            pass
        else:
            raise AssertionError("Negative test failed: ownership overlap not detected")

    # parallel_peak_inflight too low must fail.
    bad_orch2 = json.loads(json.dumps(orchestrator))
    bad_orch2["parallel_peak_inflight"] = 1
    try:
        assert_orchestrator_invariants(bad_orch2, suite_name="write")
    except AssertionError:
        pass
    else:
        raise AssertionError(
            "Negative test failed: parallel_peak_inflight < 2 not detected"
        )

    # Implementer touched path outside allowed_paths must fail.
    if implementers:
        bad_impl = json.loads(json.dumps(implementers[0]))
        bad_impl["changeset"]["touched_paths"] = bad_impl["changeset"][
            "touched_paths"
        ] + ["/abs/repo/fixture/outside"]
        try:
            assert_implementer_invariants(bad_impl)
        except AssertionError:
            pass
        else:
            raise AssertionError(
                "Negative test failed: implementer touched_paths outside allowed_paths not detected"
            )


def main() -> None:
    suites = [
        {
            "name": "write",
            "payloads": {
                "dispatch-preflight.json": "schemas/dispatch-preflight.schema.json",
                "orchestrator-write.json": "schemas/agent-output.orchestrator.write.schema.json",
                "auditor-write.json": "schemas/agent-output.auditor.write.schema.json",
                "implementer-1.json": "schemas/agent-output.implementer.schema.json",
                "implementer-2.json": "schemas/agent-output.implementer.schema.json",
            },
            "orchestrator_payload": "orchestrator-write.json",
            "auditor_payload": "auditor-write.json",
            "dispatch_payload": "dispatch-preflight.json",
            "implementer_payloads": ["implementer-1.json", "implementer-2.json"],
        },
        {
            "name": "read_only_research",
            "payloads": {
                "dispatch-preflight-research.json": "schemas/dispatch-preflight.schema.json",
                "orchestrator-read_only-research.json": "schemas/agent-output.orchestrator.read_only.schema.json",
                "auditor-read_only-research.json": "schemas/agent-output.auditor.read_only.schema.json",
                "implementer-research-1.json": "schemas/agent-output.implementer.schema.json",
                "implementer-research-2.json": "schemas/agent-output.implementer.schema.json",
            },
            "orchestrator_payload": "orchestrator-read_only-research.json",
            "auditor_payload": "auditor-read_only-research.json",
            "dispatch_payload": "dispatch-preflight-research.json",
            "implementer_payloads": [
                "implementer-research-1.json",
                "implementer-research-2.json",
            ],
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
        implementers = [loaded[p] for p in suite["implementer_payloads"]]

        assert_dispatch_preflight_invariants(dispatch)
        assert_orchestrator_invariants(orchestrator, suite_name=suite["name"])
        assert_auditor_invariants(auditor)
        for impl in implementers:
            assert_implementer_invariants(impl)
        assert_cross_payload_invariants(dispatch, orchestrator, auditor, implementers)

        if suite["name"] == "write":
            assert_negative_invariants_examples(dispatch, orchestrator, implementers)

        print(f"OK: invariants ({suite['name']})")


if __name__ == "__main__":
    main()
