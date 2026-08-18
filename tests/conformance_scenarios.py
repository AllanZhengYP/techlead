"""Provider-neutral state snapshots used as protocol conformance fixtures."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


RecordSpec = tuple[str, dict[str, Any], str]


def _roots(
    frontier: list[str],
    *,
    current: list[str] | None = None,
    historical: list[str] | None = None,
    facts: list[dict[str, Any]] | None = None,
    risks: dict[str, list[str]] | None = None,
    decisions: dict[str, dict[str, Any]] | None = None,
) -> list[RecordSpec]:
    risks = risks or {}
    decisions = decisions or {}
    risk_entries = [
        {
            "id": risk_id,
            "status": "OPEN",
            "owner": "fixture",
            "affected_work_items": affected,
            "mitigation_items": [],
            "evidence_refs": [],
            "residual_uncertainty": "Fixture uncertainty",
        }
        for risk_id, affected in risks.items()
    ]
    decision_entries = [dict({"id": decision_id}, **details) for decision_id, details in decisions.items()]
    risk_body = "# Risks\n" + "".join(f"\n## {risk_id} — Fixture risk\n\nTracked.\n" for risk_id in risks)
    decision_body = "# Decisions\n" + "".join(
        f"\n## {decision_id} — Fixture decision\n\nGoverning.\n" for decision_id in decisions
    )
    return [
        (".techlead/CHARTER.md", {"protocol_version": "1.0", "kind": "project_charter"}, "# Charter\n"),
        (
            ".techlead/OVERVIEW.md",
            {
                "protocol_version": "1.0",
                "kind": "project_overview",
                "current_resolutions": current or [],
                "historical_resolutions": historical or [],
                "current_facts": facts or [],
            },
            "# Overview\n",
        ),
        (
            ".techlead/FRONTIER.md",
            {"protocol_version": "1.0", "kind": "project_frontier", "work_items": frontier},
            "# Frontier\n",
        ),
        (
            ".techlead/RISKS.md",
            {"protocol_version": "1.0", "kind": "risk_register", "risks": risk_entries},
            risk_body,
        ),
        (
            ".techlead/DECISIONS.md",
            {"protocol_version": "1.0", "kind": "decision_register", "decisions": decision_entries},
            decision_body,
        ),
    ]


def _work(
    item_id: str,
    title: str,
    state: str,
    contract_id: str,
    *,
    revision: str = "r1",
    parents: list[str] | None = None,
    children: list[str] | None = None,
    dependencies: list[str] | None = None,
    dependents: list[str] | None = None,
    related: list[str] | None = None,
    replaces: list[str] | None = None,
    replaced_by: list[str] | None = None,
    transitions: list[str] | None = None,
    risks: list[str] | None = None,
    latest_attempt: str | None = None,
    latest_verification: str | None = None,
    target_node: str | None = None,
    from_revision: str | None = None,
) -> list[RecordSpec]:
    work = {
        "protocol_version": "1.0",
        "kind": "work_item",
        "id": item_id,
        "title": title,
        "state": state,
        "active_revision": revision,
        "parents": parents or [],
        "children": children or [],
        "dependencies": dependencies or [],
        "dependents": dependents or [],
        "related": related or [],
        "replaces": replaces or [],
        "replaced_by": replaced_by or [],
        "revision_transitions": transitions or [],
        "risk_ids": risks or [],
        "active_contract": f"revisions/{revision}.md",
        "latest_attempt": f"attempts/{latest_attempt}.md" if latest_attempt else None,
        "latest_verification": f"verifications/{latest_verification}.md" if latest_verification else None,
        "target_node": target_node,
        "from_revision": from_revision,
    }
    contract = {
        "protocol_version": "1.0",
        "kind": "assignment_contract",
        "id": contract_id,
        "work_item": item_id,
        "revision": revision,
        "context_refs": [],
        "governing_assumptions": [],
        "criteria": [{"id": "CR-001", "methods": ["deterministic"]}],
    }
    base = f".techlead/work-items/{item_id}"
    return [
        (f"{base}/WORK.md", work, f"# {item_id} — {title}\n"),
        (f"{base}/revisions/{revision}.md", contract, "# Contract\n\n## CR-001\n\nFixture criterion.\n"),
    ]


def _verification(
    item_id: str,
    verification_id: str,
    contract_id: str,
    *,
    method: str = "deterministic",
    criteria: list[str] | None = None,
    revision: str = "r1",
) -> RecordSpec:
    return (
        f".techlead/work-items/{item_id}/verifications/{verification_id}.md",
        {
            "protocol_version": "1.0",
            "kind": "verification",
            "id": verification_id,
            "work_item": item_id,
            "revision": revision,
            "contract_id": contract_id,
            "method": method,
            "criteria": criteria or ["CR-001"],
            "outcome": "PASS",
            "evidence_refs": ["tests/fixture-check"],
            "verifier_ref": "fixture",
        },
        "# Verification\n",
    )


def _resolution(
    item_id: str,
    resolution_id: str,
    contract_id: str,
    verification_ids: list[str],
    *,
    revision: str = "r1",
    decisions: list[str] | None = None,
) -> RecordSpec:
    return (
        f".techlead/work-items/{item_id}/resolutions/{revision}.md",
        {
            "protocol_version": "1.0",
            "kind": "resolution",
            "id": resolution_id,
            "work_item": item_id,
            "revision": revision,
            "contract_id": contract_id,
            "verification_ids": verification_ids,
            "consumed_resolutions": [],
            "consumed_assumptions": [],
            "produced_facts": [f"{item_id} fixture fact"],
            "affected_artifacts": [],
            "git_revisions": [],
            "decision_ids": decisions or [],
        },
        "# Resolution\n",
    )


def expansion() -> list[RecordSpec]:
    records = _roots(
        ["WI-100", "WI-110", "WI-120"], risks={"RISK-001": ["WI-100"]}
    )
    records += _work(
        "WI-100", "Deliver importer", "DECOMPOSED", "AC-100",
        children=["WI-110", "WI-120"], risks=["RISK-001"]
    )
    records += _work(
        "WI-110", "Validate parser", "READY", "AC-110",
        parents=["WI-100"], dependents=["WI-120"]
    )
    records += _work(
        "WI-120", "Implement importer", "BLOCKED", "AC-120",
        parents=["WI-100"], dependencies=["WI-110"]
    )
    return records


def resolution_release() -> list[RecordSpec]:
    records = _roots(
        ["WI-120"], current=["WI-110@r1"], historical=["WI-110@r1"],
        facts=[{"claim": "WI-110 fixture fact", "resolution_refs": ["WI-110@r1"]}],
        decisions={
            "DEC-001": {
                "status": "GOVERNING",
                "resolution_refs": ["WI-110@r1"],
                "superseded_by": [],
            }
        },
    )
    records += _work(
        "WI-110", "Validate parser", "RESOLVED", "AC-110",
        dependents=["WI-120"], latest_attempt="ATT-110", latest_verification="EV-112"
    )
    records[-1][1]["criteria"] = [
        {"id": "CR-001", "methods": ["deterministic", "independent_review"]}
    ]
    records += _work(
        "WI-120", "Implement importer", "READY", "AC-120",
        dependencies=["WI-110"]
    )
    records.append((
        ".techlead/work-items/WI-110/attempts/ATT-110.md",
        {
            "protocol_version": "1.0", "kind": "worker_result", "id": "ATT-110",
            "work_item": "WI-110", "revision": "r1", "contract_id": "AC-110",
            "outcome": "SUBMITTED", "session_ref": "fixture-worker",
            "changed_artifacts": [], "evidence_refs": ["tests/fixture-check"],
            "git_revisions": [], "affected_work_items": ["WI-120"]
        },
        "# Worker result\n",
    ))
    records.append(_verification("WI-110", "EV-111", "AC-110"))
    records.append(_verification(
        "WI-110", "EV-112", "AC-110", method="independent_review"
    ))
    records.append(_resolution(
        "WI-110", "RES-110", "AC-110", ["EV-111", "EV-112"], decisions=["DEC-001"]
    ))
    return records


def pivot_reconciliation() -> list[RecordSpec]:
    records = _roots(
        ["WI-110", "WI-210", "WI-220", "WI-300", "WI-310", "WI-320"],
        current=["WI-120@r1"],
        historical=["WI-110@r1", "WI-120@r1", "WI-130@r1"],
        facts=[{"claim": "WI-120 fixture fact", "resolution_refs": ["WI-120@r1"]}],
        risks={"RISK-001": ["WI-110", "WI-210"]},
        decisions={
            "DEC-001": {
                "status": "SUSPENDED",
                "resolution_refs": ["WI-110@r1"],
                "superseded_by": [],
            }
        },
    )
    records += _work(
        "WI-110", "Choose cache architecture", "REVISING", "AC-110",
        children=["WI-120", "WI-130"], dependents=["WI-210"],
        transitions=["WI-300"], risks=["RISK-001"]
    )
    records += _work(
        "WI-120", "Define serialization", "RESOLVED", "AC-120",
        parents=["WI-110"], latest_verification="EV-120"
    )
    records += _work(
        "WI-130", "Build local adapter", "INVALIDATED", "AC-130",
        parents=["WI-110"], related=["WI-320"], latest_verification="EV-130"
    )
    records += _work(
        "WI-210", "Build sync pipeline", "PENDING_PLAN_REVIEW", "AC-210",
        dependencies=["WI-110"], dependents=["WI-220"]
    )
    records += _work(
        "WI-220", "Benchmark sync", "BLOCKED", "AC-220",
        dependencies=["WI-210"]
    )
    records += _work(
        "WI-300", "Transition cache architecture", "DECOMPOSED", "AC-300",
        children=["WI-310", "WI-320"], target_node="WI-110", from_revision="r1"
    )
    records += _work(
        "WI-310", "Build shared-store adapter", "READY", "AC-310",
        parents=["WI-300"]
    )
    records += _work(
        "WI-320", "Reconcile local artifacts", "READY", "AC-320",
        parents=["WI-300"], related=["WI-130"]
    )
    for item_id, contract_id, verification_id, resolution_id in (
        ("WI-110", "AC-110", "EV-110", "RES-110"),
        ("WI-120", "AC-120", "EV-120", "RES-120"),
        ("WI-130", "AC-130", "EV-130", "RES-130"),
    ):
        records.append(_verification(item_id, verification_id, contract_id))
        records.append(_resolution(
            item_id, resolution_id, contract_id, [verification_id],
            decisions=["DEC-001"] if item_id == "WI-110" else []
        ))
    records.append((
        ".techlead/work-items/WI-130/INVALIDATION.md",
        {
            "protocol_version": "1.0", "kind": "invalidation", "id": "INV-130",
            "work_item": "WI-130", "invalidated_revision": "r1",
            "transition_item": "WI-300", "invalidated_facts": ["Local adapter is current"],
            "affected_artifacts": ["src/local-adapter"], "migration_items": ["WI-320"]
        },
        "# Invalidation\n",
    ))
    return records


SCENARIOS = {
    "expansion": expansion,
    "resolution-release": resolution_release,
    "pivot-reconciliation": pivot_reconciliation,
}


def copy_scenario(name: str) -> list[RecordSpec]:
    return deepcopy(SCENARIOS[name]())
