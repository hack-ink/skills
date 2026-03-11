from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "multi-agent"
SCHEMAS_DIR = SKILL_ROOT / "schemas"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


@dataclass(frozen=True)
class SchemaCatalog:
    schemas_by_id: dict[str, dict[str, Any]]
    schema_paths_by_id: dict[str, Path]
    registry: Registry


@cache
def load_schema_catalog() -> SchemaCatalog:
    schemas_by_id: dict[str, dict[str, Any]] = {}
    schema_paths_by_id: dict[str, Path] = {}

    for schema_path in sorted(SCHEMAS_DIR.glob("*.json")):
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise AssertionError(f"{schema_path} is missing a string $id")
        if schema_id in schemas_by_id:
            raise AssertionError(f"duplicate schema id detected: {schema_id}")
        schemas_by_id[schema_id] = schema
        schema_paths_by_id[schema_id] = schema_path

    if not schemas_by_id:
        raise AssertionError(f"No schema files found under {SCHEMAS_DIR}")

    def retrieve(uri: str) -> Resource[dict[str, Any]]:
        schema = schemas_by_id.get(uri)
        if schema is not None:
            return Resource.from_contents(schema)
        raise NoSuchResource(ref=uri)

    registry = Registry(retrieve=retrieve)
    for schema_id, schema in schemas_by_id.items():
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))

    return SchemaCatalog(
        schemas_by_id=schemas_by_id,
        schema_paths_by_id=schema_paths_by_id,
        registry=registry,
    )


def iter_schema_paths() -> list[Path]:
    return sorted(load_schema_catalog().schema_paths_by_id.values())


def schema_for_id(schema_id: str) -> dict[str, Any]:
    catalog = load_schema_catalog()
    try:
        return catalog.schemas_by_id[schema_id]
    except KeyError as exc:
        known = ", ".join(sorted(catalog.schemas_by_id))
        raise AssertionError(
            f"unknown schema id {schema_id!r} (known: {known})"
        ) from exc


def schema_path_for_id(schema_id: str) -> Path:
    catalog = load_schema_catalog()
    try:
        return catalog.schema_paths_by_id[schema_id]
    except KeyError as exc:
        known = ", ".join(sorted(catalog.schema_paths_by_id))
        raise AssertionError(
            f"unknown schema id {schema_id!r} (known: {known})"
        ) from exc


def validator_for_schema(schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema, registry=load_schema_catalog().registry)


def validator_for_id(schema_id: str) -> Draft202012Validator:
    return validator_for_schema(schema_for_id(schema_id))


def validators_by_id() -> dict[str, Draft202012Validator]:
    catalog = load_schema_catalog()
    return {
      schema_id: Draft202012Validator(schema, registry=catalog.registry)
      for schema_id, schema in catalog.schemas_by_id.items()
    }
