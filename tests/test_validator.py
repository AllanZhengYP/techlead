from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.conformance_scenarios import SCENARIOS, copy_scenario
from tools.techlead_state.validator import validate_project


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def render_scenario(root: Path, records: list[tuple[str, dict[str, object], str]]) -> None:
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

    def test_missing_graph_backlink_is_rejected(self) -> None:
        records = copy_scenario("expansion")
        child = next(metadata for path, metadata, _body in records if path.endswith("WI-110/WORK.md"))
        child["parents"] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("graph.backlink", codes)

    def test_incomplete_verification_coverage_is_rejected(self) -> None:
        records = copy_scenario("resolution-release")
        resolution = next(metadata for path, metadata, _body in records if path.endswith("resolutions/r1.md"))
        resolution["verification_ids"] = ["EV-111"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("resolution.coverage", codes)

    def test_invalidated_resolution_cannot_remain_current(self) -> None:
        records = copy_scenario("pivot-reconciliation")
        overview = next(metadata for path, metadata, _body in records if path.endswith("OVERVIEW.md"))
        overview["current_resolutions"].append("WI-130@r1")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("overview.current", codes)

    def test_current_fact_must_be_produced_by_cited_resolution(self) -> None:
        records = copy_scenario("resolution-release")
        overview = next(metadata for path, metadata, _body in records if path.endswith("OVERVIEW.md"))
        overview["current_facts"][0]["claim"] = "Unsupported claim"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("overview.fact", codes)

    def test_risk_graph_references_must_exist(self) -> None:
        records = copy_scenario("expansion")
        risk_register = next(metadata for path, metadata, _body in records if path.endswith("RISKS.md"))
        risk_register["risks"][0]["mitigation_items"] = ["WI-999"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            messages = [issue.message for issue in validate_project(root).issues]
        self.assertTrue(any("mitigation_items references missing WI-999" in message for message in messages))

    def test_decision_and_resolution_require_backlinks(self) -> None:
        records = copy_scenario("resolution-release")
        resolution = next(metadata for path, metadata, _body in records if path.endswith("resolutions/r1.md"))
        resolution["decision_ids"] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, records)
            codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("reference.mismatch", codes)

    def test_cli_emits_machine_readable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            render_scenario(root, copy_scenario("resolution-release"))
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
        self.assertEqual(payload["work_items_checked"], 2)


if __name__ == "__main__":
    unittest.main()
