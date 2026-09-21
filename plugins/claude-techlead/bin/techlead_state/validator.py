"""Deterministic validator for Tech Lead State Protocol 2.0."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import unquote

from .frontmatter import FrontMatterError, ParsedDocument, parse_file
from .schema import validate_schema


PROTOCOL_VERSION = "2.0"
WORK_ID = re.compile(r"^WI-[0-9]{3,}$")
WORK_DIR = re.compile(r"^(WI-[0-9]{3,})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
REVISION_FILE = re.compile(r"^(r[1-9][0-9]*)-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
SESSION_FILE = re.compile(r"^(SES-[0-9]{3,})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str | None = None


@dataclass
class ValidationReport:
    project_root: Path
    records_checked: int = 0
    work_items_checked: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    def add(self, code: str, message: str, path: Path | str | None = None) -> None:
        rendered: str | None = None
        if isinstance(path, Path):
            try:
                rendered = path.relative_to(self.project_root).as_posix()
            except ValueError:
                rendered = str(path)
        elif path is not None:
            rendered = str(path)
        self.issues.append(ValidationIssue(code=code, message=message, path=rendered))


@dataclass(frozen=True)
class Record:
    path: Path
    kind: str
    document: ParsedDocument
    owner: str | None = None

    @property
    def data(self) -> dict[str, Any]:
        return self.document.metadata


def validate_project(
    project_root: str | Path,
    *,
    schema_dir: str | Path | None = None,
    allow_active_writer: bool = False,
) -> ValidationReport:
    """Validate a canonical project root or an attached workspace."""

    supplied = Path(project_root).expanduser()
    root = _locate_project_root(supplied)
    report = ValidationReport(project_root=root)
    if not (root / "PROJECT.md").is_file():
        legacy = root / "CHARTER.md"
        if legacy.is_file() or (supplied / ".techlead" / "CHARTER.md").is_file():
            report.add(
                "protocol.legacy",
                "Protocol 1.0 state cannot be reinterpreted; initialize a separate Protocol 2.0 project",
                root,
            )
        else:
            report.add("project.missing", "expected PROJECT.md in the canonical project root", root)
        return report

    lock = root / "local" / "write.lock"
    if lock.exists() and not allow_active_writer:
        report.add("writer.active", "a canonical mutation is currently in progress", lock)
        return report

    schemas = _load_schemas(Path(schema_dir) if schema_dir else _default_schema_dir(), report)
    records = _load_records(root, report)
    report.records_checked = len(records)
    report.work_items_checked = sum(record.kind == "work_item" for record in records)

    for record in records:
        schema = schemas.get(record.kind)
        if schema is None:
            report.add("schema.kind", f"no schema is registered for {record.kind}", record.path)
            continue
        for issue in validate_schema(record.data, schema):
            report.add("schema.invalid", f"{issue.path}: {issue.message}", record.path)

    _validate_locations(root, records, report)
    _validate_project_graph(root, records, report)
    _validate_links(root, records, report)
    _validate_git_safety(root, report)
    return report


def validate_context_links(
    project_root: str | Path,
    documents: list[str | Path],
) -> tuple[ValidationReport, list[str]]:
    """Validate links in an explicit, bounded set of review documents."""

    root = _locate_project_root(Path(project_root).expanduser())
    report = ValidationReport(project_root=root)
    records: list[Record] = []
    project_path = root / "PROJECT.md"
    if project_path.is_file():
        try:
            records.append(Record(project_path, "project", parse_file(project_path)))
        except (OSError, FrontMatterError) as exc:
            report.add("record.parse", str(exc), project_path)
    external_urls: set[str] = set()
    for supplied in documents:
        path = _canonical_context_path(root, Path(supplied).expanduser())
        if path is None or not path.is_file():
            report.add("link.context_missing", f"review context does not exist: {supplied}", str(supplied))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report.add("link.context_read", f"cannot read review context: {exc}", path)
            continue
        records.append(Record(path, "context", ParsedDocument(metadata={}, body=text)))
        for match in MARKDOWN_LINK.finditer(text):
            destination = match.group(1).strip().strip("<>")
            if re.match(r"^https?://", destination):
                external_urls.add(destination)
    _validate_links(root, records, report)
    report.records_checked = len(records)
    return report, sorted(external_urls)


def _locate_project_root(path: Path) -> Path:
    path = path.resolve()
    if (path / "PROJECT.md").is_file():
        return path
    selection = path / ".techlead"
    if selection.exists() and (selection / "PROJECT.md").is_file():
        return selection.resolve()
    if path.name == ".techlead":
        return path.resolve()
    return path


def _canonical_context_path(root: Path, supplied: Path) -> Path | None:
    absolute = supplied.absolute() if supplied.is_absolute() else (Path.cwd() / supplied).absolute()
    try:
        absolute.relative_to(root)
        return absolute
    except ValueError:
        pass
    links = root / "workspace-links"
    if not links.is_dir():
        return None
    resolved = absolute.resolve()
    for link in links.iterdir():
        if not link.is_symlink():
            continue
        try:
            relative = resolved.relative_to(link.resolve())
        except ValueError:
            continue
        return link / relative
    return None


def _default_schema_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "core" / "schemas"


def _load_schemas(schema_dir: Path, report: ValidationReport) -> dict[str, dict[str, Any]]:
    manifest_path = schema_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.add("schema.load", f"cannot load schema manifest: {exc}", manifest_path)
        return {}
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        report.add("schema.version", f"schema manifest must declare protocol {PROTOCOL_VERSION}", manifest_path)
    result: dict[str, dict[str, Any]] = {}
    for kind, filename in manifest.get("schemas", {}).items():
        path = schema_dir / filename
        try:
            result[kind] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report.add("schema.load", f"cannot load schema for {kind}: {exc}", path)
    return result


def _load_records(root: Path, report: ValidationReport) -> list[Record]:
    records: list[Record] = []
    _append_record(records, root / "PROJECT.md", "project", report)
    for legacy_name in ("CHARTER.md", "OVERVIEW.md", "FRONTIER.md", "RISKS.md", "DECISIONS.md"):
        legacy = root / legacy_name
        if legacy.exists():
            report.add("record.unexpected", f"{legacy_name} is a Protocol 1.0 record and is not part of Protocol 2.0", legacy)

    items_root = root / "work-items"
    if not items_root.is_dir():
        report.add("record.missing", "work-items directory is missing", items_root)
    else:
        for item_dir in sorted(path for path in items_root.iterdir() if path.is_dir()):
            match = WORK_DIR.fullmatch(item_dir.name)
            owner = match.group(1) if match else None
            _append_record(records, item_dir / "WORK.md", "work_item", report, owner=owner)
            revisions = item_dir / "revisions"
            if revisions.is_dir():
                for path in sorted(revisions.glob("*.md")):
                    _append_record(records, path, "revision", report, owner=owner)
            for child in sorted(path for path in item_dir.iterdir() if path.is_dir()):
                if child.name != "revisions":
                    report.add("record.unexpected", "only revisions/ is allowed below a work item", child)

    sessions_root = root / "sessions"
    if not sessions_root.is_dir():
        report.add("record.missing", "sessions directory is missing", sessions_root)
    else:
        for path in sorted(sessions_root.glob("*.md")):
            _append_record(records, path, "session", report)
    return records


def _append_record(
    records: list[Record],
    path: Path,
    kind: str,
    report: ValidationReport,
    *,
    owner: str | None = None,
) -> None:
    if not path.is_file():
        report.add("record.missing", f"required {kind} record is missing", path)
        return
    try:
        records.append(Record(path=path, kind=kind, document=parse_file(path), owner=owner))
    except (OSError, FrontMatterError) as exc:
        report.add("record.parse", str(exc), path)


def _validate_locations(root: Path, records: list[Record], report: ValidationReport) -> None:
    for record in records:
        if record.kind == "project" and record.path != root / "PROJECT.md":
            report.add("record.location", "project record must be PROJECT.md", record.path)
        elif record.kind == "work_item":
            directory = record.path.parent
            match = WORK_DIR.fullmatch(directory.name)
            if not match:
                report.add("record.location", "work-item directory must be WI-NNN-descriptive-title", record.path)
            elif record.data.get("id") != match.group(1):
                report.add("record.location", "work-item ID must match its directory prefix", record.path)
        elif record.kind == "revision":
            match = REVISION_FILE.fullmatch(record.path.name)
            if not match:
                report.add("record.location", "revision filename must be rN-descriptive-title.md", record.path)
            elif record.data.get("revision") != match.group(1):
                report.add("record.location", "revision identity must match its filename prefix", record.path)
        elif record.kind == "session":
            match = SESSION_FILE.fullmatch(record.path.name)
            if not match:
                report.add("record.location", "session filename must be SES-NNN-descriptive-title.md", record.path)
            elif record.data.get("session") != match.group(1):
                report.add("record.location", "session identity must match its filename prefix", record.path)


def _validate_project_graph(root: Path, records: list[Record], report: ValidationReport) -> None:
    projects = [record for record in records if record.kind == "project"]
    if not projects:
        return
    project = projects[0].data
    if project.get("protocol_version") != PROTOCOL_VERSION:
        report.add("protocol.version", f"expected protocol {PROTOCOL_VERSION}", projects[0].path)

    items: dict[str, Record] = {}
    for record in (record for record in records if record.kind == "work_item"):
        item_id = record.data.get("id")
        if not isinstance(item_id, str):
            continue
        if item_id in items:
            report.add("identity.duplicate", f"duplicate work-item identity {item_id}", record.path)
        else:
            items[item_id] = record

    root_id = project.get("root_work_item")
    declared_root = items.get(root_id) if isinstance(root_id, str) else None
    if declared_root is None:
        report.add("tree.root", f"declared root {root_id!r} does not exist", projects[0].path)
    roots = [record for record in items.values() if record.data.get("parent") is None]
    if len(roots) != 1:
        report.add("tree.root", f"expected exactly one parentless work item, found {len(roots)}", root / "work-items")
    elif roots[0].data.get("id") != root_id:
        report.add("tree.root", "parentless work item must equal PROJECT.md root_work_item", roots[0].path)

    children: dict[str, list[str]] = {item_id: [] for item_id in items}
    for item_id, record in items.items():
        parent = record.data.get("parent")
        if parent is not None:
            if parent not in items:
                report.add("tree.parent", f"parent {parent!r} does not exist", record.path)
            else:
                children[parent].append(item_id)

    _validate_cycles(items, report)

    revisions_by_item: dict[str, dict[str, Record]] = {item_id: {} for item_id in items}
    for record in (record for record in records if record.kind == "revision"):
        if record.owner not in revisions_by_item:
            report.add("revision.owner", "revision has no valid owning work item", record.path)
            continue
        revision = record.data.get("revision")
        if not isinstance(revision, str):
            continue
        if revision in revisions_by_item[record.owner]:
            report.add("identity.duplicate", f"duplicate revision {record.owner}@{revision}", record.path)
        revisions_by_item[record.owner][revision] = record

    for item_id, record in items.items():
        data = record.data
        state = data.get("state")
        active = data.get("active_revision")
        review_required = data.get("review_required")
        revisions = revisions_by_item[item_id]
        _validate_revision_chain(item_id, revisions, report)
        if state == "in-design":
            if active is not None:
                report.add("state.active_revision", "in-design must not have an active revision", record.path)
            if review_required is not False:
                report.add("state.review_required", "in-design must not set review_required", record.path)
        elif state in {"in-working", "resolved"}:
            if active not in revisions:
                report.add("state.active_revision", f"{state} must name an existing active revision", record.path)
            if state == "resolved":
                if review_required is not False:
                    report.add("state.review_required", "resolved must not set review_required", record.path)
                unresolved = [child for child in children[item_id] if items[child].data.get("state") != "resolved"]
                if unresolved:
                    report.add("state.resolved_children", f"resolved item has unresolved children: {', '.join(unresolved)}", record.path)
        if review_required is True and state != "in-working":
            report.add("state.review_required", "review_required is valid only while in-working", record.path)

    workspace_ids = set(project.get("workspace_ids", [])) if isinstance(project.get("workspace_ids"), list) else set()
    sessions: dict[str, Record] = {}
    provider_ids: dict[tuple[str, str], str] = {}
    for record in (record for record in records if record.kind == "session"):
        session_id = record.data.get("session")
        if isinstance(session_id, str):
            if session_id in sessions:
                report.add("identity.duplicate", f"duplicate session identity {session_id}", record.path)
            sessions[session_id] = record
        key = (str(record.data.get("provider")), str(record.data.get("provider_session_id")))
        if key in provider_ids:
            report.add("identity.duplicate", f"provider session is already registered as {provider_ids[key]}", record.path)
        elif None not in key:
            provider_ids[key] = str(session_id)
        for item_id in record.data.get("work_items", []):
            if item_id not in items:
                report.add("session.work_item", f"session references missing {item_id}", record.path)
        workspace_id = record.data.get("workspace_id")
        if workspace_id not in workspace_ids:
            report.add("session.workspace", f"workspace {workspace_id!r} is not declared by PROJECT.md", record.path)


def _validate_cycles(items: dict[str, Record], report: ValidationReport) -> None:
    for item_id in items:
        seen: set[str] = set()
        current: str | None = item_id
        while current in items:
            if current in seen:
                report.add("tree.cycle", f"parent cycle includes {current}", items[item_id].path)
                break
            seen.add(current)
            parent = items[current].data.get("parent")
            current = parent if isinstance(parent, str) else None


def _validate_revision_chain(item_id: str, revisions: dict[str, Record], report: ValidationReport) -> None:
    ordered: list[tuple[int, str, Record]] = []
    for revision, record in revisions.items():
        match = re.fullmatch(r"r([1-9][0-9]*)", revision)
        if match:
            ordered.append((int(match.group(1)), revision, record))
    ordered.sort()
    for index, (number, revision, record) in enumerate(ordered, start=1):
        if number != index:
            report.add("revision.sequence", f"{item_id} revisions must be contiguous from r1", record.path)
        expected = None if number == 1 else f"r{number - 1}"
        if record.data.get("supersedes") != expected:
            report.add("revision.chain", f"{revision} must supersede {expected!r}", record.path)


def _validate_links(root: Path, records: list[Record], report: ValidationReport) -> None:
    for record in records:
        for match in MARKDOWN_LINK.finditer(record.document.body):
            destination = match.group(1).strip()
            if destination.startswith("<") and destination.endswith(">"):
                destination = destination[1:-1]
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", destination) or destination.startswith("mailto:"):
                continue
            target_text, separator, anchor = destination.partition("#")
            target_text = unquote(target_text)
            target = record.path if not target_text else Path(os.path.normpath(record.path.parent / target_text))
            try:
                target.relative_to(root)
            except ValueError:
                report.add("link.escape", f"link escapes the canonical project: {destination}", record.path)
                continue
            parts = target.relative_to(root).parts
            if parts and parts[0] == "workspace-links":
                workspace_id = parts[1] if len(parts) > 1 else ""
                project_record = next((entry for entry in records if entry.kind == "project"), None)
                allowed = set(project_record.data.get("workspace_ids", [])) if project_record else set()
                if workspace_id not in allowed:
                    report.add("link.workspace", f"link uses undeclared workspace {workspace_id!r}", record.path)
            if not target.is_file():
                report.add("link.missing", f"link target does not exist: {destination}", record.path)
                continue
            if separator and anchor and not _has_anchor(target, anchor):
                report.add("link.anchor", f"heading anchor does not exist: {destination}", record.path)


def _has_anchor(path: Path, expected: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    counts: dict[str, int] = {}
    anchors: set[str] = set()
    for match in HEADING.finditer(text):
        base = _heading_slug(match.group(2))
        count = counts.get(base, 0)
        counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")
    return unquote(expected).lower() in anchors


def _heading_slug(text: str) -> str:
    text = re.sub(r"[`*_~]", "", text.strip().lower())
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", text).strip("-")


def _validate_git_safety(root: Path, report: ValidationReport) -> None:
    git_root = _git_root(root)
    if git_root is not None:
        tracked = _tracked_paths(git_root)
        for local_name in ("local", "workspace-links"):
            target = root / local_name
            try:
                relative = target.relative_to(git_root).as_posix()
            except ValueError:
                continue
            if any(path == relative or path.startswith(relative + "/") for path in tracked):
                report.add("git.local_tracked", f"{local_name}/ must not be tracked by Git", target)

    mappings = root / "local" / "workspaces"
    if not mappings.is_dir():
        return
    for mapping in mappings.rglob("*.yaml"):
        try:
            payload = json.loads(mapping.read_text(encoding="utf-8"))
            workspace = Path(payload["path"])
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
        workspace_git_root = _git_root(workspace)
        if workspace_git_root is None:
            continue
        tracked = _tracked_paths(workspace_git_root)
        try:
            selection = (workspace / ".techlead").relative_to(workspace_git_root).as_posix()
        except ValueError:
            continue
        if selection in tracked:
            report.add("git.selection_tracked", ".techlead selection symlink must not be tracked", workspace / ".techlead")


def _git_root(path: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else None


def _tracked_paths(git_root: Path) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(git_root), "ls-files", "-z"],
            check=False,
            capture_output=True,
        )
    except OSError:
        return set()
    if result.returncode != 0:
        return set()
    return {value.decode("utf-8", errors="replace") for value in result.stdout.split(b"\0") if value}
