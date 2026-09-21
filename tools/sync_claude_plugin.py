#!/usr/bin/env python3
"""Synchronize provider-neutral files into both self-contained plugins."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "claude-techlead"
CODEX_PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "codex-techlead"
PLUGIN_ROOTS = (PLUGIN_ROOT, CODEX_PLUGIN_ROOT)


def synchronized_files() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for plugin_root in PLUGIN_ROOTS:
        for source_root, destination_root in (
            (REPOSITORY_ROOT / "core", plugin_root / "core"),
            (REPOSITORY_ROOT / "tools" / "techlead_state", plugin_root / "bin" / "techlead_state"),
        ):
            for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
                if "__pycache__" in source.parts or source.suffix == ".pyc":
                    continue
                pairs.append((source, destination_root / source.relative_to(source_root)))
        pairs.extend([
            (REPOSITORY_ROOT / "tools" / "techlead-state", plugin_root / "bin" / "techlead-state"),
            (
                REPOSITORY_ROOT / "tests" / "conformance_scenarios.py",
                plugin_root / "conformance" / "conformance_scenarios.py",
            ),
        ])
    return pairs


def sync(*, check: bool) -> list[str]:
    mismatches: list[str] = []
    expected = {destination for _source, destination in synchronized_files()}
    managed: list[Path] = []
    for plugin_root in PLUGIN_ROOTS:
        managed.extend([
            plugin_root / "core",
            plugin_root / "bin" / "techlead_state",
            plugin_root / "conformance",
        ])
        managed.append(plugin_root / "bin" / "techlead-state")
    extras: list[Path] = []
    for path in managed:
        if path.is_file():
            if path not in expected:
                extras.append(path)
        elif path.is_dir():
            extras.extend(
                candidate for candidate in path.rglob("*")
                if candidate.is_file()
                and "__pycache__" not in candidate.parts
                and candidate.suffix != ".pyc"
                and candidate not in expected
            )
    for source, destination in synchronized_files():
        if check:
            if not destination.is_file() or source.read_bytes() != destination.read_bytes():
                mismatches.append(destination.relative_to(REPOSITORY_ROOT).as_posix())
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    if check:
        mismatches.extend(path.relative_to(REPOSITORY_ROOT).as_posix() for path in extras)
    else:
        for path in extras:
            path.unlink()
        for directory in sorted(
            {
                parent
                for path in extras
                for parent in path.parents
                if any(parent == root or root in parent.parents for root in managed if root.is_dir())
            },
            key=lambda value: len(value.parts),
            reverse=True,
        ):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    return mismatches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report stale packaged files without writing")
    args = parser.parse_args(argv)
    mismatches = sync(check=args.check)
    if mismatches:
        for path in mismatches:
            print(f"stale: {path}")
        return 1
    action = "checked" if args.check else "synchronized"
    print(f"{action}: {len(synchronized_files())} packaged files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
