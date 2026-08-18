from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import hashlib

from tests.conformance_scenarios import copy_scenario
from tests.test_validator import render_scenario


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "claude-techlead"


class ClaudePluginTests(unittest.TestCase):
    def test_claude_is_the_only_provider_adapter(self) -> None:
        self.assertTrue((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").is_file())
        self.assertFalse((REPOSITORY_ROOT / "plugins" / "codex-techlead").exists())

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

    def test_packaged_validator_runs_without_source_tree_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            render_scenario(project, copy_scenario("pivot-reconciliation"))
            result = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_ROOT / "bin" / "techlead-state"),
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
            self.assertIn("techlead/skills/lead-project/SKILL.md", names)
            self.assertIn("techlead/bin/techlead-state", names)
            release = json.loads(release_marketplace.read_text(encoding="utf-8"))
            archive_source = release["plugins"][0]["source"]
            self.assertEqual(archive_source["source"], "archive")
            self.assertEqual(archive_source["sha256"], hashlib.sha256(first.read_bytes()).hexdigest())

    def test_skills_have_no_scaffold_placeholders(self) -> None:
        skills = sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(skills), 4)
        for skill in skills:
            with self.subTest(skill=skill.parent.name):
                self.assertNotIn("TODO", skill.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
