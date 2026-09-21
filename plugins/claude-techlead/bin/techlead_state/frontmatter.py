"""Dependency-free parser for the Tech Lead protocol's YAML subset."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


class FrontMatterError(ValueError):
    """Raised when a protocol document cannot be parsed deterministically."""


@dataclass(frozen=True)
class ParsedDocument:
    metadata: dict[str, Any]
    body: str


_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_INTEGER = re.compile(r"^-?(0|[1-9][0-9]*)$")


def parse_file(path: Path) -> ParsedDocument:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FrontMatterError(f"{path}: protocol records must be UTF-8") from exc
    return parse_document(text, source=str(path))


def parse_document(text: str, *, source: str = "<document>") -> ParsedDocument:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise FrontMatterError(f"{source}:1: expected opening '---'")

    end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        raise FrontMatterError(f"{source}: missing closing '---'")

    metadata = _parse_mapping(lines[1:end], source=source)
    return ParsedDocument(metadata=metadata, body="".join(lines[end + 1 :]))


def dump_document(metadata: dict[str, Any], body: str = "") -> str:
    """Render the deterministic YAML subset used by protocol records."""

    lines = ["---"]
    for key, value in metadata.items():
        if not _KEY.fullmatch(key):
            raise FrontMatterError(f"invalid key {key!r}")
        lines.append(f"{key}: {_dump_scalar(value)}")
    lines.append("---")
    rendered = "\n".join(lines) + "\n"
    if body:
        rendered += body if body.endswith("\n") else body + "\n"
    return rendered


def _parse_mapping(lines: list[str], *, source: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        raw = lines[index].rstrip("\r\n")
        line_number = index + 2
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        if raw[:1].isspace():
            raise FrontMatterError(
                f"{source}:{line_number}: nested block mappings are not supported; use inline JSON"
            )
        if ":" not in raw:
            raise FrontMatterError(f"{source}:{line_number}: expected 'key: value'")

        key, raw_value = raw.split(":", 1)
        key = key.strip()
        if not _KEY.fullmatch(key):
            raise FrontMatterError(f"{source}:{line_number}: invalid key {key!r}")
        if key in result:
            raise FrontMatterError(f"{source}:{line_number}: duplicate key {key!r}")

        value_text = raw_value.strip()
        if value_text:
            result[key] = _parse_scalar(value_text, source=source, line_number=line_number)
            index += 1
            continue

        items: list[Any] = []
        index += 1
        while index < len(lines):
            candidate = lines[index].rstrip("\r\n")
            if not candidate.strip() or candidate.lstrip().startswith("#"):
                index += 1
                continue
            if not candidate.startswith("  - "):
                break
            item_text = candidate[4:].strip()
            if not item_text:
                raise FrontMatterError(f"{source}:{index + 2}: empty block-list item")
            items.append(_parse_scalar(item_text, source=source, line_number=index + 2))
            index += 1
        result[key] = items

    return result


def _parse_scalar(text: str, *, source: str, line_number: int) -> Any:
    lowered = text.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if _INTEGER.fullmatch(text):
        return int(text)

    if text.startswith(("[", "{", '"')):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise FrontMatterError(
                f"{source}:{line_number}: invalid inline JSON: {exc.msg}"
            ) from exc

    if text.startswith("'"):
        if len(text) < 2 or not text.endswith("'"):
            raise FrontMatterError(f"{source}:{line_number}: unterminated quoted string")
        return text[1:-1].replace("''", "'")

    if text[0] in "&*!|>":
        raise FrontMatterError(
            f"{source}:{line_number}: YAML tags, anchors, and block scalars are not supported"
        )
    return text


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (str, list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    raise FrontMatterError(f"unsupported frontmatter value {value!r}")
