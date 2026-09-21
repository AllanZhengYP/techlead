from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tests.conformance_scenarios import copy_scenario
from tests.test_validator import render_scenario


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_ROOT = REPOSITORY_ROOT / "plugins" / "claude-techlead"
CODEX_ROOT = REPOSITORY_ROOT / "plugins" / "codex-techlead"


class PluginParityTests(unittest.TestCase):
    def test_both_provider_adapters_exist(self) -> None:
        self.assertTrue((CLAUDE_ROOT / ".claude-plugin" / "plugin.json").is_file())
        self.assertTrue((CODEX_ROOT / "plugin.json").is_file())
        self.assertTrue((CODEX_ROOT / ".codex-plugin" / "plugin.json").is_file())

    def test_packaged_shared_files_are_synchronized(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/sync_claude_plugin.py", "--check"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_marketplace_exposes_the_claude_plugin(self) -> None:
        marketplace = json.loads(
            (REPOSITORY_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(marketplace["name"], "techlead")
        self.assertEqual(marketplace["plugins"][0]["name"], "techlead")
        self.assertEqual(marketplace["plugins"][0]["source"], "./plugins/claude-techlead")

    def test_packaged_validators_run_without_source_tree_imports(self) -> None:
        for plugin_root in (CLAUDE_ROOT, CODEX_ROOT):
            with self.subTest(plugin=plugin_root.name), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                render_scenario(project, copy_scenario("exception-rollup"))
                result = subprocess.run(
                    [
                        sys.executable,
                        str(plugin_root / "bin" / "techlead-state"),
                        "validate",
                        str(project),
                        "--format",
                        "json",
                    ],
                    cwd=project,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["valid"])

    def test_packaged_helpers_produce_equivalent_canonical_state(self) -> None:
        projections = []
        for plugin_root in (CLAUDE_ROOT, CODEX_ROOT):
            with self.subTest(plugin=plugin_root.name), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                workspace = base / "workspace"
                workspace.mkdir()
                control = base / "control"
                registry_home = base / "state"
                executable = plugin_root / "bin" / "techlead-state"
                environment = {**os.environ, "TECHLEAD_STATE_HOME": str(registry_home)}
                revision_file = base / "revision.md"
                revision_file.write_text("# Signed baseline\n\nSelf-contained acceptance conditions.\n", encoding="utf-8")

                commands = [
                    [
                        "init", "--control-dir", str(control), "--name", "fixture-project",
                        "--title", "Fixture", "--root", "Fixture design",
                        "--workspace", str(workspace), "--workspace-id", "service-a",
                    ],
                    [
                        "apply-review", str(control / "fixture-project"), "--item", "WI-001",
                        "--decision", "signoff", "--revision-title", "Initial fixture design",
                        "--revision-file", str(revision_file),
                    ],
                    [
                        "create-work-item", str(control / "fixture-project"), "--parent", "WI-001",
                        "--title", "Implement fixture", "--work-type", "implementation",
                    ],
                    [
                        "apply-review", str(control / "fixture-project"), "--item", "WI-002",
                        "--decision", "signoff", "--revision-title", "Implementation contract",
                        "--revision-file", str(revision_file),
                    ],
                    [
                        "apply-review", str(control / "fixture-project"), "--item", "WI-002",
                        "--decision", "resolve", "--verdict", "External result accepted",
                    ],
                    [
                        "apply-review", str(control / "fixture-project"), "--item", "WI-001",
                        "--decision", "resolve", "--verdict", "All child work satisfies the parent",
                    ],
                ]
                for command in commands:
                    result = subprocess.run(
                        [sys.executable, str(executable), *command],
                        cwd=base,
                        env=environment,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                status = subprocess.run(
                    [sys.executable, str(executable), "status", str(control / "fixture-project")],
                    cwd=base,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(status.returncode, 0, status.stderr)
                payload = json.loads(status.stdout)
                projections.append([
                    {
                        key: item[key]
                        for key in (
                            "id", "title", "work_type", "state", "parent",
                            "active_revision", "review_required", "children",
                        )
                    }
                    for item in payload["work_items"]
                ])
        self.assertEqual(projections[0], projections[1])

    def test_release_archive_is_deterministic_and_installable_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.zip"
            second = Path(temporary) / "second.zip"
            release_marketplace = Path(temporary) / "marketplace.json"
            for output in (first, second):
                extra_args = []
                if output == first:
                    extra_args = [
                        "--release-marketplace-output",
                        str(release_marketplace),
                        "--archive-url",
                        "https://github.com/example/project/releases/latest/download/plugin.zip",
                    ]
                result = subprocess.run(
                    [
                        sys.executable,
                        "tools/package_claude_plugin.py",
                        "--output",
                        str(output),
                        *extra_args,
                    ],
                    cwd=REPOSITORY_ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = set(archive.namelist())
            self.assertIn("techlead/.claude-plugin/plugin.json", names)
            self.assertIn("techlead/skills/review-work/SKILL.md", names)
            self.assertIn("techlead/bin/techlead-state", names)
            self.assertNotIn("techlead/agents/worker.md", names)
            release = json.loads(release_marketplace.read_text(encoding="utf-8"))
            archive_source = release["plugins"][0]["source"]
            self.assertEqual(archive_source["source"], "archive")
            self.assertEqual(archive_source["sha256"], hashlib.sha256(first.read_bytes()).hexdigest())

    def test_codex_release_archive_is_deterministic_and_installable_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.zip"
            second = Path(temporary) / "second.zip"
            for output in (first, second):
                result = subprocess.run(
                    [sys.executable, "tools/package_codex_plugin.py", "--output", str(output)],
                    cwd=REPOSITORY_ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = set(archive.namelist())
            self.assertIn("codex-techlead/plugin.json", names)
            self.assertIn("codex-techlead/.codex-plugin/plugin.json", names)
            self.assertIn("codex-techlead/skills/review-work/SKILL.md", names)
            self.assertIn("codex-techlead/bin/techlead-state", names)

    def test_each_adapter_exposes_exactly_three_explicit_skills(self) -> None:
        expected = {"review-work", "create-work-item", "work-log"}
        for plugin_root in (CLAUDE_ROOT, CODEX_ROOT):
            with self.subTest(plugin=plugin_root.name):
                skills = {path.parent.name for path in (plugin_root / "skills").glob("*/SKILL.md")}
                self.assertEqual(skills, expected)
                self.assertFalse((plugin_root / "agents").exists())
                self.assertFalse((plugin_root / "hooks").exists())
                for skill in (plugin_root / "skills").glob("*/SKILL.md"):
                    self.assertNotIn("TODO", skill.read_text(encoding="utf-8"))

    def test_protocol_2_removes_old_record_families(self) -> None:
        schema_names = {path.name for path in (REPOSITORY_ROOT / "core" / "schemas").glob("*.json")}
        self.assertEqual(
            schema_names,
            {
                "manifest.json",
                "project.schema.json",
                "revision.schema.json",
                "session.schema.json",
                "work-item.schema.json",
                "workspace-locator.schema.json",
            },
        )
        for plugin_root in (CLAUDE_ROOT, CODEX_ROOT):
            self.assertFalse((plugin_root / "core" / "roles").exists())


if __name__ == "__main__":
    unittest.main()
