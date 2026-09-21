from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.techlead_state.frontmatter import parse_file
from tools.techlead_state.operations import (
    OperationError,
    apply_review,
    attach_workspace,
    close_session,
    create_work_item,
    initialize_project,
    next_actions,
    project_status,
    register_session,
)
from tools.techlead_state.resolver import ResolutionError, read_locator, resolve_project
from tools.techlead_state.validator import validate_project


class ProtocolOperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.control = self.base / "control"
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        self.registry = self.base / "state" / "projects.json"

    def initialize(self, *, name: str = "demo-project", title: str = "Demo") -> Path:
        result = initialize_project(
            self.control,
            name=name,
            title=title,
            root_title=f"{title} design",
            workspace=self.workspace,
            workspace_id="service-a",
            registry_path=self.registry,
        )
        return Path(result["project_root"])

    def signoff(self, root: Path, item_id: str, title: str = "Initial signed baseline") -> None:
        apply_review(
            root,
            item_id=item_id,
            decision="signoff",
            revision_title=title,
            revision_body="# Signed baseline\n\nResolution conditions are explicit.\n",
            registry_path=self.registry,
        )

    def test_multi_project_control_root_and_ambiguous_locator(self) -> None:
        first = self.initialize(name="first-project", title="First")
        first_id = parse_file(first / "PROJECT.md").metadata["project_id"]
        second = self.initialize(name="second-project", title="Second")
        second_id = parse_file(second / "PROJECT.md").metadata["project_id"]

        self.assertTrue(validate_project(first).valid)
        self.assertTrue(validate_project(second).valid)
        locator = read_locator(self.workspace / ".techlead-project")
        self.assertEqual(set(locator["project_ids"]), {first_id, second_id})
        self.assertEqual(resolve_project(self.workspace, registry_path=self.registry).project_id, second_id)

        (self.workspace / ".techlead").unlink()
        with self.assertRaisesRegex(ResolutionError, "multiple projects"):
            resolve_project(self.workspace, registry_path=self.registry)
        selected = resolve_project(
            self.workspace,
            project_id=first_id,
            registry_path=self.registry,
        )
        self.assertEqual(selected.project_root, first)

    def test_one_project_spans_workspaces_and_worktrees_select_projects_independently(self) -> None:
        first = self.initialize(name="first-project", title="First")
        second_workspace = self.base / "web-workspace"
        second_workspace.mkdir()
        attach_workspace(
            first,
            second_workspace,
            workspace_id="web-client",
            registry_path=self.registry,
        )
        clone = self.base / "service-clone"
        clone.mkdir()
        attach_workspace(
            first,
            clone,
            workspace_id="service-a",
            registry_path=self.registry,
        )
        project = parse_file(first / "PROJECT.md").metadata
        self.assertEqual(set(project["workspace_ids"]), {"service-a", "web-client"})
        self.assertEqual((clone / ".techlead").resolve(), first)
        mappings = list((first / "local" / "workspaces" / "service-a").glob("*.yaml"))
        self.assertEqual(len(mappings), 2)

        second = self.initialize(name="second-project", title="Second")
        self.assertEqual((self.workspace / ".techlead").resolve(), second)
        self.assertEqual((clone / ".techlead").resolve(), first)

    def test_child_creation_is_unsigned_and_resolved_parent_is_terminal(self) -> None:
        root = self.initialize()
        child = create_work_item(
            root,
            parent="WI-001",
            title="Implement session auth",
            work_type="implementation",
            registry_path=self.registry,
        )
        child_doc = parse_file(Path(child["directory"]) / "WORK.md")
        self.assertEqual(child_doc.metadata["state"], "in-design")
        self.assertIsNone(child_doc.metadata["active_revision"])
        self.assertIn("Parent context", child_doc.body)

        self.signoff(root, "WI-001")
        self.signoff(root, "WI-002", "Implementation contract")
        with self.assertRaisesRegex(OperationError, "children remain unresolved"):
            apply_review(
                root,
                item_id="WI-001",
                decision="resolve",
                verdict="Premature parent result.",
                registry_path=self.registry,
            )
        apply_review(root, item_id="WI-002", decision="resolve", verdict="Implementation completed.", registry_path=self.registry)
        apply_review(root, item_id="WI-001", decision="resolve", verdict="All child work is complete.", registry_path=self.registry)
        with self.assertRaisesRegex(OperationError, "resolved parent"):
            create_work_item(
                root,
                parent="WI-001",
                title="Late work",
                work_type="design",
                registry_path=self.registry,
            )

    def test_next_returns_action_work_item_pairs_without_running_work(self) -> None:
        root = self.initialize()
        initial = next_actions(root)
        self.assertEqual(initial[0]["action"], "continue-design-or-review")
        self.assertEqual(initial[0]["work_item"], "WI-001")

        self.signoff(root, "WI-001")
        create_work_item(
            root,
            parent="WI-001",
            title="Child design",
            work_type="design",
        )
        actions = {entry["work_item"]: entry for entry in next_actions(root)}
        self.assertEqual(actions["WI-001"]["action"], "await-children")
        self.assertEqual(actions["WI-002"]["action"], "continue-design-or-review")
        self.assertIn("parallel_note", actions["WI-002"])

    def test_revision_created_only_for_changed_semantic_baseline(self) -> None:
        root = self.initialize()
        with self.assertRaisesRegex(OperationError, "self-contained revision body"):
            apply_review(root, item_id="WI-001", decision="signoff")
        self.signoff(root, "WI-001")
        item_dir = next((root / "work-items").glob("WI-001-*"))
        work_path = item_dir / "WORK.md"
        document = parse_file(work_path)
        work_path.write_text(
            work_path.read_text(encoding="utf-8").replace("# WI-001", "# Clearer WI-001"),
            encoding="utf-8",
        )
        self.assertTrue(validate_project(root).valid)
        apply_review(root, item_id="WI-001", decision="reaffirm", registry_path=self.registry)
        self.assertEqual(len(list((item_dir / "revisions").glob("*.md"))), 1)

        result = apply_review(
            root,
            item_id="WI-001",
            decision="revise",
            revision_title="Changed authentication boundary",
            revision_body="# Changed baseline\n",
            registry_path=self.registry,
        )
        self.assertEqual(result["new_revision"], "r2")
        self.assertEqual(parse_file(work_path).metadata["active_revision"], "r2")

        apply_review(root, item_id="WI-001", decision="return-to-design", registry_path=self.registry)
        reopened = parse_file(work_path).metadata
        self.assertEqual(reopened["state"], "in-design")
        self.assertIsNone(reopened["active_revision"])
        apply_review(
            root,
            item_id="WI-001",
            decision="signoff",
            revision_title="Replacement signed baseline",
            revision_body="# Replacement baseline\n",
            registry_path=self.registry,
        )
        self.assertEqual(parse_file(work_path).metadata["active_revision"], "r3")
        apply_review(root, item_id="WI-001", decision="resolve", verdict="The replacement baseline is satisfied.", registry_path=self.registry)
        with self.assertRaisesRegex(OperationError, "terminal"):
            apply_review(root, item_id="WI-001", decision="return-to-design", registry_path=self.registry)

    def test_early_exception_and_all_children_completion_roll_up_separately(self) -> None:
        root = self.initialize()
        self.signoff(root, "WI-001")
        for title in ("Explore storage", "Implement service"):
            create_work_item(
                root,
                parent="WI-001",
                title=title,
                work_type="exploration" if title.startswith("Explore") else "implementation",
                registry_path=self.registry,
            )
        self.signoff(root, "WI-002", "Storage exploration")
        self.signoff(root, "WI-003", "Service implementation")

        apply_review(
            root,
            item_id="WI-002",
            decision="resolve",
            verdict="The storage assumption is false.",
            material_challenge=True,
            registry_path=self.registry,
        )
        status = project_status(root, registry_path=self.registry)
        by_id = {item["id"]: item for item in status["work_items"]}
        self.assertTrue(by_id["WI-001"]["review_required"])
        self.assertEqual(by_id["WI-003"]["state"], "in-working")

        apply_review(root, item_id="WI-001", decision="reaffirm", registry_path=self.registry)
        apply_review(root, item_id="WI-003", decision="resolve", verdict="Service implementation completed.", registry_path=self.registry)
        status = project_status(root, registry_path=self.registry)
        by_id = {item["id"]: item for item in status["work_items"]}
        self.assertTrue(by_id["WI-001"]["review_required"])
        apply_review(root, item_id="WI-001", decision="resolve", verdict="All child verdicts satisfy the parent.", registry_path=self.registry)
        self.assertEqual(project_status(root)["work_items"][0]["state"], "resolved")

    def test_review_can_atomically_create_explicitly_approved_children(self) -> None:
        root = self.initialize()
        self.signoff(root, "WI-001")
        result = apply_review(
            root,
            item_id="WI-001",
            decision="revise",
            revision_title="Add rollout validation",
            revision_body="# Revised baseline\n\nRollout validation is required.\n",
            children=[
                {
                    "title": "Verify rollout",
                    "work_type": "verification",
                    "body": "# Verify rollout\n\n[Parent](../WI-001-demo-design/WORK.md)\n",
                }
            ],
            registry_path=self.registry,
        )
        self.assertEqual(result["created_children"], ["WI-002"])
        status = project_status(root)
        child = next(item for item in status["work_items"] if item["id"] == "WI-002")
        self.assertEqual(child["state"], "in-design")

    def test_session_role_is_stable_and_closed_id_is_not_reused(self) -> None:
        root = self.initialize()
        create_work_item(root, parent="WI-001", title="Implementation", work_type="implementation")
        first = register_session(
            root,
            provider="codex",
            provider_session_id="opaque-1",
            role="implementation",
            work_items=["WI-001", "WI-002"],
            workspace=self.workspace,
            registry_path=self.registry,
        )
        self.assertEqual(first["session"], "SES-001")
        with self.assertRaisesRegex(OperationError, "already registered as implementation"):
            register_session(
                root,
                provider="codex",
                provider_session_id="opaque-1",
                role="techlead-review",
                work_items=["WI-001"],
                workspace=self.workspace,
                registry_path=self.registry,
            )
        close_session(root, session_id="SES-001", registry_path=self.registry)
        root_body = parse_file(next((root / "work-items").glob("WI-001-*/WORK.md"))).body
        self.assertIn("provider_session_id=opaque-1", root_body)

        second = register_session(
            root,
            provider="claude-code",
            provider_session_id="opaque-2",
            role="design",
            work_items=["WI-001"],
            workspace=self.workspace,
            registry_path=self.registry,
        )
        self.assertEqual(second["session"], "SES-002")

    def test_writer_lock_blocks_competing_mutation(self) -> None:
        root = self.initialize()
        lock = root / "local" / "write.lock"
        lock.mkdir()
        with self.assertRaisesRegex(OperationError, "writer lock"):
            create_work_item(root, parent="WI-001", title="Blocked", work_type="design")

    def test_concurrent_id_allocation_cannot_collide(self) -> None:
        root = self.initialize()

        def create(number: int):
            try:
                return create_work_item(
                    root,
                    parent="WI-001",
                    title=f"Parallel child {number}",
                    work_type="implementation",
                )
            except OperationError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            attempted = list(executor.map(create, (1, 2)))
        results = [result for result in attempted if isinstance(result, dict)]
        conflicts = [result for result in attempted if isinstance(result, OperationError)]
        self.assertTrue(all("writer lock" in str(conflict) for conflict in conflicts))
        for number, _conflict in enumerate(conflicts, start=10):
            results.append(create_work_item(
                root,
                parent="WI-001",
                title=f"Retried parallel child {number}",
                work_type="implementation",
            ))
        self.assertEqual({result["id"] for result in results}, {"WI-002", "WI-003"})
        self.assertTrue(validate_project(root).valid)

    def test_failed_overlay_validation_rolls_back_every_file(self) -> None:
        root = self.initialize()
        self.signoff(root, "WI-001")
        item_dir = next((root / "work-items").glob("WI-001-*"))
        original_work = (item_dir / "WORK.md").read_bytes()
        with self.assertRaisesRegex(OperationError, "invalid project state"):
            apply_review(
                root,
                item_id="WI-001",
                decision="revise",
                revision_title="Broken linked baseline",
                revision_body="# Revised\n",
                children=[
                    {
                        "title": "Broken child",
                        "work_type": "design",
                        "body": "[Required source](missing.md)\n",
                    }
                ],
            )
        self.assertEqual((item_dir / "WORK.md").read_bytes(), original_work)
        self.assertEqual(len(list((item_dir / "revisions").glob("*.md"))), 1)
        self.assertFalse(any((root / "work-items").glob("WI-002-*")))

    def test_git_is_optional_and_local_selection_is_never_staged(self) -> None:
        workspace = self.base / "git-workspace"
        workspace.mkdir()
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
        result = initialize_project(
            self.control,
            name="git-project",
            title="Git project",
            root_title="Git design",
            workspace=workspace,
            workspace_id="git-service",
            registry_path=self.registry,
        )
        root = Path(result["project_root"])
        staged = subprocess.run(
            ["git", "-C", str(workspace), "diff", "--cached", "--quiet"],
            check=False,
        )
        self.assertEqual(staged.returncode, 0)
        ignored = subprocess.run(
            ["git", "-C", str(workspace), "check-ignore", ".techlead"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(ignored.returncode, 0)
        self.assertEqual(ignored.stdout.strip(), ".techlead")
        self.assertTrue(validate_project(root).valid)

        subprocess.run(["git", "-C", str(workspace), "add", "-f", ".techlead"], check=True)
        codes = {issue.code for issue in validate_project(root).issues}
        self.assertIn("git.selection_tracked", codes)


if __name__ == "__main__":
    unittest.main()
