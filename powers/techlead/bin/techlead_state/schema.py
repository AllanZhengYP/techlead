"""Small JSON Schema evaluator for the protocol schema vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


@dataclass(frozen=True)
class SchemaIssue:
    path: str
    message: str


def validate_schema(instance: Any, schema: dict[str, Any], *, path: str = "$") -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []
    expected = schema.get("type")
    if expected is not None and not _matches_type(instance, expected):
        issues.append(SchemaIssue(path, f"expected type {_describe_type(expected)}, got {_type_name(instance)}"))
        return issues

    if "const" in schema and instance != schema["const"]:
        issues.append(SchemaIssue(path, f"must equal {schema['const']!r}"))
    if "enum" in schema and instance not in schema["enum"]:
        issues.append(SchemaIssue(path, f"must be one of {schema['enum']!r}"))

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                issues.append(SchemaIssue(f"{path}.{key}", "is required"))
        properties = schema.get("properties", {})
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            child_schema = properties.get(key)
            if child_schema is None:
                if schema.get("additionalProperties") is False:
                    issues.append(SchemaIssue(child_path, "is not an allowed property"))
                continue
            issues.extend(validate_schema(value, child_schema, path=child_path))

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            issues.append(SchemaIssue(path, f"must contain at least {schema['minItems']} item(s)"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            issues.append(SchemaIssue(path, f"must contain at most {schema['maxItems']} item(s)"))
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in instance]
            if len(encoded) != len(set(encoded)):
                issues.append(SchemaIssue(path, "must contain unique items"))
        if "items" in schema:
            for index, value in enumerate(instance):
                issues.extend(validate_schema(value, schema["items"], path=f"{path}[{index}]"))

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            issues.append(SchemaIssue(path, f"must contain at least {schema['minLength']} character(s)"))
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, instance) is None:
            issues.append(SchemaIssue(path, f"must match {pattern!r}"))

    return issues


def _matches_type(instance: Any, expected: str | list[str]) -> bool:
    choices = [expected] if isinstance(expected, str) else expected
    return any(_is_type(instance, choice) for choice in choices)


def _is_type(instance: Any, expected: str) -> bool:
    return {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
        "null": lambda value: value is None,
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    }.get(expected, lambda _value: False)(instance)


def _describe_type(expected: str | list[str]) -> str:
    return expected if isinstance(expected, str) else " or ".join(expected)


def _type_name(instance: Any) -> str:
    if instance is None:
        return "null"
    if isinstance(instance, bool):
        return "boolean"
    if isinstance(instance, dict):
        return "object"
    if isinstance(instance, list):
        return "array"
    if isinstance(instance, str):
        return "string"
    if isinstance(instance, int):
        return "integer"
    if isinstance(instance, float):
        return "number"
    return type(instance).__name__
