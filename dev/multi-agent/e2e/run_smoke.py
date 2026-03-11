import subprocess
import sys
from pathlib import Path

from schema_support import SCHEMAS_DIR, iter_schema_paths, load_json, validator_for_schema

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_DIR = Path(__file__).resolve().parent
BACKTESTS_DIR = E2E_DIR.parent / "backtests"


def validate_schema_and_examples(schema_path: Path) -> None:
    schema = load_json(schema_path)
    validator = validator_for_schema(schema)
    for index, example in enumerate(schema.get("examples", []), 1):
        errors = list(validator.iter_errors(example))
        if errors:
            messages = "; ".join(error.message for error in errors[:5])
            raise AssertionError(
                f"{schema_path.relative_to(REPO_ROOT)} example #{index} invalid: {messages}"
            )


def run_step(path: Path) -> None:
    proc = subprocess.run([sys.executable, str(path)], check=False, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> None:
    schema_files = iter_schema_paths()
    if not schema_files:
        raise AssertionError(f"No schema files found under {SCHEMAS_DIR}")

    for schema_path in schema_files:
        validate_schema_and_examples(schema_path)
        print(f"OK: schema + examples ({schema_path.relative_to(REPO_ROOT)})")

    run_step(E2E_DIR / "validate_doc_templates.py")
    run_step(E2E_DIR / "validate_broker_e2e.py")
    run_step(E2E_DIR / "validate_payloads.py")
    run_step(BACKTESTS_DIR / "run_backtests.py")

    print("OK: e2e fixtures + broker docs + backtests")


if __name__ == "__main__":
    main()
