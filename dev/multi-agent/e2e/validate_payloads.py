from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "multi-agent"
SCHEMAS_DIR = SKILL_ROOT / "schemas"
E2E_DIR = Path(__file__).resolve().parent


def load_json(path: Path):
    text = path.read_text()
    stripped = text.strip()
    if stripped.startswith("```") or stripped.endswith("```"):
        raise AssertionError(
            f"{path.name}: worker output must be raw JSON only; code fences are not allowed"
        )
    return json.loads(stripped)

def validate_one(schema_path: Path, payload: dict, label: str) -> None:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    print(f"OK: {label} against {schema_path.relative_to(SKILL_ROOT)}")


def ssot_parts(ssot_id: str) -> tuple[str, str]:
    if "-" not in ssot_id:
        raise AssertionError("ssot_id must be scenario-hash: <scenario>-<hex>")
    scenario, token = ssot_id.rsplit("-", 1)
    return scenario, token


def assert_ssot_id_policy(ssot_id: str) -> None:
    scenario, token = ssot_parts(ssot_id)
    if not scenario:
        raise AssertionError("ssot_id scenario prefix must be non-empty")
    if not (8 <= len(token) <= 64):
        raise AssertionError("ssot_id token must be hex length 8..64")
    if any(c not in "0123456789abcdef" for c in token):
        raise AssertionError("ssot_id token must be lowercase hex")

    expected = hashlib.sha256(scenario.encode("utf-8")).hexdigest()[: len(token)]
    if token != expected:
        raise AssertionError(
            "ssot_id must use scenario-hash (sha256(scenario) prefix); "
            f"expected {scenario}-{expected}"
        )


def assert_json_only_output(payload: dict, path: Path) -> None:
    if not isinstance(payload, (dict, list)):
        raise AssertionError(f"{path.name}: output must be a JSON object or array")


def is_within(touched: str, allowed_paths: list[str]) -> bool:
    touched = touched.rstrip("/")
    for allowed in allowed_paths:
        a = allowed.rstrip("/")
        if touched == a:
            return True
        if touched.startswith(a + "/"):
            return True
    return False


def overlaps(a: str, b: str) -> bool:
    a = a.rstrip("/")
    b = b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def assert_no_forbidden_roles(payload: dict) -> None:
    agent_type = payload.get("agent_type")
    role = payload.get("role")
    forbidden = {"orchestrator", "director"}
    if agent_type in forbidden or role in forbidden:
        raise AssertionError(
            "Fixtures must not use forbidden roles (orchestrator/director)"
        )


def assert_coder_spark_timebox(payload: dict) -> None:
    if (
        payload.get("agent_type") == "coder_spark"
        and payload.get("slice_kind") == "work"
        and payload.get("timebox_minutes", 0) > 12
    ):
        raise AssertionError(
            f"{payload['slice_id']}: coder_spark+work must have timebox_minutes <= 12"
        )


def assert_supervisor_first_invariants(
    dispatches: list[dict], *, supervisor_slice_id: str, prefix: str
) -> None:
    slice_ids = [d["slice_id"] for d in dispatches]
    if len(slice_ids) != len(set(slice_ids)):
        duplicates = sorted(
            {sid for sid in slice_ids if slice_ids.count(sid) > 1}
        )
        raise AssertionError(
            "dispatches.workstreams.json has duplicate slice_id(s): "
            + ", ".join(duplicates)
        )

    non_prefix = [d["slice_id"] for d in dispatches if not d["slice_id"].startswith(prefix)]
    if non_prefix:
        raise AssertionError(
            "dispatches.workstreams.json slice_id prefix invariant failed for: "
            + ", ".join(non_prefix)
        )

    for d in dispatches:
        if d["slice_id"] == supervisor_slice_id:
            continue
        deps = d.get("dependencies", [])
        if supervisor_slice_id not in deps:
            raise AssertionError(
                f"{d['slice_id']}: non-plan dispatch must depend on {supervisor_slice_id}"
            )


def validate_dispatches(path: Path, expected_count: int) -> list[dict]:
    dispatches = load_json(path)
    if not isinstance(dispatches, list):
        raise AssertionError(f"{path.name} must be a JSON array")
    if len(dispatches) != expected_count:
        raise AssertionError(
            f"{path.name}: expected {expected_count} items, got {len(dispatches)}"
        )
    schema_path = SCHEMAS_DIR / "task-dispatch.schema.json"
    for i, d in enumerate(dispatches, 1):
        assert_no_forbidden_roles(d)
        validate_one(schema_path, d, f"{path.name}[{i}]")
        assert_ssot_id_policy(d["ssot_id"])
        assert_coder_spark_timebox(d)
    return dispatches


def validate_results() -> None:
    operator_schema = SCHEMAS_DIR / "worker-result.operator.schema.json"
    coder_schema = SCHEMAS_DIR / "worker-result.coder.schema.json"
    auditor_schema = SCHEMAS_DIR / "review-result.auditor.schema.json"
    supervisor_schema = SCHEMAS_DIR / "worker-result.supervisor.schema.json"
    dispatch_schema = SCHEMAS_DIR / "task-dispatch.schema.json"

    results = [
        ("result.operator.json", operator_schema),
        ("result.coder.json", coder_schema),
        ("result.auditor.pass.json", auditor_schema),
        ("result.auditor.block.json", auditor_schema),
        ("result.auditor.needs_evidence.json", auditor_schema),
        ("result.supervisor.plan.json", supervisor_schema),
        ("result.supervisor.integrate.json", supervisor_schema),
    ]
    for fname, schema_path in results:
        payload = load_json(E2E_DIR / fname)
        assert_no_forbidden_roles(payload)
        assert_json_only_output(payload, E2E_DIR / fname)
        validate_one(schema_path, payload, fname)
        assert_ssot_id_policy(payload["ssot_id"])

        if fname == "result.supervisor.plan.json":
            for i, d in enumerate(payload.get("dispatch_plan", []), 1):
                assert_no_forbidden_roles(d)
                validate_one(dispatch_schema, d, f"{fname}.dispatch_plan[{i}]")
                assert_coder_spark_timebox(d)
                assert_ssot_id_policy(d["ssot_id"])

    coder = load_json(E2E_DIR / "result.coder.json")
    for p in coder["changeset"]["touched_paths"]:
        if not is_within(p, coder["allowed_paths"]):
            raise AssertionError(
                f"result.coder.json: touched path {p!r} is outside allowed_paths"
            )


def assert_dispatch_invariants() -> None:
    read_only = validate_dispatches(
        E2E_DIR / "dispatches.read_only.json", expected_count=16
    )
    if any(d["agent_type"] != "operator" for d in read_only):
        raise AssertionError("read_only dispatches must use agent_type=operator only")
    if any(d["ownership_paths"] for d in read_only):
        raise AssertionError("read_only dispatches must have empty ownership_paths")

    write = validate_dispatches(E2E_DIR / "dispatches.write_mixed.json", expected_count=12)
    coders = [d for d in write if d["agent_type"] in ("coder_spark", "coder_codex")]
    ops = [d for d in write if d["agent_type"] == "operator"]
    if len(coders) != 6 or len(ops) != 6:
        raise AssertionError("write_mixed dispatches must be 6 coders + 6 operators")

    coder_ownership = []
    for d in coders:
        if not d["ownership_paths"]:
            raise AssertionError(f"{d['slice_id']}: coder must declare ownership_paths")
        if not d["allowed_paths"]:
            raise AssertionError(f"{d['slice_id']}: coder must declare allowed_paths")
        coder_ownership.append((d["slice_id"], d["ownership_paths"]))

    for i in range(len(coder_ownership)):
        a_id, a_paths = coder_ownership[i]
        for j in range(i + 1, len(coder_ownership)):
            b_id, b_paths = coder_ownership[j]
            for ap in a_paths:
                for bp in b_paths:
                    if overlaps(ap, bp):
                        raise AssertionError(
                            f"Ownership overlap between coder slices {a_id} and {b_id}: {ap!r} vs {bp!r}"
                        )

    workstreams = validate_dispatches(
        E2E_DIR / "dispatches.workstreams.json", expected_count=9
    )
    assert_supervisor_first_invariants(
        workstreams,
        supervisor_slice_id="ws2-dev--supervisor-plan",
        prefix="ws2-dev--",
    )


def main() -> None:
    assert_dispatch_invariants()
    validate_results()
    print("OK: fixtures + invariants (vNext)")


if __name__ == "__main__":
    main()
