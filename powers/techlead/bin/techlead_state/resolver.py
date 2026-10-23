"""Project discovery and provider-neutral per-user registry support."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .frontmatter import FrontMatterError, dump_document, parse_file
from .schema import validate_schema


class ResolutionError(RuntimeError):
    """Raised when a canonical project cannot be selected safely."""


@dataclass(frozen=True)
class ProjectResolution:
    project_root: Path
    project_id: str
    source: str


def default_registry_path() -> Path:
    override = os.environ.get("TECHLEAD_STATE_HOME")
    if override:
        return Path(override).expanduser() / "projects.json"
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else Path.home() / ".local" / "state"
    return base / "techlead" / "projects.json"


def read_registry(path: str | Path | None = None) -> dict[str, str]:
    registry = Path(path) if path else default_registry_path()
    if not registry.is_file():
        return {}
    try:
        payload = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolutionError(f"cannot read Tech Lead registry {registry}: {exc}") from exc
    projects = payload.get("projects", {})
    if not isinstance(projects, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in projects.items()):
        raise ResolutionError(f"invalid Tech Lead registry {registry}")
    return dict(projects)


def write_registry(projects: dict[str, str], path: str | Path | None = None) -> Path:
    registry = Path(path) if path else default_registry_path()
    registry.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"version": 1, "projects": dict(sorted(projects.items()))}, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".projects-", suffix=".json", dir=registry.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, registry)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return registry


def register_project(project_root: str | Path, *, registry_path: str | Path | None = None) -> str:
    root = Path(project_root).expanduser().resolve()
    project_id = _project_id(root)
    projects = read_registry(registry_path)
    projects[project_id] = str(root)
    write_registry(projects, registry_path)
    return project_id


def register_control_root(control_root: str | Path, *, registry_path: str | Path | None = None) -> list[str]:
    root = Path(control_root).expanduser().resolve()
    projects = read_registry(registry_path)
    registered: list[str] = []
    if not root.is_dir():
        raise ResolutionError(f"control root does not exist: {root}")
    for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
        if not (candidate / "PROJECT.md").is_file():
            continue
        project_id = _project_id(candidate)
        projects[project_id] = str(candidate.resolve())
        registered.append(project_id)
    write_registry(projects, registry_path)
    return registered


def resolve_project(
    location: str | Path = ".",
    *,
    project_id: str | None = None,
    registry_path: str | Path | None = None,
) -> ProjectResolution:
    start = Path(location).expanduser().resolve()
    if start.is_file():
        start = start.parent

    direct = _direct_project(start)
    if direct is not None:
        actual_id = _project_id(direct)
        if project_id is not None and actual_id != project_id:
            raise ResolutionError(f"selected project is {actual_id}, not requested {project_id}")
        return ProjectResolution(direct, actual_id, "project-root")

    selection = _find_upward(start, ".techlead")
    if selection is not None:
        if not selection.is_dir() or not (selection / "PROJECT.md").is_file():
            raise ResolutionError(f"stale .techlead selection: {selection}")
        selected_root = selection.resolve()
        actual_id = _project_id(selected_root)
        if project_id is None or project_id == actual_id:
            return ProjectResolution(selected_root, actual_id, "workspace-selection")

    projects = read_registry(registry_path)
    if project_id is not None:
        return _resolve_registry_entry(project_id, projects, "explicit-project")

    locator_path = _find_upward(start, ".techlead-project")
    if locator_path is None:
        raise ResolutionError("no canonical project, .techlead selection, or .techlead-project locator found")
    locator = read_locator(locator_path)
    candidates: list[ProjectResolution] = []
    stale: list[str] = []
    for candidate_id in locator["project_ids"]:
        try:
            candidates.append(_resolve_registry_entry(candidate_id, projects, "workspace-locator"))
        except ResolutionError:
            stale.append(candidate_id)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ResolutionError(f"no locator project is available in the local registry; stale IDs: {', '.join(stale)}")
    ids = ", ".join(candidate.project_id for candidate in candidates)
    raise ResolutionError(f"workspace is bound to multiple projects ({ids}); specify a project UUID or select .techlead")


def read_locator(path: str | Path) -> dict[str, Any]:
    locator_path = Path(path)
    try:
        document = parse_file(locator_path)
    except (OSError, FrontMatterError) as exc:
        raise ResolutionError(str(exc)) from exc
    schema_path = Path(__file__).resolve().parents[2] / "core" / "schemas" / "workspace-locator.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolutionError(f"cannot load workspace locator schema: {exc}") from exc
    issues = validate_schema(document.metadata, schema)
    if issues:
        rendered = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
        raise ResolutionError(f"invalid workspace locator {locator_path}: {rendered}")
    return document.metadata


def write_locator(path: str | Path, *, workspace_id: str, project_ids: list[str]) -> None:
    target = Path(path)
    target.write_text(
        dump_document({"workspace_id": workspace_id, "project_ids": sorted(set(project_ids))}),
        encoding="utf-8",
    )


def _direct_project(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / "PROJECT.md").is_file():
            return candidate.resolve()
    return None


def _find_upward(start: Path, name: str) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / name
        if candidate.exists() or candidate.is_symlink():
            return candidate
    return None


def _project_id(root: Path) -> str:
    path = root / "PROJECT.md"
    try:
        value = parse_file(path).metadata.get("project_id")
    except (OSError, FrontMatterError) as exc:
        raise ResolutionError(f"cannot read project identity from {path}: {exc}") from exc
    if not isinstance(value, str) or not value:
        raise ResolutionError(f"PROJECT.md at {root} has no valid project_id")
    return value


def _resolve_registry_entry(project_id: str, projects: dict[str, str], source: str) -> ProjectResolution:
    registered = projects.get(project_id)
    if registered is None:
        raise ResolutionError(f"project {project_id} is not registered on this machine")
    root = Path(registered).expanduser().resolve()
    if not (root / "PROJECT.md").is_file():
        raise ResolutionError(f"registered project path is stale: {root}")
    actual_id = _project_id(root)
    if actual_id != project_id:
        raise ResolutionError(f"registry maps {project_id} to a different project identity {actual_id}")
    return ProjectResolution(root, actual_id, source)
