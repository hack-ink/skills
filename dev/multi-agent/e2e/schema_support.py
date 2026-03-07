from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin

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
    schema_aliases_by_uri: dict[str, str]
    registry: Registry


def iter_schema_refs(value: Any) -> list[str]:
    refs: list[str] = []

    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            refs.append(ref)
        for nested in value.values():
            refs.extend(iter_schema_refs(nested))
        return refs

    if isinstance(value, list):
        for item in value:
            refs.extend(iter_schema_refs(item))

    return refs


def build_schema_aliases(
    schemas_by_id: dict[str, dict[str, Any]],
) -> dict[str, str]:
    aliases: dict[str, str] = {}

    for schema_id, schema in schemas_by_id.items():
        for ref in iter_schema_refs(schema):
            resource_uri, _fragment = urldefrag(ref)
            if not resource_uri or resource_uri not in schemas_by_id:
                continue

            resolved_uri = urljoin(schema_id, resource_uri)
            if resolved_uri == resource_uri:
                continue
            if resolved_uri in schemas_by_id:
                raise AssertionError(
                    "schema alias collides with concrete schema id: "
                    f"{resolved_uri}"
                )

            existing = aliases.get(resolved_uri)
            if existing is not None and existing != resource_uri:
                raise AssertionError(
                    f"conflicting schema alias for {resolved_uri!r}: "
                    f"{existing!r} vs {resource_uri!r}"
                )
            aliases[resolved_uri] = resource_uri

    return aliases


@cache
def load_schema_catalog() -> SchemaCatalog:
    schemas_by_id: dict[str, dict[str, Any]] = {}
    schema_paths_by_id: dict[str, Path] = {}

    for schema_path in sorted(SCHEMAS_DIR.glob("*.json")):
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)

        schema_id = schema.get("$id")
        if not schema_id or not isinstance(schema_id, str):
            raise AssertionError(f"{schema_path} is missing string $id")
        if schema_id in schemas_by_id:
            raise AssertionError(f"duplicate schema id detected: {schema_id}")

        schemas_by_id[schema_id] = schema
        schema_paths_by_id[schema_id] = schema_path

    if not schemas_by_id:
        raise AssertionError(f"No schema files found under {SCHEMAS_DIR}")

    schema_aliases_by_uri = build_schema_aliases(schemas_by_id)

    def retrieve(uri: str) -> Resource[dict[str, Any]]:
        target_schema_id = schema_aliases_by_uri.get(uri, uri)
        schema = schemas_by_id.get(target_schema_id)
        if schema is not None:
            return Resource.from_contents(schema)

        raise NoSuchResource(ref=uri)

    registry = Registry(retrieve=retrieve)
    for schema_id, schema in schemas_by_id.items():
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return SchemaCatalog(
        schemas_by_id=schemas_by_id,
        schema_paths_by_id=schema_paths_by_id,
        schema_aliases_by_uri=schema_aliases_by_uri,
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
