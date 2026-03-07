import json
import subprocess
import sys
from pathlib import Path

from schema_support import (
    SCHEMAS_DIR,
    SKILL_ROOT,
    iter_schema_paths,
    load_json,
    validator_for_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_DIR = Path(__file__).resolve().parent
BACKTESTS_DIR = E2E_DIR.parent / "backtests"

def validate_schema_and_examples(schema_path: Path) -> None:
    schema = load_json(schema_path)
    v = validator_for_schema(schema)
    for i, ex in enumerate(schema.get("examples", []), 1):
        errs = list(v.iter_errors(ex))
        if errs:
            messages = "; ".join(e.message for e in errs[:5])
            raise AssertionError(
                f"{schema_path.relative_to(SKILL_ROOT)} example #{i} invalid: {messages}"
            )


def main() -> None:
    schema_files = iter_schema_paths()
    if not schema_files:
        raise AssertionError(f"No schema files found under {SCHEMAS_DIR}")

    for f in schema_files:
        validate_schema_and_examples(f)
        print(f"OK: schema + examples ({f.relative_to(SKILL_ROOT)})")

    proc = subprocess.run(
        [sys.executable, str(E2E_DIR / "validate_doc_templates.py")],
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    proc = subprocess.run(
        [sys.executable, str(E2E_DIR / "validate_broker_e2e.py")],
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    proc = subprocess.run(
        [sys.executable, str(E2E_DIR / "validate_payloads.py")],
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    proc = subprocess.run(
        [sys.executable, str(BACKTESTS_DIR / "run_backtests.py")],
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    print("OK: e2e fixtures + invariants + backtests")


if __name__ == "__main__":
    main()
