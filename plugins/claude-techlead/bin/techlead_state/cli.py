"""Command-line entry point for Tech Lead State Protocol 2.0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .operations import (
    OperationError,
    apply_review,
    attach_workspace,
    clear_stale_lock,
    close_session,
    create_work_item,
    initialize_project,
    next_actions,
    project_status,
    register_session,
    repair_attachment,
    update_session,
)
from .resolver import ResolutionError, register_control_root, resolve_project
from .validator import validate_context_links, validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="techlead-state")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate Protocol 2.0 canonical state")
    _location(validate)
    validate.add_argument("--schema-dir", help=argparse.SUPPRESS)
    _output(validate)

    links = subparsers.add_parser("validate-links", help="validate links in bounded review context")
    _location(links)
    links.add_argument("--document", action="append", required=True, dest="documents")

    init = subparsers.add_parser("init", help="create a project under a multi-project control root")
    init.add_argument("--control-dir", required=True)
    init.add_argument("--name", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--root", required=True, dest="root_title", help="root work-item title")
    init.add_argument("--workspace", default=".")
    init.add_argument("--workspace-id", required=True)
    _registry(init)

    attach = subparsers.add_parser("attach", help="attach or repair a workspace")
    _location(attach)
    attach.add_argument("--project", help="explicit canonical project root")
    attach.add_argument("--workspace", default=".")
    attach.add_argument("--workspace-id")
    attach.add_argument("--control-dir", help="register every project below a control root first")
    attach.add_argument("--scan-only", action="store_true", help="only register projects found below --control-dir")
    _registry(attach)

    resolve = subparsers.add_parser("resolve-project", help="resolve the canonical project root")
    _location(resolve)
    resolve.add_argument("--project-id")
    _registry(resolve)

    repair = subparsers.add_parser("repair-attachment", help="repair local attachment artifacts")
    _location(repair)
    repair.add_argument("--workspace", default=".")
    repair.add_argument("--workspace-id")
    _registry(repair)

    create = subparsers.add_parser("create-work-item", help="create one unsigned child")
    _location(create)
    create.add_argument("--parent", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--work-type", required=True, choices=("design", "exploration", "implementation", "verification"))
    create.add_argument("--body-file")
    _registry(create)

    review = subparsers.add_parser("apply-review", help="apply a human-authorized review decision")
    _location(review)
    review.add_argument("--item", required=True)
    review.add_argument(
        "--decision",
        required=True,
        choices=("signoff", "revise", "reaffirm", "resolve", "return-to-design", "remain"),
    )
    review.add_argument("--revision-title")
    review.add_argument("--revision-file")
    review.add_argument("--work-file")
    review.add_argument("--verdict")
    review.add_argument("--material-challenge", action="store_true")
    review.add_argument("--children-json", help="JSON array of explicitly approved child definitions")
    _registry(review)

    register = subparsers.add_parser("register-session", help="attach a workspace and register a resumable session")
    _location(register)
    register.add_argument("--provider", required=True)
    register.add_argument("--provider-session-id", required=True)
    register.add_argument("--role", required=True, choices=("design", "exploration", "implementation", "verification", "techlead-review"))
    register.add_argument("--work-item", action="append", required=True, dest="work_items")
    register.add_argument("--workspace", default=".")
    register.add_argument("--workspace-id")
    register.add_argument("--title")
    register.add_argument("--note", default="")
    register.add_argument("--git-branch")
    register.add_argument("--git-revision")
    _registry(register)

    pause = subparsers.add_parser("pause-session", help="pause a live session")
    _location(pause)
    pause.add_argument("--session", required=True)
    _registry(pause)

    move = subparsers.add_parser("move-session", help="move a live session to another attached workspace")
    _location(move)
    move.add_argument("--session", required=True)
    move.add_argument("--workspace", required=True)
    move.add_argument("--workspace-id")
    _registry(move)

    close = subparsers.add_parser("close-session", help="close a session and retain compact provenance")
    _location(close)
    close.add_argument("--session", required=True)
    _registry(close)

    status = subparsers.add_parser("status", help="render current tree and live sessions")
    _location(status)
    _registry(status)

    next_parser = subparsers.add_parser("next", help="project mechanical next-action candidates")
    _location(next_parser)
    _registry(next_parser)

    unlock = subparsers.add_parser("clear-stale-lock", help="explicitly remove a confirmed stale writer lock")
    _location(unlock)
    unlock.add_argument("--force", action="store_true", required=True)
    _registry(unlock)
    return parser


def _location(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("location", nargs="?", default=".", help="canonical project root or attached workspace")


def _registry(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", help=argparse.SUPPRESS)


def _output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "validate-links":
            try:
                resolution = resolve_project(args.location)
                target = resolution.project_root
            except ResolutionError:
                target = Path(args.location)
            report, external_urls = validate_context_links(target, args.documents)
            print(json.dumps({
                "valid": report.valid,
                "issues": [
                    {"code": issue.code, "path": issue.path, "message": issue.message}
                    for issue in report.issues
                ],
                "external_urls_to_check": external_urls,
            }, indent=2))
            return 0 if report.valid else 1
        if args.command == "init":
            result = initialize_project(
                args.control_dir,
                name=args.name,
                title=args.title,
                root_title=args.root_title,
                workspace=args.workspace,
                workspace_id=args.workspace_id,
                registry_path=args.registry,
            )
        elif args.command == "attach":
            registered: list[str] = []
            if args.control_dir:
                registered = register_control_root(args.control_dir, registry_path=args.registry)
            if args.scan_only:
                if not args.control_dir:
                    raise ValueError("--scan-only requires --control-dir")
                result = {"registered_projects": registered}
            else:
                result = attach_workspace(
                    args.project or args.location,
                    args.workspace,
                    workspace_id=args.workspace_id,
                    registry_path=args.registry,
                )
                if registered:
                    result["registered_projects"] = registered
        elif args.command == "resolve-project":
            resolution = resolve_project(
                args.location,
                project_id=args.project_id,
                registry_path=args.registry,
            )
            result = {
                "project_root": str(resolution.project_root),
                "project_id": resolution.project_id,
                "source": resolution.source,
            }
        elif args.command == "repair-attachment":
            result = repair_attachment(
                args.location,
                args.workspace,
                workspace_id=args.workspace_id,
                registry_path=args.registry,
            )
        elif args.command == "create-work-item":
            result = create_work_item(
                args.location,
                parent=args.parent,
                title=args.title,
                work_type=args.work_type,
                body=_read_optional(args.body_file),
                registry_path=args.registry,
            )
        elif args.command == "apply-review":
            children = _read_json_array(args.children_json)
            result = apply_review(
                args.location,
                item_id=args.item,
                decision=args.decision,
                revision_title=args.revision_title,
                revision_body=_read_optional(args.revision_file, preserve_none=True),
                work_body=_read_optional(args.work_file, preserve_none=True),
                verdict=args.verdict,
                material_challenge=args.material_challenge,
                children=children,
                registry_path=args.registry,
            )
        elif args.command == "register-session":
            result = register_session(
                args.location,
                provider=args.provider,
                provider_session_id=args.provider_session_id,
                role=args.role,
                work_items=args.work_items,
                workspace=args.workspace,
                workspace_id=args.workspace_id,
                title=args.title,
                note=args.note,
                git_branch=args.git_branch,
                git_revision=args.git_revision,
                registry_path=args.registry,
            )
        elif args.command == "pause-session":
            result = update_session(
                args.location,
                session_id=args.session,
                status="paused",
                registry_path=args.registry,
            )
        elif args.command == "move-session":
            result = update_session(
                args.location,
                session_id=args.session,
                status="active",
                workspace=args.workspace,
                workspace_id=args.workspace_id,
                registry_path=args.registry,
            )
        elif args.command == "close-session":
            result = close_session(args.location, session_id=args.session, registry_path=args.registry)
        elif args.command == "status":
            result = project_status(args.location, registry_path=args.registry)
        elif args.command == "next":
            result = next_actions(args.location, registry_path=args.registry)
        elif args.command == "clear-stale-lock":
            result = {"cleared": str(clear_stale_lock(args.location, registry_path=args.registry))}
        else:
            return 2
    except (OperationError, ResolutionError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _validate(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_project(args.location)
        target = resolution.project_root
    except ResolutionError:
        target = Path(args.location)
    report = validate_project(target, schema_dir=args.schema_dir)
    if args.output_format == "json":
        print(
            json.dumps(
                {
                    "valid": report.valid,
                    "protocol_version": "2.0",
                    "project_root": str(report.project_root),
                    "records_checked": report.records_checked,
                    "work_items_checked": report.work_items_checked,
                    "issues": [
                        {"code": issue.code, "path": issue.path, "message": issue.message}
                        for issue in report.issues
                    ],
                },
                indent=2,
            )
        )
    elif report.valid:
        print(f"valid: protocol 2.0; {report.records_checked} records; {report.work_items_checked} work item(s)")
    else:
        for issue in report.issues:
            location = f"{issue.path}: " if issue.path else ""
            print(f"{location}[{issue.code}] {issue.message}", file=sys.stderr)
        print(f"invalid: {len(report.issues)} issue(s)", file=sys.stderr)
    return 0 if report.valid else 1


def _read_optional(path: str | None, *, preserve_none: bool = False) -> str | None:
    if path is None:
        return None if preserve_none else ""
    return Path(path).read_text(encoding="utf-8")


def _read_json_array(path: str | None) -> list[dict[str, str]]:
    if path is None:
        return []
    value: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(entry, dict) for entry in value):
        raise ValueError("--children-json must contain a JSON array of objects")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
