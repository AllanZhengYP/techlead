"""Command line entry point for deterministic Tech Lead state operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .validator import validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="techlead-state")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a project's .techlead state")
    validate.add_argument("project", nargs="?", default=".", help="project root or .techlead directory")
    validate.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    validate.add_argument("--schema-dir", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "validate":
        return 2

    report = validate_project(args.project, schema_dir=args.schema_dir)
    if args.output_format == "json":
        print(json.dumps({
            "valid": report.valid,
            "project_root": str(report.project_root),
            "records_checked": report.records_checked,
            "work_items_checked": report.work_items_checked,
            "issues": [
                {"code": issue.code, "path": issue.path, "message": issue.message}
                for issue in report.issues
            ],
        }, indent=2))
    elif report.valid:
        print(
            f"valid: protocol 1.0; {report.records_checked} records; "
            f"{report.work_items_checked} work item(s)"
        )
    else:
        for issue in report.issues:
            location = f"{issue.path}: " if issue.path else ""
            print(f"{location}[{issue.code}] {issue.message}", file=sys.stderr)
        print(f"invalid: {len(report.issues)} issue(s)", file=sys.stderr)
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
