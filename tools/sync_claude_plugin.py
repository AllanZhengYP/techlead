#!/usr/bin/env python3
"""Synchronize provider-neutral files into the self-contained Claude plugin."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "claude-techlead"


def synchronized_files() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for source_root, destination_root in (
        (REPOSITORY_ROOT / "core", PLUGIN_ROOT / "core"),
        (REPOSITORY_ROOT / "tools" / "techlead_state", PLUGIN_ROOT / "bin" / "techlead_state"),
    ):
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            if "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            pairs.append((source, destination_root / source.relative_to(source_root)))
    pairs.extend([
        (REPOSITORY_ROOT / "tools" / "techlead-state", PLUGIN_ROOT / "bin" / "techlead-state"),
        (
            REPOSITORY_ROOT / "tests" / "conformance_scenarios.py",
            PLUGIN_ROOT / "conformance" / "conformance_scenarios.py",
        ),
    ])
    return pairs


def sync(*, check: bool) -> list[str]:
    mismatches: list[str] = []
    for source, destination in synchronized_files():
        if check:
            if not destination.is_file() or source.read_bytes() != destination.read_bytes():
                mismatches.append(destination.relative_to(REPOSITORY_ROOT).as_posix())
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
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
