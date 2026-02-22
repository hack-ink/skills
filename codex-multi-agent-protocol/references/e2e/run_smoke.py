import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "schemas"
E2E_DIR = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def validate_schema_and_examples(schema_path: Path) -> None:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    for i, ex in enumerate(schema.get("examples", []), 1):
        errs = list(v.iter_errors(ex))
        if errs:
            messages = "; ".join(e.message for e in errs[:5])
            raise AssertionError(
                f"{schema_path.relative_to(ROOT)} example #{i} invalid: {messages}"
            )


def main() -> None:
    schema_files = sorted(SCHEMAS_DIR.glob("*.json"))
    if not schema_files:
        raise AssertionError(f"No schema files found under {SCHEMAS_DIR}")

    for f in schema_files:
        validate_schema_and_examples(f)
        print(f"OK: schema + examples ({f.relative_to(ROOT)})")

    proc = subprocess.run(
        [sys.executable, str(E2E_DIR / "validate_payloads.py")],
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    print("OK: e2e fixtures + invariants")


if __name__ == "__main__":
    main()
