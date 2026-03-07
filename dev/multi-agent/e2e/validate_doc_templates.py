import json
import re
import hashlib
from pathlib import Path

from schema_support import SKILL_ROOT, validators_by_id

JSON_FENCE_RE = re.compile(r"```\s*json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def iter_json_blocks(text: str) -> list[str]:
    return [m.group(1) for m in JSON_FENCE_RE.finditer(text)]


def iter_markdown_docs(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def validate_payload(payload: object, validators: dict[str, object], ctx: str) -> None:
    if isinstance(payload, list):
        for i, item in enumerate(payload, 1):
            validate_payload(item, validators, f"{ctx}[{i}]")
        return

    if not isinstance(payload, dict):
        raise AssertionError(f"{ctx}: top-level JSON must be an object or an array of objects")

    schema_id = payload.get("schema")
    if not schema_id or not isinstance(schema_id, str):
        raise AssertionError(f"{ctx}: missing string field 'schema'")

    v = validators.get(schema_id)
    if not v:
        known = ", ".join(sorted(validators.keys()))
        raise AssertionError(f"{ctx}: unknown schema '{schema_id}' (known: {known})")

    errs = list(v.iter_errors(payload))
    if errs:
        messages = "; ".join(e.message for e in errs[:5])
        raise AssertionError(f"{ctx}: {messages}")

    ssot_id = payload.get("ssot_id")
    if ssot_id is not None:
        if not isinstance(ssot_id, str) or "-" not in ssot_id:
            raise AssertionError(f"{ctx}: ssot_id must be scenario-hash: <scenario>-<hex>")
        scenario, token = ssot_id.rsplit("-", 1)
        if not scenario:
            raise AssertionError(f"{ctx}: ssot_id scenario prefix must be non-empty")
        if not (8 <= len(token) <= 64):
            raise AssertionError(f"{ctx}: ssot_id token must be hex length 8..64")
        if any(c not in "0123456789abcdef" for c in token):
            raise AssertionError(f"{ctx}: ssot_id token must be lowercase hex")
        expected = hashlib.sha256(scenario.encode("utf-8")).hexdigest()[: len(token)]
        if token != expected:
            raise AssertionError(f"{ctx}: ssot_id must use scenario-hash; expected {scenario}-{expected}")


def main() -> None:
    validators = validators_by_id()

    doc_files = iter_markdown_docs(SKILL_ROOT)
    if not doc_files:
        raise AssertionError(f"No markdown docs found under {SKILL_ROOT}")

    total_blocks = 0
    files_with_blocks = 0
    for md_path in doc_files:
        rel_path = md_path.relative_to(SKILL_ROOT)
        blocks = iter_json_blocks(md_path.read_text())
        if blocks:
            files_with_blocks += 1
            print(f"INFO: scanning {rel_path} ({len(blocks)} json block(s))")
        for i, block in enumerate(blocks, 1):
            total_blocks += 1
            try:
                payload = json.loads(block)
            except json.JSONDecodeError as e:
                raise AssertionError(
                    f"{rel_path} json block #{i} invalid JSON: {e}"
                ) from e
            validate_payload(payload, validators, f"{rel_path} json block #{i}")

    if total_blocks == 0:
        raise AssertionError("No ```json templates found in multi-agent docs (expected at least one)")

    print(
        "OK: doc templates "
        f"({total_blocks} json blocks across {files_with_blocks} markdown files; recursive scan)"
    )


if __name__ == "__main__":
    main()
