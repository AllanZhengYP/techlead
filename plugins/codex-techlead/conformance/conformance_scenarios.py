"""Filesystem snapshots shared by source and packaged Protocol 2.0 validators."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


RecordSpec = tuple[str, dict[str, Any], str]
PROJECT_ID = "8d96a5d7-4127-4ef5-a3da-32ea927d951f"


def _project(*, root: str = "WI-001", workspaces: list[str] | None = None) -> RecordSpec:
    return (
        "PROJECT.md",
        {
            "protocol_version": "2.0",
            "project_id": PROJECT_ID,
            "title": "Fixture project",
            "root_work_item": root,
            "workspace_ids": workspaces or ["service-a"],
        },
        "# Fixture project\n",
    )


def _work(
    item_id: str,
    slug: str,
    title: str,
    *,
    work_type: str = "design",
    state: str = "in-design",
    parent: str | None = None,
    active_revision: str | None = None,
    review_required: bool = False,
    body: str = "",
) -> RecordSpec:
    return (
        f"work-items/{item_id}-{slug}/WORK.md",
        {
            "id": item_id,
            "title": title,
            "work_type": work_type,
            "state": state,
            "parent": parent,
            "active_revision": active_revision,
            "review_required": review_required,
        },
        body or f"# {item_id} — {title}\n",
    )


def _revision(item_dir: str, revision: str, title: str, supersedes: str | None) -> RecordSpec:
    slug = title.lower().replace(" ", "-")
    return (
        f"work-items/{item_dir}/revisions/{revision}-{slug}.md",
        {"revision": revision, "title": title, "supersedes": supersedes},
        f"# {title}\n\nSigned semantic baseline.\n",
    )


def initialization() -> list[RecordSpec]:
    return [
        _project(),
        _work("WI-001", "fixture-design", "Fixture design"),
    ]


def signed_decomposition() -> list[RecordSpec]:
    return [
        _project(),
        _work("WI-001", "fixture-design", "Fixture design", state="in-working", active_revision="r1"),
        _revision("WI-001-fixture-design", "r1", "Initial fixture design", None),
        _work(
            "WI-002",
            "implementation",
            "Implementation",
            work_type="implementation",
            state="in-working",
            parent="WI-001",
            active_revision="r1",
        ),
        _revision("WI-002-implementation", "r1", "Implementation contract", None),
        _work("WI-003", "verification", "Verification", work_type="verification", parent="WI-001"),
    ]


def session_continuity() -> list[RecordSpec]:
    records = signed_decomposition()
    records.append(
        (
            "sessions/SES-001-implement-fixture.md",
            {
                "session": "SES-001",
                "provider": "codex",
                "provider_session_id": "opaque-session-1",
                "role": "implementation",
                "status": "paused",
                "work_items": ["WI-002", "WI-003"],
                "workspace_id": "service-a",
            },
            "# Resume implementation\n",
        )
    )
    return records


def exception_rollup() -> list[RecordSpec]:
    return [
        _project(),
        _work(
            "WI-001",
            "fixture-design",
            "Fixture design",
            state="in-working",
            active_revision="r1",
            review_required=True,
            body="# Fixture design\n\n## Child verdict\n\n- WI-002 challenges an assumption.\n",
        ),
        _revision("WI-001-fixture-design", "r1", "Initial fixture design", None),
        _work(
            "WI-002",
            "exploration",
            "Exploration",
            work_type="exploration",
            state="resolved",
            parent="WI-001",
            active_revision="r1",
        ),
        _revision("WI-002-exploration", "r1", "Exploration question", None),
        _work(
            "WI-003",
            "implementation",
            "Implementation",
            work_type="implementation",
            state="in-working",
            parent="WI-001",
            active_revision="r1",
        ),
        _revision("WI-003-implementation", "r1", "Implementation contract", None),
    ]


def resolved_tree() -> list[RecordSpec]:
    return [
        _project(),
        _work("WI-001", "fixture-design", "Fixture design", state="resolved", active_revision="r1"),
        _revision("WI-001-fixture-design", "r1", "Initial fixture design", None),
        _work(
            "WI-002",
            "implementation",
            "Implementation",
            work_type="implementation",
            state="resolved",
            parent="WI-001",
            active_revision="r1",
        ),
        _revision("WI-002-implementation", "r1", "Implementation contract", None),
    ]


SCENARIOS = {
    "initialization": initialization(),
    "signed-decomposition": signed_decomposition(),
    "session-continuity": session_continuity(),
    "exception-rollup": exception_rollup(),
    "resolved-tree": resolved_tree(),
}


def copy_scenario(name: str) -> list[RecordSpec]:
    return deepcopy(SCENARIOS[name])
