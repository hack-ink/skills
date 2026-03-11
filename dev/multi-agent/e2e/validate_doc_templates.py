import json
import re
from pathlib import Path

from schema_support import SKILL_ROOT, validators_by_id

JSON_FENCE_RE = re.compile(r"```\s*json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def iter_json_blocks(text: str) -> list[str]:
    return [match.group(1) for match in JSON_FENCE_RE.finditer(text)]


def iter_markdown_docs(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def validate_payload(payload: object, validators: dict[str, object], label: str) -> None:
    if not isinstance(payload, dict):
        raise AssertionError(f"{label}: expected a JSON object")

    schema_id = payload.get("schema")
    if not isinstance(schema_id, str) or not schema_id:
        raise AssertionError(f"{label}: missing string field 'schema'")

    validator = validators.get(schema_id)
    if validator is None:
        known = ", ".join(sorted(validators))
        raise AssertionError(f"{label}: unknown schema {schema_id!r} (known: {known})")

    errors = list(validator.iter_errors(payload))
    if errors:
        messages = "; ".join(error.message for error in errors[:5])
        raise AssertionError(f"{label}: {messages}")


def main() -> None:
    validators = validators_by_id()
    doc_files = iter_markdown_docs(SKILL_ROOT)
    total_blocks = 0
    files_with_blocks = 0

    for md_path in doc_files:
        rel_path = md_path.relative_to(SKILL_ROOT)
        blocks = iter_json_blocks(md_path.read_text())
        if blocks:
            files_with_blocks += 1
            print(f"INFO: scanning {rel_path} ({len(blocks)} json block(s))")
        for index, block in enumerate(blocks, 1):
            total_blocks += 1
            try:
                payload = json.loads(block)
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"{rel_path} json block #{index} invalid JSON: {exc}"
                ) from exc
            validate_payload(payload, validators, f"{rel_path} json block #{index}")

    if total_blocks == 0:
        raise AssertionError(
            "No ```json templates found in multi-agent docs (expected at least one)"
        )

    print(
        "OK: doc templates "
        f"({total_blocks} json blocks across {files_with_blocks} markdown files)"
    )


if __name__ == "__main__":
    main()
