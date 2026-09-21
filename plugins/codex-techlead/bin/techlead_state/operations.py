"""Transactional operations for Tech Lead State Protocol 2.0."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Iterator
import uuid

from .frontmatter import ParsedDocument, dump_document, parse_file
from .resolver import (
    ProjectResolution,
    ResolutionError,
    read_locator,
    register_project,
    resolve_project,
    write_locator,
)
from .validator import ValidationReport, validate_project


class OperationError(RuntimeError):
    """Raised when a requested operation would violate Protocol 2.0."""


@dataclass(frozen=True)
class WorkItem:
    item_id: str
    directory: Path
    document: ParsedDocument


ChangeSet = dict[Path, str | None]
ChangeBuilder = Callable[[], tuple[ChangeSet, Any]]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise OperationError("a descriptive title must contain at least one letter or digit")
    return slug


def initialize_project(
    control_dir: str | Path,
    *,
    name: str,
    title: str,
    root_title: str,
    workspace: str | Path,
    workspace_id: str,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    if slugify(name) != name:
        raise OperationError("project directory name must be descriptive kebab-case")
    control = Path(control_dir).expanduser().resolve()
    control.mkdir(parents=True, exist_ok=True)
    target = control / name
    if target.exists() or target.is_symlink():
        raise OperationError(f"project target already exists: {target}")
    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.is_dir():
        raise OperationError(f"workspace does not exist: {workspace_path}")
    _preflight_attachment(target, workspace_path, workspace_id)

    project_id = str(uuid.uuid4())
    root_id = "WI-001"
    root_dir = target / "work-items" / f"{root_id}-{slugify(root_title)}"
    try:
        root_dir.mkdir(parents=True)
        (root_dir / "revisions").mkdir()
        (target / "sessions").mkdir()
        (target / "local" / "workspaces").mkdir(parents=True)
        (target / "local" / "sessions").mkdir(parents=True)
        (target / "workspace-links").mkdir()
        (target / ".gitignore").write_text("/local/\n/workspace-links/\n", encoding="utf-8")
        (target / "PROJECT.md").write_text(
            dump_document(
                {
                    "protocol_version": "2.0",
                    "project_id": project_id,
                    "title": title,
                    "root_work_item": root_id,
                    "workspace_ids": [workspace_id],
                },
                f"# {title}\n",
            ),
            encoding="utf-8",
        )
        (root_dir / "WORK.md").write_text(
            dump_document(
                {
                    "id": root_id,
                    "title": root_title,
                    "work_type": "design",
                    "state": "in-design",
                    "parent": None,
                    "active_revision": None,
                    "review_required": False,
                },
                f"# {root_id} — {root_title}\n",
            ),
            encoding="utf-8",
        )
        report = validate_project(target)
        _raise_invalid(report, "initialized project is invalid")
        _install_attachment(target, workspace_path, workspace_id, project_id)
        register_project(target, registry_path=registry_path)
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        raise
    return {
        "project_root": str(target),
        "project_id": project_id,
        "root_work_item": root_id,
        "workspace_id": workspace_id,
    }


def attach_workspace(
    project: str | Path,
    workspace: str | Path,
    *,
    workspace_id: str | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    resolution = _resolve_direct(project, registry_path=registry_path)
    root = resolution.project_root
    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.is_dir():
        raise OperationError(f"workspace does not exist: {workspace_path}")
    locator_path = workspace_path / ".techlead-project"
    if locator_path.is_file():
        locator = read_locator(locator_path)
        existing_workspace_id = locator["workspace_id"]
        if workspace_id is not None and workspace_id != existing_workspace_id:
            raise OperationError(
                f"workspace locator already declares {existing_workspace_id!r}, not {workspace_id!r}"
            )
        workspace_id = existing_workspace_id
        project_ids = list(locator["project_ids"])
    else:
        if workspace_id is None:
            raise OperationError("workspace_id is required when .techlead-project does not exist")
        project_ids = []
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", workspace_id):
        raise OperationError("workspace_id must contain only letters, digits, dot, underscore, and hyphen")
    _preflight_attachment(root, workspace_path, workspace_id)

    def build() -> tuple[ChangeSet, Any]:
        project_doc = parse_file(root / "PROJECT.md")
        metadata = dict(project_doc.metadata)
        workspace_ids = list(metadata["workspace_ids"])
        if workspace_id not in workspace_ids:
            workspace_ids.append(workspace_id)
        metadata["workspace_ids"] = sorted(workspace_ids)
        return {Path("PROJECT.md"): dump_document(metadata, project_doc.body)}, None

    _mutate(root, "attach-workspace", build)
    if resolution.project_id not in project_ids:
        project_ids.append(resolution.project_id)
    _install_attachment(root, workspace_path, workspace_id, resolution.project_id, project_ids=project_ids)
    register_project(root, registry_path=registry_path)
    return {
        "project_root": str(root),
        "project_id": resolution.project_id,
        "workspace": str(workspace_path),
        "workspace_id": workspace_id,
    }


def repair_attachment(
    project: str | Path,
    workspace: str | Path,
    *,
    workspace_id: str | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    return attach_workspace(
        project,
        workspace,
        workspace_id=workspace_id,
        registry_path=registry_path,
    )


def create_work_item(
    project: str | Path,
    *,
    parent: str,
    title: str,
    work_type: str,
    body: str = "",
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    root = _resolve_direct(project, registry_path=registry_path).project_root
    if work_type not in {"design", "exploration", "implementation", "verification"}:
        raise OperationError(f"unsupported work type: {work_type}")

    def build() -> tuple[ChangeSet, Any]:
        items = _load_items(root)
        parent_item = items.get(parent)
        if parent_item is None:
            raise OperationError(f"parent work item does not exist: {parent}")
        if parent_item.document.metadata.get("state") == "resolved":
            raise OperationError("cannot create a child under a resolved parent")
        number = max((_numeric_id(item_id) for item_id in items), default=0) + 1
        item_id = f"WI-{number:03d}"
        directory = Path("work-items") / f"{item_id}-{slugify(title)}"
        content = dump_document(
            {
                "id": item_id,
                "title": title,
                "work_type": work_type,
                "state": "in-design",
                "parent": parent,
                "active_revision": None,
                "review_required": False,
            },
            body or f"# {item_id} — {title}\n\n[Parent context](../{parent_item.directory.name}/WORK.md)\n",
        )
        return {directory / "WORK.md": content}, {
            "id": item_id,
            "directory": str(root / directory),
            "parent": parent,
            "state": "in-design",
        }

    return _mutate(root, "create-work-item", build)


def apply_review(
    project: str | Path,
    *,
    item_id: str,
    decision: str,
    revision_title: str | None = None,
    revision_body: str | None = None,
    work_body: str | None = None,
    verdict: str | None = None,
    material_challenge: bool = False,
    children: list[dict[str, str]] | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    root = _resolve_direct(project, registry_path=registry_path).project_root
    allowed = {"signoff", "revise", "reaffirm", "resolve", "return-to-design", "remain"}
    if decision not in allowed:
        raise OperationError(f"unsupported review decision: {decision}")
    if (decision == "resolve" or material_challenge) and not verdict:
        raise OperationError("resolution and material challenges require a concise verdict for WORK.md")
    proposed_children = children or []

    def build() -> tuple[ChangeSet, Any]:
        items = _load_items(root)
        item = items.get(item_id)
        if item is None:
            raise OperationError(f"work item does not exist: {item_id}")
        metadata = dict(item.document.metadata)
        state = metadata["state"]
        if state == "resolved":
            raise OperationError("resolved work is terminal and cannot be reviewed into another state")
        if decision == "signoff" and state != "in-design":
            raise OperationError("signoff applies only to in-design work")
        if decision in {"revise", "reaffirm", "resolve", "return-to-design"} and state != "in-working":
            raise OperationError(f"{decision} applies only to in-working work")
        direct_children = [candidate for candidate in items.values() if candidate.document.metadata.get("parent") == item_id]
        if decision == "resolve":
            unresolved = [child.item_id for child in direct_children if child.document.metadata.get("state") != "resolved"]
            if unresolved:
                raise OperationError(f"cannot resolve while children remain unresolved: {', '.join(unresolved)}")
            if proposed_children:
                raise OperationError("a resolving review cannot create children")
        if proposed_children and decision not in {"signoff", "revise"}:
            raise OperationError("approved children require a changed signed baseline in the same review")

        changes: ChangeSet = {}
        new_revision: str | None = None
        if decision in {"signoff", "revise"}:
            if revision_body is None:
                raise OperationError("signoff and revise require an explicit self-contained revision body")
            existing = _revision_numbers(item.directory)
            next_number = max(existing, default=0) + 1
            new_revision = f"r{next_number}"
            supersedes = f"r{next_number - 1}" if next_number > 1 else None
            title = revision_title or (
                f"Initial {metadata['title']} baseline" if next_number == 1 else f"Updated {metadata['title']} baseline"
            )
            baseline = revision_body
            revision_path = item.directory.relative_to(root) / "revisions" / f"{new_revision}-{slugify(title)}.md"
            changes[revision_path] = dump_document(
                {"revision": new_revision, "title": title, "supersedes": supersedes},
                baseline,
            )
            metadata["state"] = "in-working"
            metadata["active_revision"] = new_revision
            metadata["review_required"] = False
        elif decision == "reaffirm":
            metadata["review_required"] = False
        elif decision == "resolve":
            metadata["state"] = "resolved"
            metadata["review_required"] = False
        elif decision == "return-to-design":
            metadata["state"] = "in-design"
            metadata["active_revision"] = None
            metadata["review_required"] = False

        body = item.document.body if work_body is None else work_body
        if verdict:
            body = _append_log(body, "Review finding", verdict)
        changes[item.directory.relative_to(root) / "WORK.md"] = dump_document(metadata, body)

        created: list[str] = []
        if proposed_children:
            if metadata["state"] == "resolved":
                raise OperationError("cannot create children under a resolved parent")
            next_number = max((_numeric_id(existing_id) for existing_id in items), default=0) + 1
            for child in proposed_children:
                child_title = child["title"]
                child_type = child.get("work_type", "design")
                if child_type not in {"design", "exploration", "implementation", "verification"}:
                    raise OperationError(f"unsupported child work type: {child_type}")
                child_id = f"WI-{next_number:03d}"
                next_number += 1
                directory = Path("work-items") / f"{child_id}-{slugify(child_title)}"
                child_body = child.get("body") or (
                    f"# {child_id} — {child_title}\n\n"
                    f"[Parent context](../{item.directory.name}/WORK.md)\n"
                )
                changes[directory / "WORK.md"] = dump_document(
                    {
                        "id": child_id,
                        "title": child_title,
                        "work_type": child_type,
                        "state": "in-design",
                        "parent": item_id,
                        "active_revision": None,
                        "review_required": False,
                    },
                    child_body,
                )
                created.append(child_id)

        if decision == "resolve" or material_challenge:
            _roll_up(
                root,
                items,
                changes,
                item_id=item_id,
                resulting_state=metadata["state"],
                verdict=verdict,
                material_challenge=material_challenge,
            )
        return changes, {
            "item": item_id,
            "decision": decision,
            "state": metadata["state"],
            "active_revision": metadata["active_revision"],
            "new_revision": new_revision,
            "created_children": created,
        }

    return _mutate(root, f"review-{item_id}", build)


def register_session(
    project: str | Path,
    *,
    provider: str,
    provider_session_id: str,
    role: str,
    work_items: list[str],
    workspace: str | Path,
    workspace_id: str | None = None,
    title: str | None = None,
    note: str = "",
    git_branch: str | None = None,
    git_revision: str | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    if role not in {"design", "exploration", "implementation", "verification", "techlead-review"}:
        raise OperationError(f"unsupported session role: {role}")
    initial_root = _resolve_direct(project, registry_path=registry_path).project_root
    initial_existing = next(
        (
            entry for entry in _load_sessions(initial_root).values()
            if entry.document.metadata.get("provider") == provider
            and entry.document.metadata.get("provider_session_id") == provider_session_id
        ),
        None,
    )
    if initial_existing is not None and initial_existing.document.metadata.get("role") != role:
        raise OperationError(
            f"provider session is already registered as {initial_existing.document.metadata['role']}; "
            f"use a dedicated session for {role}"
        )
    attachment = attach_workspace(
        project,
        workspace,
        workspace_id=workspace_id,
        registry_path=registry_path,
    )
    root = Path(attachment["project_root"])
    workspace_id = attachment["workspace_id"]

    def build() -> tuple[ChangeSet, Any]:
        items = _load_items(root)
        missing = [item_id for item_id in work_items if item_id not in items]
        if missing:
            raise OperationError(f"session references missing work items: {', '.join(missing)}")
        sessions = _load_sessions(root)
        existing = next(
            (
                entry for entry in sessions.values()
                if entry.document.metadata.get("provider") == provider
                and entry.document.metadata.get("provider_session_id") == provider_session_id
            ),
            None,
        )
        if existing is not None:
            metadata = dict(existing.document.metadata)
            if metadata["role"] != role:
                raise OperationError(
                    f"provider session is already registered as {metadata['role']}; use a dedicated session for {role}"
                )
            metadata["work_items"] = sorted(set(metadata["work_items"]) | set(work_items))
            metadata["status"] = "active"
            metadata["workspace_id"] = workspace_id
            session_id = metadata["session"]
            relative = existing.path.relative_to(root)
            session_title = existing.path.stem.split("-", 2)[-1]
        else:
            number = _next_session_number(root)
            session_id = f"SES-{number:03d}"
            session_title = slugify(title or f"{role}-{provider}")
            relative = Path("sessions") / f"{session_id}-{session_title}.md"
            metadata = {
                "session": session_id,
                "provider": provider,
                "provider_session_id": provider_session_id,
                "role": role,
                "status": "active",
                "work_items": sorted(set(work_items)),
                "workspace_id": workspace_id,
            }
        if git_branch:
            metadata["git_branch"] = git_branch
        else:
            metadata.pop("git_branch", None)
        if git_revision:
            metadata["git_revision"] = git_revision
        else:
            metadata.pop("git_revision", None)
        body = existing.document.body if existing is not None and not note else (
            f"# {session_id} — {session_title.replace('-', ' ').title()}\n\n{note}\n" if note else ""
        )
        return {relative: dump_document(metadata, body)}, {
            "session": session_id,
            "provider": provider,
            "provider_session_id": provider_session_id,
            "role": role,
            "work_items": metadata["work_items"],
            "workspace_id": workspace_id,
        }

    result = _mutate(root, "register-session", build)
    _write_session_mapping(root, result["session"], Path(workspace), workspace_id)
    return result


def update_session(
    project: str | Path,
    *,
    session_id: str,
    status: str | None = None,
    workspace: str | Path | None = None,
    workspace_id: str | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    root = _resolve_direct(project, registry_path=registry_path).project_root
    if status is not None and status not in {"active", "paused"}:
        raise OperationError("session status must be active or paused")
    if workspace is not None:
        attachment = attach_workspace(
            root,
            workspace,
            workspace_id=workspace_id,
            registry_path=registry_path,
        )
        workspace_id = attachment["workspace_id"]

    def build() -> tuple[ChangeSet, Any]:
        sessions = _load_sessions(root)
        session = sessions.get(session_id)
        if session is None:
            raise OperationError(f"live session does not exist: {session_id}")
        metadata = dict(session.document.metadata)
        if status is not None:
            metadata["status"] = status
        if workspace_id is not None:
            metadata["workspace_id"] = workspace_id
        return {session.path.relative_to(root): dump_document(metadata, session.document.body)}, dict(metadata)

    result = _mutate(root, f"update-{session_id}", build)
    if workspace is not None:
        _write_session_mapping(root, session_id, Path(workspace), str(workspace_id))
    return result


def close_session(
    project: str | Path,
    *,
    session_id: str,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    root = _resolve_direct(project, registry_path=registry_path).project_root

    def build() -> tuple[ChangeSet, Any]:
        sessions = _load_sessions(root)
        session = sessions.get(session_id)
        if session is None:
            raise OperationError(f"live session does not exist: {session_id}")
        metadata = session.document.metadata
        items = _load_items(root)
        changes: ChangeSet = {session.path.relative_to(root): None}
        provenance = (
            f"{session_id}; provider={metadata['provider']}; "
            f"provider_session_id={metadata['provider_session_id']}"
        )
        for item_id in metadata["work_items"]:
            item = items[item_id]
            changes[item.directory.relative_to(root) / "WORK.md"] = dump_document(
                item.document.metadata,
                _append_log(item.document.body, "Closed session provenance", provenance),
            )
        return changes, {
            "session": session_id,
            "closed": True,
            "work_items": list(metadata["work_items"]),
        }

    result = _mutate(root, f"close-{session_id}", build)
    mapping = root / "local" / "sessions" / f"{session_id}.yaml"
    if mapping.exists():
        mapping.unlink()
    return result


def project_status(
    project: str | Path,
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    root = _resolve_direct(project, registry_path=registry_path).project_root
    _ensure_reader_safe(root)
    report = validate_project(root)
    _raise_invalid(report, "project is invalid")
    project_doc = parse_file(root / "PROJECT.md")
    items = _load_items(root)
    sessions = _load_sessions(root)
    children = {item_id: [] for item_id in items}
    for item in items.values():
        parent = item.document.metadata.get("parent")
        if parent in children:
            children[parent].append(item.item_id)
    return {
        "project_root": str(root),
        "project_id": project_doc.metadata["project_id"],
        "title": project_doc.metadata["title"],
        "root_work_item": project_doc.metadata["root_work_item"],
        "work_items": [
            {
                **item.document.metadata,
                "path": str(item.directory / "WORK.md"),
                "children": sorted(children[item.item_id]),
            }
            for item in sorted(items.values(), key=lambda value: _numeric_id(value.item_id))
        ],
        "sessions": [
            {**session.document.metadata, "path": str(session.path)}
            for session in sorted(sessions.values(), key=lambda value: _numeric_id(value.document.metadata["session"]))
        ],
    }


def next_actions(
    project: str | Path,
    *,
    registry_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    status = project_status(project, registry_path=registry_path)
    items = {entry["id"]: entry for entry in status["work_items"]}
    active_items = {
        item_id
        for session in status["sessions"]
        if session["status"] == "active"
        for item_id in session["work_items"]
    }
    actions: list[dict[str, Any]] = []
    for item_id, item in items.items():
        if item["state"] == "resolved":
            continue
        if item["review_required"]:
            action = "review-work"
            reason = "a mandatory exception or roll-up review is pending"
        elif item["state"] == "in-design":
            action = "continue-design-or-review"
            reason = "the work item has no signed semantic baseline"
        elif item["children"] and all(items[child]["state"] == "resolved" for child in item["children"]):
            action = "review-work"
            reason = "every current child is resolved and the parent needs synthesis"
        elif item["children"]:
            action = "await-children"
            reason = "one or more current children remain unresolved"
        elif item_id in active_items:
            action = "resume-session"
            reason = "an active recorded session already owns current context"
        else:
            action = "execute-signed-work"
            reason = "the item is signed, unresolved, and has no active recorded session"
        actions.append(
            {
                "action": action,
                "work_item": item_id,
                "title": item["title"],
                "context": item["path"],
                "reason": reason,
                "parallel_note": "Confirm signed coordination and artifact non-collision before grouping with another item.",
            }
        )
    priority = {
        "review-work": 0,
        "continue-design-or-review": 1,
        "resume-session": 2,
        "execute-signed-work": 3,
        "await-children": 4,
    }
    return sorted(actions, key=lambda entry: (priority[entry["action"]], _numeric_id(entry["work_item"])))


def clear_stale_lock(project: str | Path, *, registry_path: str | Path | None = None) -> Path:
    root = _resolve_direct(project, registry_path=registry_path).project_root
    lock = root / "local" / "write.lock"
    if not lock.is_dir():
        raise OperationError("no writer lock exists")
    shutil.rmtree(lock)
    return lock


def _resolve_direct(project: str | Path, *, registry_path: str | Path | None) -> ProjectResolution:
    try:
        return resolve_project(project, registry_path=registry_path)
    except ResolutionError as exc:
        raise OperationError(str(exc)) from exc


def _load_items(root: Path) -> dict[str, WorkItem]:
    result: dict[str, WorkItem] = {}
    for work in sorted((root / "work-items").glob("WI-*-*/WORK.md")):
        document = parse_file(work)
        item_id = document.metadata.get("id")
        if isinstance(item_id, str):
            result[item_id] = WorkItem(item_id=item_id, directory=work.parent, document=document)
    return result


@dataclass(frozen=True)
class SessionRecord:
    path: Path
    document: ParsedDocument


def _load_sessions(root: Path) -> dict[str, SessionRecord]:
    result: dict[str, SessionRecord] = {}
    for path in sorted((root / "sessions").glob("SES-*.md")):
        document = parse_file(path)
        session_id = document.metadata.get("session")
        if isinstance(session_id, str):
            result[session_id] = SessionRecord(path=path, document=document)
    return result


def _revision_numbers(item_directory: Path) -> list[int]:
    numbers: list[int] = []
    for path in (item_directory / "revisions").glob("r*-*.md"):
        match = re.match(r"r([1-9][0-9]*)-", path.name)
        if match:
            numbers.append(int(match.group(1)))
    return numbers


def _next_session_number(root: Path) -> int:
    values = [_numeric_id(path.name.split("-", 2)[0] + "-" + path.name.split("-", 2)[1]) for path in (root / "sessions").glob("SES-*.md")]
    provenance = re.compile(r"\bSES-([0-9]{3,})\b")
    for item in _load_items(root).values():
        values.extend(int(match.group(1)) for match in provenance.finditer(item.document.body))
    return max(values, default=0) + 1


def _numeric_id(value: str) -> int:
    return int(value.rsplit("-", 1)[1])


def _roll_up(
    root: Path,
    items: dict[str, WorkItem],
    changes: ChangeSet,
    *,
    item_id: str,
    resulting_state: str,
    verdict: str,
    material_challenge: bool,
) -> None:
    origin = items[item_id]
    parent_id = origin.document.metadata.get("parent")
    child_id = item_id
    child_state = resulting_state
    first = True
    while isinstance(parent_id, str) and parent_id in items:
        parent = items[parent_id]
        metadata = dict(parent.document.metadata)
        body = parent.document.body
        relative_link = os.path.relpath(origin.directory / "WORK.md", parent.directory).replace(os.sep, "/")
        body = _append_log(body, "Child verdict", f"[{item_id}]({relative_link}): {verdict}")
        siblings = [candidate for candidate in items.values() if candidate.document.metadata.get("parent") == parent_id]
        all_resolved = all(
            (child_state if candidate.item_id == child_id and first else candidate.document.metadata.get("state")) == "resolved"
            for candidate in siblings
        )
        if metadata.get("state") == "in-working" and (material_challenge or all_resolved):
            metadata["review_required"] = True
        changes[parent.directory.relative_to(root) / "WORK.md"] = dump_document(metadata, body)
        if not material_challenge:
            break
        child_id = parent_id
        child_state = str(metadata.get("state"))
        parent_id = metadata.get("parent")
        first = False


def _append_log(body: str, label: str, message: str) -> str:
    content = body.rstrip()
    return f"{content}\n\n## {label}\n\n- {message}\n" if content else f"## {label}\n\n- {message}\n"


def _mutate(root: Path, operation: str, builder: ChangeBuilder) -> Any:
    with _writer_lock(root, operation):
        report = validate_project(root, allow_active_writer=True)
        _raise_invalid(report, "cannot mutate an invalid project")
        changes, result = builder()
        _apply_validated_changes(root, changes, operation)
        return result


@contextmanager
def _writer_lock(root: Path, operation: str) -> Iterator[None]:
    local = root / "local"
    local.mkdir(parents=True, exist_ok=True)
    lock = local / "write.lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        owner = lock / "owner.json"
        details = owner.read_text(encoding="utf-8").strip() if owner.is_file() else "unknown owner"
        raise OperationError(f"project writer lock is held: {details}") from exc
    (lock / "owner.json").write_text(
        json.dumps({"operation": operation, "pid": os.getpid()}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        yield
    finally:
        if lock.exists():
            shutil.rmtree(lock)


def _apply_validated_changes(root: Path, changes: ChangeSet, operation: str) -> None:
    transaction_root = Path(tempfile.mkdtemp(prefix="transaction-", dir=root / "local"))
    staging = transaction_root / "project"
    backup = transaction_root / "backup"
    backup.mkdir()
    try:
        shutil.copytree(
            root,
            staging,
            symlinks=True,
            ignore=shutil.ignore_patterns("local"),
        )
        (staging / "local").mkdir()
        for relative, content in changes.items():
            candidate = staging / relative
            if content is None:
                if candidate.exists():
                    candidate.unlink()
            else:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_text(content, encoding="utf-8")
        report = validate_project(staging)
        _raise_invalid(report, f"{operation} would produce invalid project state")

        applied: list[tuple[Path, Path | None]] = []
        try:
            for index, (relative, content) in enumerate(changes.items()):
                destination = root / relative
                saved: Path | None = None
                if destination.exists() or destination.is_symlink():
                    saved = backup / str(index)
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(destination, saved)
                applied.append((destination, saved))
                if content is not None:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}-", dir=destination.parent)
                    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary_name, destination)
        except Exception:
            for destination, saved in reversed(applied):
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
                if saved is not None and saved.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(saved, destination)
            raise
    finally:
        shutil.rmtree(transaction_root, ignore_errors=True)


def _raise_invalid(report: ValidationReport, prefix: str) -> None:
    if report.valid:
        return
    details = "; ".join(
        f"{issue.path or '.'} [{issue.code}] {issue.message}" for issue in report.issues[:8]
    )
    raise OperationError(f"{prefix}: {details}")


def _ensure_reader_safe(root: Path) -> None:
    lock = root / "local" / "write.lock"
    if lock.exists():
        raise OperationError("project writer lock is active; retry the read after it completes")


def _install_attachment(
    root: Path,
    workspace: Path,
    workspace_id: str,
    project_id: str,
    *,
    project_ids: list[str] | None = None,
) -> None:
    workspace = workspace.expanduser().resolve()
    _preflight_attachment(root, workspace, workspace_id)
    locator = workspace / ".techlead-project"
    if project_ids is None and locator.is_file():
        existing = read_locator(locator)
        if existing["workspace_id"] != workspace_id:
            raise OperationError(
                f"workspace locator already declares {existing['workspace_id']!r}, not {workspace_id!r}"
            )
        project_ids = list(existing["project_ids"])
    project_ids = list(project_ids or [])
    if project_id not in project_ids:
        project_ids.append(project_id)
    selection = workspace / ".techlead"
    if selection.exists() and not selection.is_symlink():
        raise OperationError(f"refusing to replace non-symlink attachment: {selection}")
    if _is_git_tracked(workspace, selection):
        raise OperationError(f"refusing to replace tracked .techlead selection: {selection}")

    links = root / "workspace-links"
    links.mkdir(exist_ok=True)
    link = links / workspace_id
    if link.exists() and not link.is_symlink():
        raise OperationError(f"refusing to replace non-symlink workspace link: {link}")

    write_locator(
        locator,
        workspace_id=workspace_id,
        project_ids=project_ids,
    )
    if selection.is_symlink():
        selection.unlink()
    selection.symlink_to(root, target_is_directory=True)
    if link.is_symlink():
        link.unlink()
    link.symlink_to(workspace, target_is_directory=True)

    digest = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:12]
    mapping = root / "local" / "workspaces" / workspace_id / f"{digest}.yaml"
    mapping.parent.mkdir(parents=True, exist_ok=True)
    mapping.write_text(
        json.dumps(
            {"workspace_id": workspace_id, "path": str(workspace), "worktree_name": workspace.name},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    _install_git_exclude(workspace, ".techlead")


def _preflight_attachment(root: Path, workspace: Path, workspace_id: str) -> None:
    if not workspace.is_dir():
        raise OperationError(f"workspace does not exist: {workspace}")
    locator = workspace / ".techlead-project"
    if locator.is_file():
        existing = read_locator(locator)
        if existing["workspace_id"] != workspace_id:
            raise OperationError(
                f"workspace locator already declares {existing['workspace_id']!r}, not {workspace_id!r}"
            )
    selection = workspace / ".techlead"
    if selection.exists() and not selection.is_symlink():
        raise OperationError(f"refusing to replace non-symlink attachment: {selection}")
    if _is_git_tracked(workspace, selection):
        raise OperationError(f"refusing to replace tracked .techlead selection: {selection}")
    link = root / "workspace-links" / workspace_id
    if link.exists() and not link.is_symlink():
        raise OperationError(f"refusing to replace non-symlink workspace link: {link}")


def _write_session_mapping(root: Path, session_id: str, workspace: Path, workspace_id: str) -> None:
    target = root / "local" / "sessions" / f"{session_id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    workspace = workspace.expanduser().resolve()
    target.write_text(
        json.dumps(
            {"session": session_id, "workspace_id": workspace_id, "path": str(workspace), "worktree_name": workspace.name},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def _is_git_tracked(workspace: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(workspace)
        result = subprocess.run(
            ["git", "-C", str(workspace), "ls-files", "--error-unmatch", "--", relative.as_posix()],
            check=False,
            capture_output=True,
        )
    except (OSError, ValueError):
        return False
    return result.returncode == 0


def _install_git_exclude(workspace: Path, entry: str) -> None:
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--git-path", "info/exclude"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return
    if result.returncode != 0:
        return
    exclude = Path(result.stdout.strip())
    if not exclude.is_absolute():
        exclude = workspace / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
    lines = {line.strip() for line in existing.splitlines()}
    if entry not in lines:
        with exclude.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(entry + "\n")
