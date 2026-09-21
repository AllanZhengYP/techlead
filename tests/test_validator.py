from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.conformance_scenarios import SCENARIOS, copy_scenario
from tools.techlead_state.validator import validate_context_links, validate_project


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def render_scenario(root: Path, records: list[tuple[str, dict[str, object], str]]) -> None:
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    (root / "local").mkdir(exist_ok=True)
    (root / "workspace-links").mkdir(exist_ok=True)
    for relative, metadata, body in records:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["---"]
        for key, value in metadata.items():
            lines.append(f"{key}: {json.dumps(value, separators=(',', ':'))}")
        lines.extend(["---", body])
        path.write_text("\n".join(lines), encoding="utf-8")


class ValidatorConformanceTests(unittest.TestCase):
    def validate_fixture(self, name: str):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        render_scenario(root, copy_scenario(name))
        return root, validate_project(root)

    def test_all_conformance_snapshots_are_valid(self) -> None:
        for name in SCENARIOS:
            with self.subTest(name=name):
                _root, report = self.validate_fixture(name)
                self.assertTrue(report.valid, report.issues)

    def test_exact_work_item_schema_rejects_old_graph_fields(self) -> None:
        records = copy_scenario("initialization")
        root_work = next(metadata for path, metadata, _body in records if path.endswith("WORK.md"))
        root_work["dependencies"] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            issues = validate_project(root).issues
        self.assertTrue(any(issue.code == "schema.invalid" and "dependencies" in issue.message for issue in issues))

    def test_non_root_parent_must_exist(self) -> None:
        records = copy_scenario("signed-decomposition")
        child = next(metadata for path, metadata, _body in records if "WI-002-" in path and path.endswith("WORK.md"))
        child["parent"] = "WI-999"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("tree.parent", codes)

    def test_in_design_cannot_have_active_revision(self) -> None:
        records = copy_scenario("initialization")
        root_work = next(metadata for path, metadata, _body in records if path.endswith("WORK.md"))
        root_work["active_revision"] = "r1"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("state.active_revision", codes)

    def test_resolved_parent_requires_resolved_children(self) -> None:
        records = copy_scenario("signed-decomposition")
        parent = next(metadata for path, metadata, _body in records if "WI-001-" in path and path.endswith("WORK.md"))
        parent["state"] = "resolved"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("state.resolved_children", codes)

    def test_revision_chain_must_be_contiguous(self) -> None:
        records = copy_scenario("signed-decomposition")
        records.append(
            (
                "work-items/WI-001-fixture-design/revisions/r3-skipped.md",
                {"revision": "r3", "title": "Skipped", "supersedes": "r2"},
                "# Skipped\n",
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("revision.sequence", codes)

    def test_broken_local_link_and_anchor_are_rejected(self) -> None:
        records = copy_scenario("initialization")
        path, metadata, _body = records[1]
        records[1] = (path, metadata, "[Missing](missing.md)\n[Heading](WORK.md#not-there)\n")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("link.missing", codes)
        self.assertIn("link.anchor", codes)

    def test_session_must_reference_declared_workspace(self) -> None:
        records = copy_scenario("session-continuity")
        session = next(metadata for path, metadata, _body in records if path.startswith("sessions/"))
        session["workspace_id"] = "unknown"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("session.workspace", codes)

    def test_bounded_review_context_validates_nested_links_and_reports_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            root.mkdir()
            render_scenario(root, copy_scenario("initialization"))
            workspace = base / "workspace"
            workspace.mkdir()
            (workspace / "support.md").write_text("# Details\n", encoding="utf-8")
            design = workspace / "design.md"
            design.write_text(
                "[Support](support.md#details)\n[External](https://example.com/source)\n",
                encoding="utf-8",
            )
            (root / "workspace-links").rmdir()
            (root / "workspace-links").mkdir()
            (root / "workspace-links" / "service-a").symlink_to(workspace, target_is_directory=True)

            report, urls = validate_context_links(root, [design])
            self.assertTrue(report.valid, report.issues)
            self.assertEqual(urls, ["https://example.com/source"])

            (workspace / "support.md").write_text("# Different\n", encoding="utf-8")
            report, _urls = validate_context_links(root, [design])
            self.assertIn("link.anchor", {issue.code for issue in report.issues})

    def test_legacy_protocol_returns_explicit_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CHARTER.md").write_text("---\nprotocol_version: \"1.0\"\n---\n", encoding="utf-8")
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("protocol.legacy", codes)

    def test_cli_emits_machine_readable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, copy_scenario("session-continuity"))
            result = subprocess.run(
                [sys.executable, str(REPOSITORY_ROOT / "tools/techlead-state"), "validate", str(root), "--format", "json"],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["protocol_version"], "2.0")
        self.assertEqual(payload["work_items_checked"], 3)


if __name__ == "__main__":
    unittest.main()
