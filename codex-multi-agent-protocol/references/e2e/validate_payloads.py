import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
	return json.loads(path.read_text())


def validate(schema_path: Path, payload_path: Path) -> None:
	schema = load_json(schema_path)
	payload = load_json(payload_path)
	Draft202012Validator.check_schema(schema)
	Draft202012Validator(schema).validate(payload)
	print(f"OK: {payload_path.relative_to(ROOT)} against {schema_path.relative_to(ROOT)}")


def assert_invariants(orchestrator: dict) -> None:
	if orchestrator.get("parallel_peak_inflight", 0) < 2:
		raise AssertionError("Expected orchestrator.parallel_peak_inflight >= 2")

	slices = orchestrator["dispatch_plan"]["slices"]
	ownership_sets = [set(s["ownership_paths"]) for s in slices]
	for i in range(len(ownership_sets)):
		for j in range(i + 1, len(ownership_sets)):
			overlap = ownership_sets[i].intersection(ownership_sets[j])
			if overlap:
				raise AssertionError(f"Ownership overlap between slices: {sorted(overlap)}")


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
		},
	]

	for suite in suites:
		for payload_name, schema_rel in suite["payloads"].items():
			validate(ROOT / schema_rel, E2E_DIR / payload_name)

		orchestrator = load_json(E2E_DIR / suite["orchestrator_payload"])
		assert_invariants(orchestrator)
		print(f"OK: invariants ({suite['name']})")


if __name__ == "__main__":
	main()
