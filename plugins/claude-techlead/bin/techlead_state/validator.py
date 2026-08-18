"""Cross-record validator for `.techlead/` protocol state."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable

from .frontmatter import FrontMatterError, ParsedDocument, parse_file
from .schema import validate_schema


PROTOCOL_VERSION = "1.0"
TERMINAL_STATES = {"RESOLVED", "REPLACED", "INVALIDATED"}
ASSIGNMENT_STATES = {
    "READY", "IN_PROGRESS", "BLOCKED", "SUBMITTED", "VERIFYING",
    "NEEDS_CHANGES", "PENDING_HUMAN", "PENDING_PLAN_REVIEW",
}
ROOT_RECORDS = {
    "CHARTER.md": "project_charter",
    "OVERVIEW.md": "project_overview",
    "FRONTIER.md": "project_frontier",
    "RISKS.md": "risk_register",
    "DECISIONS.md": "decision_register",
}
RESOLUTION_REF = re.compile(r"^(WI-[0-9]+)@(r[1-9][0-9]*)$")
HEADING_ID = re.compile(r"^##\s+((?:RISK|DEC)-[0-9]+)\b", re.MULTILINE)


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
        rendered = None
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
    document: ParsedDocument

    @property
    def data(self) -> dict[str, Any]:
        return self.document.metadata

    @property
    def kind(self) -> str | None:
        value = self.data.get("kind")
        return value if isinstance(value, str) else None


def validate_project(project_root: str | Path, *, schema_dir: str | Path | None = None) -> ValidationReport:
    root = Path(project_root).resolve()
    state_root = root if root.name == ".techlead" else root / ".techlead"
    actual_project_root = state_root.parent
    report = ValidationReport(project_root=actual_project_root)
    if not state_root.is_dir():
        report.add("state.missing", "expected a .techlead directory", state_root)
        return report

    schemas = _load_schemas(Path(schema_dir) if schema_dir else _default_schema_dir(), report)
    records = _load_records(state_root, report)
    report.records_checked = len(records)

    for record in records:
        if record.kind not in schemas:
            report.add("schema.kind", f"unknown or missing record kind {record.kind!r}", record.path)
            continue
        for issue in validate_schema(record.data, schemas[record.kind]):
            report.add("schema.invalid", f"{issue.path}: {issue.message}", record.path)

    _validate_locations(state_root, records, report)
    _validate_records(state_root, records, report)
    return report


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


def _load_records(state_root: Path, report: ValidationReport) -> list[Record]:
    paths: list[Path] = []
    for filename in ROOT_RECORDS:
        path = state_root / filename
        if not path.is_file():
            report.add("record.missing", f"required project record {filename} is missing", path)
        else:
            paths.append(path)

    items_root = state_root / "work-items"
    if not items_root.is_dir():
        report.add("record.missing", "work-items directory is missing", items_root)
    else:
        for item_dir in sorted(path for path in items_root.iterdir() if path.is_dir()):
            work = item_dir / "WORK.md"
            if not work.is_file():
                report.add("record.missing", "work-item directory is missing WORK.md", work)
            else:
                paths.append(work)
            for directory in ("revisions", "attempts", "verifications", "resolutions"):
                child = item_dir / directory
                if child.is_dir():
                    paths.extend(sorted(child.glob("*.md")))
            invalidation = item_dir / "INVALIDATION.md"
            if invalidation.is_file():
                paths.append(invalidation)

    records: list[Record] = []
    for path in paths:
        try:
            records.append(Record(path=path, document=parse_file(path)))
        except (OSError, FrontMatterError) as exc:
            report.add("record.parse", str(exc), path)
    return records


def _validate_locations(state_root: Path, records: list[Record], report: ValidationReport) -> None:
    by_path = {record.path: record for record in records}
    for filename, kind in ROOT_RECORDS.items():
        record = by_path.get(state_root / filename)
        if record and record.kind != kind:
            report.add("record.location", f"{filename} must have kind {kind}", record.path)

    for record in records:
        try:
            relative = record.path.relative_to(state_root / "work-items")
        except ValueError:
            continue
        parts = relative.parts
        if len(parts) < 2:
            report.add("record.location", "record is not inside a work-item directory", record.path)
            continue
        item_id = parts[0]
        if parts[1] == "WORK.md":
            if len(parts) != 2 or record.kind != "work_item":
                report.add("record.location", "WORK.md must be a work_item record", record.path)
            if record.data.get("id") != item_id:
                report.add("record.location", f"directory {item_id} must match work-item ID", record.path)
        elif parts[1] == "revisions":
            _expect_location(record, "assignment_contract", report)
            if record.data.get("revision") != record.path.stem:
                report.add("record.location", "contract filename must match its revision", record.path)
        elif parts[1] == "attempts":
            if record.kind not in {"worker_result", "plan_review_result"}:
                report.add("record.location", "attempts may contain worker_result or plan_review_result", record.path)
            if record.data.get("id") != record.path.stem:
                report.add("record.location", "attempt filename must match its ID", record.path)
        elif parts[1] == "verifications":
            _expect_location(record, "verification", report)
            if record.data.get("id") != record.path.stem:
                report.add("record.location", "verification filename must match its ID", record.path)
        elif parts[1] == "resolutions":
            _expect_location(record, "resolution", report)
            if record.data.get("revision") != record.path.stem:
                report.add("record.location", "resolution filename must match its revision", record.path)
        elif parts[1] == "INVALIDATION.md":
            _expect_location(record, "invalidation", report)
        else:
            report.add("record.location", "record is outside a protocol record directory", record.path)


def _expect_location(record: Record, kind: str, report: ValidationReport) -> None:
    if record.kind != kind:
        report.add("record.location", f"expected record kind {kind}, got {record.kind!r}", record.path)


def _validate_records(state_root: Path, records: list[Record], report: ValidationReport) -> None:
    roots = {record.kind: record for record in records if record.path.parent == state_root}
    work_items = _index_by_kind(records, "work_item", report)
    contracts = _index_by_kind(records, "assignment_contract", report)
    attempts = {
        **_index_by_kind(records, "worker_result", report),
        **_index_by_kind(records, "plan_review_result", report),
    }
    verifications = _index_by_kind(records, "verification", report)
    resolutions = _index_by_kind(records, "resolution", report)
    invalidations = _index_by_kind(records, "invalidation", report)
    report.work_items_checked = len(work_items)

    _validate_global_ids(records, roots, report)
    _validate_registers(roots, report)
    _validate_graph(work_items, report)
    _validate_acyclic(work_items, "children", "decomposition", report)
    _validate_acyclic(work_items, "dependencies", "dependency", report)

    resolution_by_key: dict[tuple[str, str], Record] = {}
    for record in resolutions.values():
        key = (record.data.get("work_item"), record.data.get("revision"))
        if key in resolution_by_key:
            report.add("resolution.duplicate", f"multiple resolutions exist for {key[0]}@{key[1]}", record.path)
        else:
            resolution_by_key[key] = record

    for record in records:
        if record.kind == "assignment_contract":
            _validate_owned_record(record, work_items, report)
            _validate_criterion_ids(record, report)
        elif record.kind in {"worker_result", "plan_review_result", "verification", "resolution"}:
            _validate_owned_record(record, work_items, report)
            _validate_contract_reference(record, contracts, report)
        elif record.kind == "invalidation":
            _validate_owned_record(record, work_items, report)

    for record in attempts.values():
        _validate_attempt(record, work_items, attempts, report)
    for record in verifications.values():
        _validate_verification(record, contracts, report)
    for record in resolutions.values():
        _validate_resolution(
            record, contracts, verifications, resolution_by_key, roots, report
        )
    for record in invalidations.values():
        _validate_invalidation(record, work_items, resolution_by_key, report)

    _validate_work_lifecycle(
        work_items, contracts, attempts, verifications, resolution_by_key,
        invalidations, roots, report
    )
    _validate_registry_references(roots, work_items, resolution_by_key, report)
    _validate_project_projections(roots, work_items, resolution_by_key, report)


def _index_by_kind(records: Iterable[Record], kind: str, report: ValidationReport) -> dict[str, Record]:
    result: dict[str, Record] = {}
    for record in records:
        if record.kind != kind:
            continue
        identifier = record.data.get("id")
        if not isinstance(identifier, str):
            continue
        if identifier in result:
            report.add("id.duplicate", f"duplicate {kind} ID {identifier}", record.path)
        else:
            result[identifier] = record
    return result


def _validate_global_ids(records: list[Record], roots: dict[str | None, Record], report: ValidationReport) -> None:
    seen: dict[str, Path] = {}
    for record in records:
        identifier = record.data.get("id")
        if isinstance(identifier, str):
            if identifier in seen:
                report.add("id.duplicate", f"ID {identifier} is also used by {seen[identifier]}", record.path)
            else:
                seen[identifier] = record.path
    for kind, field in (("risk_register", "risks"), ("decision_register", "decisions")):
        record = roots.get(kind)
        if not record:
            continue
        for entry in record.data.get(field, []):
            identifier = entry.get("id") if isinstance(entry, dict) else None
            if not isinstance(identifier, str):
                continue
            if identifier in seen:
                report.add("id.duplicate", f"ID {identifier} is also used by {seen[identifier]}", record.path)
            else:
                seen[identifier] = record.path


def _validate_registers(roots: dict[str | None, Record], report: ValidationReport) -> None:
    expectations = {
        "project_overview": {"current_resolutions", "historical_resolutions", "current_facts"},
        "project_frontier": {"work_items"},
        "risk_register": {"risks"},
        "decision_register": {"decisions"},
    }
    for kind, fields in expectations.items():
        record = roots.get(kind)
        if not record:
            continue
        for field_name in fields:
            if field_name not in record.data:
                report.add("record.field", f"{kind} requires {field_name}", record.path)

    for kind, field, prefix in (
        ("risk_register", "risks", "RISK-"),
        ("decision_register", "decisions", "DEC-"),
    ):
        record = roots.get(kind)
        if not record:
            continue
        headings = {match for match in HEADING_ID.findall(record.document.body) if match.startswith(prefix)}
        declared = {
            entry.get("id") for entry in record.data.get(field, [])
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        }
        if len(declared) != len(record.data.get(field, [])):
            report.add("register.index", f"{field} must contain unique IDs", record.path)
        if headings != declared:
            missing = sorted(declared - headings)
            extra = sorted(headings - declared)
            report.add(
                "register.index",
                f"{field} disagrees with body headings (missing headings={missing}, unindexed headings={extra})",
                record.path,
            )


def _validate_graph(work_items: dict[str, Record], report: ValidationReport) -> None:
    pairs = (
        ("children", "parents"),
        ("parents", "children"),
        ("dependencies", "dependents"),
        ("dependents", "dependencies"),
        ("related", "related"),
        ("replaces", "replaced_by"),
        ("replaced_by", "replaces"),
    )
    for item_id, record in work_items.items():
        for field_name, backlink in pairs:
            for target_id in record.data.get(field_name, []):
                if target_id == item_id:
                    report.add("graph.self", f"{field_name} may not reference the item itself", record.path)
                    continue
                target = work_items.get(target_id)
                if not target:
                    report.add("reference.missing", f"{field_name} references missing work item {target_id}", record.path)
                elif item_id not in target.data.get(backlink, []):
                    report.add("graph.backlink", f"{target_id}.{backlink} must contain {item_id}", record.path)


def _validate_acyclic(
    work_items: dict[str, Record], field_name: str, graph_name: str, report: ValidationReport
) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item_id: str, trail: list[str]) -> None:
        if item_id in visiting:
            cycle = trail[trail.index(item_id):] + [item_id]
            report.add("graph.cycle", f"{graph_name} cycle: {' -> '.join(cycle)}", work_items[item_id].path)
            return
        if item_id in visited:
            return
        visiting.add(item_id)
        trail.append(item_id)
        for target in work_items[item_id].data.get(field_name, []):
            if target in work_items:
                visit(target, trail)
        trail.pop()
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in work_items:
        visit(item_id, [])


def _validate_owned_record(record: Record, work_items: dict[str, Record], report: ValidationReport) -> None:
    item_id = record.data.get("work_item")
    item = work_items.get(item_id)
    if not item:
        report.add("reference.missing", f"work_item references missing item {item_id!r}", record.path)
        return
    try:
        owner_dir = record.path.relative_to(item.path.parent).parts[0]
    except ValueError:
        report.add("record.owner", f"record for {item_id} is outside that item's directory", record.path)
        return
    if owner_dir not in {"revisions", "attempts", "verifications", "resolutions", "INVALIDATION.md"}:
        report.add("record.owner", f"record for {item_id} is outside a supported item directory", record.path)


def _validate_criterion_ids(contract: Record, report: ValidationReport) -> None:
    ids = [criterion.get("id") for criterion in contract.data.get("criteria", []) if isinstance(criterion, dict)]
    if len(ids) != len(set(ids)):
        report.add("contract.criteria", "criterion IDs must be unique within a contract", contract.path)


def _validate_contract_reference(record: Record, contracts: dict[str, Record], report: ValidationReport) -> None:
    contract_id = record.data.get("contract_id")
    contract = contracts.get(contract_id)
    if not contract:
        report.add("reference.missing", f"contract_id references missing contract {contract_id!r}", record.path)
        return
    if contract.data.get("work_item") != record.data.get("work_item") or contract.data.get("revision") != record.data.get("revision"):
        report.add("reference.mismatch", "record work item/revision does not match its contract", record.path)


def _validate_attempt(
    record: Record, work_items: dict[str, Record], attempts: dict[str, Record], report: ValidationReport
) -> None:
    for item_id in record.data.get("affected_work_items", []):
        if item_id not in work_items:
            report.add("reference.missing", f"affected_work_items references missing {item_id}", record.path)
    if record.kind == "plan_review_result":
        source = record.data.get("source_attempt")
        source_record = attempts.get(source)
        if not source_record:
            report.add("reference.missing", f"source_attempt references missing {source!r}", record.path)
        elif source_record.kind != "worker_result":
            report.add("reference.mismatch", "source_attempt must reference a worker_result", record.path)


def _validate_verification(record: Record, contracts: dict[str, Record], report: ValidationReport) -> None:
    contract = contracts.get(record.data.get("contract_id"))
    if not contract:
        return
    allowed = {criterion.get("id") for criterion in contract.data.get("criteria", []) if isinstance(criterion, dict)}
    unknown = sorted(set(record.data.get("criteria", [])) - allowed)
    if unknown:
        report.add("verification.criteria", f"verification references criteria outside its contract: {unknown}", record.path)


def _validate_resolution(
    record: Record,
    contracts: dict[str, Record],
    verifications: dict[str, Record],
    resolution_by_key: dict[tuple[str, str], Record],
    roots: dict[str | None, Record],
    report: ValidationReport,
) -> None:
    contract = contracts.get(record.data.get("contract_id"))
    selected: list[Record] = []
    for verification_id in record.data.get("verification_ids", []):
        verification = verifications.get(verification_id)
        if not verification:
            report.add("reference.missing", f"verification_ids references missing {verification_id}", record.path)
            continue
        selected.append(verification)
        if verification.data.get("work_item") != record.data.get("work_item") or verification.data.get("revision") != record.data.get("revision"):
            report.add("reference.mismatch", f"verification {verification_id} evaluates another item/revision", record.path)
        if verification.data.get("contract_id") != record.data.get("contract_id"):
            report.add("reference.mismatch", f"verification {verification_id} evaluates another contract", record.path)
        if verification.data.get("outcome") != "PASS":
            report.add("resolution.verification", f"verification {verification_id} did not PASS", record.path)

    if contract:
        coverage = {
            (criterion, verification.data.get("method"))
            for verification in selected
            if verification.data.get("outcome") == "PASS"
            for criterion in verification.data.get("criteria", [])
        }
        required = {
            (criterion.get("id"), method)
            for criterion in contract.data.get("criteria", [])
            if isinstance(criterion, dict)
            for method in criterion.get("methods", [])
        }
        missing = sorted(required - coverage)
        if missing:
            report.add("resolution.coverage", f"required criterion methods are not covered: {missing}", record.path)

    for reference in record.data.get("consumed_resolutions", []):
        key = _parse_resolution_ref(reference)
        if not key or key not in resolution_by_key:
            report.add("reference.missing", f"consumed_resolutions references missing {reference!r}", record.path)

    decision_record = roots.get("decision_register")
    decisions = {
        entry.get("id") for entry in decision_record.data.get("decisions", [])
        if isinstance(entry, dict)
    } if decision_record else set()
    for decision_id in record.data.get("decision_ids", []):
        if decision_id not in decisions:
            report.add("reference.missing", f"decision_ids references missing {decision_id}", record.path)


def _validate_invalidation(
    record: Record,
    work_items: dict[str, Record],
    resolution_by_key: dict[tuple[str, str], Record],
    report: ValidationReport,
) -> None:
    item_id = record.data.get("work_item")
    revision = record.data.get("invalidated_revision")
    if (item_id, revision) not in resolution_by_key:
        report.add("reference.missing", f"invalidation references unresolved revision {item_id}@{revision}", record.path)
    transition = work_items.get(record.data.get("transition_item"))
    if not transition or not transition.data.get("target_node"):
        report.add("invalidation.transition", "transition_item must reference a revision-transition work item", record.path)
    for migration_id in record.data.get("migration_items", []):
        if migration_id not in work_items:
            report.add("reference.missing", f"migration_items references missing {migration_id}", record.path)


def _validate_work_lifecycle(
    work_items: dict[str, Record],
    contracts: dict[str, Record],
    attempts: dict[str, Record],
    verifications: dict[str, Record],
    resolution_by_key: dict[tuple[str, str], Record],
    invalidations: dict[str, Record],
    roots: dict[str | None, Record],
    report: ValidationReport,
) -> None:
    risks_record = roots.get("risk_register")
    risk_ids = {
        entry.get("id") for entry in risks_record.data.get("risks", [])
        if isinstance(entry, dict)
    } if risks_record else set()
    invalidation_by_item = {record.data.get("work_item"): record for record in invalidations.values()}

    for item_id, record in work_items.items():
        data = record.data
        state = data.get("state")
        revision = data.get("active_revision")
        for risk_id in data.get("risk_ids", []):
            if risk_id not in risk_ids:
                report.add("reference.missing", f"risk_ids references missing {risk_id}", record.path)

        contract = _resolve_item_pointer(record, data.get("active_contract"), "revisions", report)
        if state != "DRAFT" and contract is None:
            report.add("lifecycle.contract", f"{state} item must point to its active contract", record.path)
        if contract and contract.data.get("id") not in contracts:
            report.add("reference.mismatch", "active_contract does not reference a known contract", record.path)
        if contract and (contract.data.get("work_item"), contract.data.get("revision")) != (item_id, revision):
            report.add("reference.mismatch", "active_contract does not match the active work-item revision", record.path)

        attempt = _resolve_item_pointer(record, data.get("latest_attempt"), "attempts", report)
        if attempt and attempt.data.get("id") not in attempts:
            report.add("reference.mismatch", "latest_attempt does not reference a known attempt", record.path)
        if attempt and (attempt.data.get("work_item"), attempt.data.get("revision")) != (item_id, revision):
            report.add("reference.mismatch", "latest_attempt does not match the active work-item revision", record.path)
        verification = _resolve_item_pointer(record, data.get("latest_verification"), "verifications", report)
        if verification and verification.data.get("id") not in verifications:
            report.add("reference.mismatch", "latest_verification does not reference a known verification", record.path)
        if verification and (verification.data.get("work_item"), verification.data.get("revision")) != (item_id, revision):
            report.add("reference.mismatch", "latest_verification does not match the active work-item revision", record.path)

        if state == "READY":
            unresolved = sorted(
                dependency for dependency in data.get("dependencies", [])
                if dependency in work_items and work_items[dependency].data.get("state") != "RESOLVED"
            )
            if unresolved:
                report.add("lifecycle.ready", f"READY item has unresolved dependencies: {unresolved}", record.path)
        if state == "DECOMPOSED" and not data.get("children"):
            report.add("lifecycle.decomposed", "DECOMPOSED item must have children", record.path)
        if state == "RESOLVED" and (item_id, revision) not in resolution_by_key:
            report.add("lifecycle.resolved", "RESOLVED item lacks a resolution for its active revision", record.path)
        if state == "INVALIDATED" and item_id not in invalidation_by_item:
            report.add("lifecycle.invalidated", "INVALIDATED item lacks INVALIDATION.md", record.path)
        if state == "REPLACED" and not data.get("replaced_by"):
            report.add("lifecycle.replaced", "REPLACED item must name its replacement", record.path)
        if state == "REVISING":
            transitions = data.get("revision_transitions", [])
            active = [
                transition_id for transition_id in transitions
                if transition_id in work_items and work_items[transition_id].data.get("state") not in TERMINAL_STATES
            ]
            if not active:
                report.add("lifecycle.revising", "REVISING item must have an unresolved revision transition", record.path)

        target_id = data.get("target_node")
        from_revision = data.get("from_revision")
        if bool(target_id) != bool(from_revision):
            report.add("transition.fields", "target_node and from_revision must be set together", record.path)
        if target_id:
            target = work_items.get(target_id)
            if not target:
                report.add("reference.missing", f"target_node references missing {target_id}", record.path)
            else:
                if item_id not in target.data.get("revision_transitions", []):
                    report.add("graph.backlink", f"{target_id}.revision_transitions must contain {item_id}", record.path)
                if (target_id, from_revision) not in resolution_by_key:
                    report.add("transition.source", f"transition source {target_id}@{from_revision} is not resolved", record.path)

        for transition_id in data.get("revision_transitions", []):
            transition = work_items.get(transition_id)
            if not transition:
                report.add("reference.missing", f"revision_transitions references missing {transition_id}", record.path)
            elif transition.data.get("target_node") != item_id:
                report.add("reference.mismatch", f"{transition_id} does not target {item_id}", record.path)


def _validate_registry_references(
    roots: dict[str | None, Record],
    work_items: dict[str, Record],
    resolution_by_key: dict[tuple[str, str], Record],
    report: ValidationReport,
) -> None:
    risk_record = roots.get("risk_register")
    if risk_record:
        for risk in risk_record.data.get("risks", []):
            if not isinstance(risk, dict):
                continue
            for field_name in ("affected_work_items", "mitigation_items"):
                for item_id in risk.get(field_name, []):
                    if item_id not in work_items:
                        report.add(
                            "reference.missing",
                            f"risk {risk.get('id')} {field_name} references missing {item_id}",
                            risk_record.path,
                        )
            for reference in risk.get("evidence_refs", []):
                key = _parse_resolution_ref(reference)
                if key and key not in resolution_by_key:
                    report.add(
                        "reference.missing",
                        f"risk {risk.get('id')} evidence references missing {reference}",
                        risk_record.path,
                    )

    decision_record = roots.get("decision_register")
    if not decision_record:
        return
    decisions = {
        decision.get("id"): decision
        for decision in decision_record.data.get("decisions", [])
        if isinstance(decision, dict) and isinstance(decision.get("id"), str)
    }
    for decision_id, decision in decisions.items():
        if decision.get("status") == "SUPERSEDED" and not decision.get("superseded_by"):
            report.add(
                "decision.supersession",
                f"superseded decision {decision_id} must identify its successor",
                decision_record.path,
            )
        for successor in decision.get("superseded_by", []):
            if successor not in decisions:
                report.add(
                    "reference.missing",
                    f"decision {decision_id} superseded_by references missing {successor}",
                    decision_record.path,
                )
        for reference in decision.get("resolution_refs", []):
            key = _parse_resolution_ref(reference)
            resolution = resolution_by_key.get(key) if key else None
            if not resolution:
                report.add(
                    "reference.missing",
                    f"decision {decision_id} references missing resolution {reference!r}",
                    decision_record.path,
                )
            elif decision_id not in resolution.data.get("decision_ids", []):
                report.add(
                    "reference.mismatch",
                    f"resolution {reference} must link back to decision {decision_id}",
                    decision_record.path,
                )


def _resolve_item_pointer(
    item: Record, pointer: Any, expected_directory: str, report: ValidationReport
) -> Record | None:
    if pointer is None:
        return None
    if not isinstance(pointer, str) or not _safe_relative(pointer):
        report.add("reference.path", f"invalid repository-relative pointer {pointer!r}", item.path)
        return None
    path = item.path.parent / Path(pointer)
    try:
        path.relative_to(item.path.parent)
    except ValueError:
        report.add("reference.path", f"pointer escapes work-item directory: {pointer}", item.path)
        return None
    if not path.is_file():
        report.add("reference.missing", f"pointer does not exist: {pointer}", item.path)
        return None
    if PurePosixPath(pointer).parts[0] != expected_directory:
        report.add("reference.path", f"pointer must be inside {expected_directory}/", item.path)
        return None
    try:
        return Record(path=path, document=parse_file(path))
    except (OSError, FrontMatterError) as exc:
        report.add("record.parse", str(exc), path)
        return None


def _validate_project_projections(
    roots: dict[str | None, Record],
    work_items: dict[str, Record],
    resolution_by_key: dict[tuple[str, str], Record],
    report: ValidationReport,
) -> None:
    frontier = roots.get("project_frontier")
    if frontier:
        expected = {item_id for item_id, item in work_items.items() if item.data.get("state") not in TERMINAL_STATES}
        actual = set(frontier.data.get("work_items", []))
        if actual != expected:
            report.add(
                "frontier.projection",
                f"frontier differs from unresolved graph (missing={sorted(expected - actual)}, extra={sorted(actual - expected)})",
                frontier.path,
            )

    overview = roots.get("project_overview")
    if not overview:
        return
    expected_historical = {f"{item_id}@{revision}" for item_id, revision in resolution_by_key}
    expected_current = {
        f"{item_id}@{item.data.get('active_revision')}"
        for item_id, item in work_items.items()
        if item.data.get("state") == "RESOLVED"
        and (item_id, item.data.get("active_revision")) in resolution_by_key
    }
    actual_historical = set(overview.data.get("historical_resolutions", []))
    actual_current = set(overview.data.get("current_resolutions", []))
    for reference in actual_historical | actual_current:
        if not _parse_resolution_ref(reference):
            report.add("overview.reference", f"invalid resolution reference {reference!r}", overview.path)
    if actual_historical != expected_historical:
        report.add(
            "overview.history",
            f"historical index differs from resolutions (missing={sorted(expected_historical - actual_historical)}, extra={sorted(actual_historical - expected_historical)})",
            overview.path,
        )
    if actual_current != expected_current:
        report.add(
            "overview.current",
            f"current index differs from authoritative resolutions (missing={sorted(expected_current - actual_current)}, extra={sorted(actual_current - expected_current)})",
            overview.path,
        )
    for index, fact in enumerate(overview.data.get("current_facts", [])):
        if not isinstance(fact, dict):
            continue
        claim = fact.get("claim")
        references = fact.get("resolution_refs", [])
        supporting_resolutions: list[Record] = []
        for reference in references:
            key = _parse_resolution_ref(reference)
            resolution = resolution_by_key.get(key) if key else None
            if reference not in actual_current or not resolution:
                report.add(
                    "overview.fact",
                    f"current_facts[{index}] cites non-current resolution {reference!r}",
                    overview.path,
                )
            else:
                supporting_resolutions.append(resolution)
        if supporting_resolutions and not any(
            claim in resolution.data.get("produced_facts", [])
            for resolution in supporting_resolutions
        ):
            report.add(
                "overview.fact",
                f"current_facts[{index}] claim is not produced by a cited resolution",
                overview.path,
            )


def _parse_resolution_ref(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, str):
        return None
    match = RESOLUTION_REF.fullmatch(value)
    return (match.group(1), match.group(2)) if match else None


def _safe_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts
