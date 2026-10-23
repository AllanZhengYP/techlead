#!/usr/bin/env python3
"""Validate the publishable Kiro Power against its portable package contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from techlead_state.frontmatter import FrontMatterError, parse_document


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POWER_ROOT = REPOSITORY_ROOT / "powers" / "techlead"
AGENT_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
EXPECTED_SKILLS = {"create-work-item", "review-work", "work-log"}
ALLOWED_MANIFEST_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
}
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def validate_power(power_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = power_root / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["missing plugin.json at the Power root"]
    except json.JSONDecodeError as error:
        return [f"plugin.json is not valid JSON: {error}"]
    if not isinstance(manifest, dict):
        return ["plugin.json must contain a JSON object"]

    unknown = sorted(set(manifest) - ALLOWED_MANIFEST_FIELDS)
    if unknown:
        errors.append(f"plugin.json has unsupported fields: {', '.join(unknown)}")
    if manifest.get("$schema") != AGENT_PLUGIN_SCHEMA:
        errors.append(f"plugin.json $schema must be {AGENT_PLUGIN_SCHEMA}")

    name = manifest.get("name")
    if not isinstance(name, str) or NAME.fullmatch(name) is None or "--" in name:
        errors.append("plugin.json name must be lowercase kebab-case")
    elif name != power_root.name:
        errors.append("plugin.json name must match the Power directory name")
    version = manifest.get("version")
    if not isinstance(version, str) or SEMVER.fullmatch(version) is None:
        errors.append("plugin.json version must be strict semantic versioning")
    if not _non_empty_string(manifest.get("description")):
        errors.append("plugin.json description must be a non-empty string")
    author = manifest.get("author")
    if not isinstance(author, dict) or not _non_empty_string(author.get("name")):
        errors.append("plugin.json author.name must be a non-empty string")
    keywords = manifest.get("keywords")
    if not isinstance(keywords, list) or not keywords or not all(
        _non_empty_string(keyword) for keyword in keywords
    ):
        errors.append("plugin.json keywords must be a non-empty array of strings")
    if "TODO" in manifest_path.read_text(encoding="utf-8"):
        errors.append("plugin.json contains a TODO marker")

    for required_path in (
        power_root / "bin" / "techlead-state",
        power_root / "core" / "protocol" / "PROTOCOL.md",
        power_root / "core" / "schemas" / "manifest.json",
    ):
        if not required_path.is_file():
            errors.append(f"missing packaged file: {required_path.relative_to(power_root)}")

    skills_root = power_root / "skills"
    skills = {
        path.parent.name: path
        for path in skills_root.glob("*/SKILL.md")
        if path.is_file()
    }
    if set(skills) != EXPECTED_SKILLS:
        errors.append(
            "skills must be exactly: " + ", ".join(sorted(EXPECTED_SKILLS))
        )
    for skill_name, skill_path in sorted(skills.items()):
        _validate_skill(power_root, skill_name, skill_path, errors)

    for path in power_root.rglob("*"):
        if path.is_symlink() and power_root.resolve() not in path.resolve().parents:
            errors.append(f"package symlink escapes the Power root: {path}")
    return errors


def _validate_skill(
    power_root: Path,
    skill_name: str,
    skill_path: Path,
    errors: list[str],
) -> None:
    text = skill_path.read_text(encoding="utf-8")
    try:
        document = parse_document(text)
    except FrontMatterError as error:
        errors.append(f"{skill_path.relative_to(power_root)}: {error}")
        return
    if document.metadata.get("name") != skill_name:
        errors.append(f"{skill_path.relative_to(power_root)} name must match its directory")
    if not _non_empty_string(document.metadata.get("description")):
        errors.append(f"{skill_path.relative_to(power_root)} needs a description")
    if f"/{skill_name}" not in str(document.metadata.get("description", "")):
        errors.append(f"{skill_path.relative_to(power_root)} must document explicit invocation")
    if "TODO" in text:
        errors.append(f"{skill_path.relative_to(power_root)} contains a TODO marker")

    skill_root = skill_path.parent
    required = (
        skill_root / "scripts" / "techlead-state",
        skill_root / "references" / "PROTOCOL.md",
        skill_root / "references" / f"{skill_name}.md",
    )
    for required_path in required:
        if not required_path.is_file():
            errors.append(
                f"{required_path.relative_to(power_root)} is required for a self-contained skill"
            )


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("power_root", nargs="?", type=Path, default=DEFAULT_POWER_ROOT)
    args = parser.parse_args(argv)
    power_root = args.power_root.expanduser().resolve()
    errors = validate_power(power_root)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(f"valid Kiro Power: {power_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
