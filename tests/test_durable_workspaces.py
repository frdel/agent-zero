"""Managed project handoff preserves files while refusing unsafe custody."""
import asyncio
import base64
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from helpers.durable import workspaces
from helpers.durable.store import ConflictError, OwnershipError, StaleRunError


class MemoryResources:
    """Resource-manager boundary fake; encryption/SQL use the real test below."""
    def __init__(self):
        self.context_id, self.run_id = "context", "run"
        self.valid = True
        self.owner = SimpleNamespace(sync=self.assert_owner)
        self.data = {}
        self.manifest = None

    def assert_owner(self, method, run_id):
        if not self.valid:
            raise OwnershipError("Synthetic stale owner")

    def put_bytes(self, kind, name, data, sensitive=False):
        self.assert_owner("assert_owner", self.run_id)
        digest = hashlib.sha256(data).hexdigest()
        identity = hashlib.sha256((name + digest).encode()).hexdigest()
        self.data[identity] = data
        return {"id": identity, "kind": kind, "name": name, "digest": digest, "size": len(data)}

    def get_bytes(self, ref):
        return self.data[ref["id"]]

    def get_manifest(self, kind):
        return deepcopy(self.manifest)

    def publish_manifest(self, kind, value, expected_version):
        self.assert_owner("assert_owner", self.run_id)
        if (self.manifest["version"] if self.manifest else 0) != expected_version:
            raise ConflictError("Synthetic stale manifest")
        self.manifest = {"version": expected_version + 1, "value": deepcopy(value)}
        return self.get_manifest(kind)


class DurableWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.environment = patch.dict(os.environ, {"A0_DURABILITY_RESOURCE_KEY": base64.urlsafe_b64encode(b"k" * 32).decode()})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.manager = MemoryResources()

    def tree(self, name="project"):
        root = self.directory / name
        root.mkdir()
        return root

    def git(self, root, *args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()

    def test_git_dirty_untracked_deletions_and_executable_files_round_trip_without_owner_changes(self):
        root = self.tree()
        self.git(root, "init")
        self.git(root, "config", "user.email", "synthetic@example.invalid")
        self.git(root, "config", "user.name", "Synthetic")
        (root / "main.py").write_text("before\n")
        (root / "removed.txt").write_text("removed\n")
        (root / ".gitignore").write_text("ignored.txt\n")
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", "Synthetic base")
        revision = self.git(root, "rev-parse", "HEAD")
        (root / "main.py").write_text("after\n")
        (root / "removed.txt").unlink()
        (root / "run.sh").write_text("#!/bin/sh\nprintf synthetic\n")
        (root / "run.sh").chmod(0o700)
        (root / "ignored.txt").write_text("required ignored working input\n")
        (root / "empty-directory").mkdir()
        (root / "node_modules").mkdir()
        (root / "node_modules" / "ignored.js").write_text("dependency cache")
        manifest = workspaces.capture(self.manager, root)
        self.assertIsNone(self.manager.manifest, "Capture must not secretly publish a manifest")
        self.assertEqual(manifest["revision"], revision)
        self.assertIn("main.py", manifest["dirty"])
        self.assertIn("removed.txt", manifest["deleted"])
        self.assertIn("run.sh", manifest["untracked"])
        self.assertEqual(manifest["digest"], workspaces.capture(self.manager, root)["digest"])
        self.assertIn(".git", manifest["excluded"])
        self.assertIn("node_modules", manifest["excluded"])
        restored = workspaces.restore(self.manager, manifest, self.directory / "restored")
        self.assertEqual((restored / "main.py").read_text(), "after\n")
        self.assertEqual((restored / "ignored.txt").read_text(), "required ignored working input\n")
        self.assertFalse((restored / "removed.txt").exists())
        self.assertFalse((restored / ".git").exists())
        self.assertTrue(os.access(restored / "run.sh", os.X_OK))
        self.assertTrue((restored / "empty-directory").is_dir())
        with self.assertRaises(workspaces.WorkspaceHeld):
            workspaces.restore(self.manager, manifest, root)
        self.assertEqual((root / "main.py").read_text(), "after\n")
        with workspaces.project_override(root.name, restored, manifest=manifest):
            recaptured = workspaces.capture(self.manager, restored)
        self.assertEqual(recaptured["revision"], revision)
        self.assertEqual(recaptured["project_name"], root.name)
        self.assertEqual(recaptured["digest"], manifest["digest"])

    def test_symlinks_hardlinks_special_files_and_real_credentials_hold_without_publication(self):
        for kind in ("symlink", "hardlink", "fifo", "environment", "private_key", "ignored_environment"):
            with self.subTest(kind=kind):
                root = self.tree(kind)
                if kind == "symlink":
                    (root / "escape").symlink_to(self.directory)
                elif kind == "hardlink":
                    (root / "original").write_text("synthetic")
                    os.link(root / "original", root / "linked")
                elif kind == "fifo":
                    os.mkfifo(root / "fifo")
                elif kind == "private_key":
                    (root / "plain.txt").write_text("-----BEGIN PRIVATE KEY-----\nsynthetic\n")
                else:
                    if kind == "ignored_environment":
                        self.git(root, "init")
                        (root / ".gitignore").write_text(".env\n")
                    (root / ".env").write_text("PRIVATE_VALUE=synthetic-value\n")
                with self.assertRaises(workspaces.WorkspaceHeld):
                    workspaces.capture(self.manager, root)
                self.assertEqual(self.manager.data, {})

    def test_restore_refuses_traversal_corruption_and_stale_claim_before_creating_paths(self):
        root = self.tree()
        (root / "safe.txt").write_text("safe")
        manifest = workspaces.capture(self.manager, root)
        malformed = deepcopy(manifest)
        malformed["files"][0]["path"] = "../escape"
        with self.assertRaises(workspaces.WorkspaceHeld):
            workspaces.restore(self.manager, malformed, self.directory / "malformed")
        self.manager.data[manifest["files"][0]["ref"]["id"]] = b"corrupt"
        with self.assertRaises(workspaces.WorkspaceHeld):
            workspaces.restore(self.manager, manifest, self.directory / "corrupt")
        self.manager.valid = False
        with self.assertRaises(OwnershipError):
            workspaces.restore(self.manager, manifest, self.directory / "stale")
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), [root.name])

    def test_capture_bounds_and_concurrent_change_hold_without_manifest_publication(self):
        root = self.tree()
        (root / "file").write_bytes(b"too large")
        with patch.dict(os.environ, {"A0_DURABILITY_RESOURCE_KEY": ""}), self.assertRaises(workspaces.WorkspaceHeld):
            workspaces.capture(self.manager, root)
        with patch.object(workspaces, "MAX_FILE_BYTES", 3), self.assertRaises(workspaces.WorkspaceHeld):
            workspaces.capture(self.manager, root)
        inventory = workspaces._inventory
        calls = 0
        def mutate_before_verification(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                (root / "file").write_bytes(b"changed during capture")
            return inventory(path)
        with patch.object(workspaces, "_inventory", side_effect=mutate_before_verification), self.assertRaises(workspaces.WorkspaceHeld):
            workspaces.capture(self.manager, root)
        self.assertIsNone(self.manager.manifest)
        self.assertEqual(self.manager.data, {})

    def test_context_local_lookup_and_manifest_cas_do_not_leak_between_workers(self):
        from helpers import projects
        roots = [self.tree("project-a"), self.tree("project-b")]
        for index, root in enumerate(roots):
            (root / "value").write_text(str(index))
        manifests = [workspaces.capture(self.manager, root) for root in roots]
        self.manager.publish_manifest("workspace", manifests[0], 0)
        with self.assertRaises(ConflictError):
            self.manager.publish_manifest("workspace", manifests[1], 0)
        async def check():
            ready = asyncio.Event()
            count = 0
            async def worker(root):
                nonlocal count
                with workspaces.project_override("same-project", root):
                    count += 1
                    if count == 2:
                        ready.set()
                    await ready.wait()
                    await asyncio.sleep(0)
                    self.assertEqual(Path(projects.get_project_folder("same-project")), root)
                    self.assertNotEqual(Path(projects.get_project_folder("other-project")), root)
            await asyncio.gather(*(worker(root) for root in roots))
        asyncio.run(check())
        self.assertIsNone(workspaces.project_folder("same-project"))


@unittest.skipUnless(os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN"), "Disposable PostgreSQL test DSN is required")
class EncryptedWorkspaceIntegrationTests(unittest.TestCase):
    def test_real_encrypted_resource_custody_cas_and_reset_fencing(self):
        import psycopg
        from psycopg import sql
        from cryptography.fernet import Fernet
        from helpers.durable.postgres import PostgresStore
        from helpers.durable.resources import ResourceManager
        dsn = os.environ["A0_TEST_DURABILITY_POSTGRES_DSN"]
        namespace = "a0_workspace_" + uuid.uuid4().hex
        store = PostgresStore(dsn, namespace=namespace)
        owner = SimpleNamespace(sync=lambda method, *args, **kwargs: getattr(store, method)(*args, **kwargs))
        try:
            run = store.admit("context", "input", {}, {})
            store.claim(run["run_id"])
            manager = ResourceManager(owner, "context", run["run_id"])
            with patch.dict(os.environ, {"A0_DURABILITY_RESOURCE_KEY": Fernet.generate_key().decode()}), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve() / "owner-project"
                root.mkdir()
                (root / "source.py").write_text("synthetic private workspace content")
                manifest = workspaces.capture(manager, root)
                body = bytes(store._connection.execute("SELECT body FROM resource_objects").fetchone()[0])
                self.assertNotIn(b"synthetic private workspace content", body)
                manager.publish_manifest("workspace", manifest, 0)
                with self.assertRaises(ConflictError):
                    manager.publish_manifest("workspace", manifest, 0)
                restored = workspaces.restore(manager, manifest, root.parent / "worker")
                self.assertEqual((restored / "source.py").read_bytes(), (root / "source.py").read_bytes())
                store.control("context", "reset")
                with self.assertRaises((OwnershipError, StaleRunError)):
                    manager.publish_manifest("workspace", manifest, 1)
        finally:
            store.close()
            with psycopg.connect(dsn, autocommit=True) as cleanup:
                cleanup.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))


if __name__ == "__main__":
    unittest.main()


# Reuse the existing real-service fixture rather than building another worker
# harness. The standalone unittest cases above also run without pytest fixtures.
from test_durable_cluster import nodes
from test_durable_runtime import rig


def test_claimed_cluster_worker_commits_workspace_edits_without_touching_owner_checkout(nodes, monkeypatch, tmp_path):
    from cryptography.fernet import Fernet
    from agent import UserMessage
    from helpers import projects
    from helpers.durable import codec, resources
    from helpers.durable.cluster import RunHandle
    from helpers.tool import Response
    from tools.response import ResponseTool
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(projects, "PROJECTS_PARENT_DIR", str(tmp_path / "projects"))
    project = "portable-project"
    original = Path(projects.get_project_folder(project))
    original.mkdir(parents=True)
    (original / "value.txt").write_text("owner checkout")
    context = nodes.rig.context
    context.set_data("project", project)
    resources.capture_context(nodes.first, context)
    message = UserMessage("Edit managed project", id="workspace-input")
    run = nodes.first.sync("admit", context.id, message.id, codec.message_payload(message), codec.checkpoint(context.agent0))
    paths = []
    async def edit_managed(self, **kwargs):
        path = Path(projects.get_project_folder(project))
        assert path != original
        paths.append(path)
        (path / "value.txt").write_text("committed worker edit")
        if len(paths) > 1:
            (path / ".env").write_text("API_KEY=private-test-key-that-cannot-travel")
        return Response(message="Done", break_loop=True)
    monkeypatch.setattr(ResponseTool, "execute", edit_managed)
    nodes.second.scan()
    assert RunHandle(nodes.second, run["run_id"]).result_sync(timeout=10) == "Done"
    completed = nodes.first.sync("get_run", run["run_id"])
    manifest = completed["checkpoint"]["resources"]["workspace"]
    row = next(row for row in manifest["files"] if row["path"] == "value.txt")
    manager = resources.ResourceManager(nodes.first, context.id)
    assert manager.get_bytes(row["ref"]) == b"committed worker edit"
    assert paths and (original / "value.txt").read_text() == "owner checkout"
    # A completed body remains known when its changed files cannot safely travel.
    for node in (nodes.first, nodes.second):
        local = node.contexts.get(run["run_id"])
        if local and local.task:
            local.task.result_sync(timeout=10)
    held = nodes.second.communicate_remote(context.id, UserMessage("Create unsafe state", id="workspace-unsafe"))
    held.result_sync(timeout=10)
    held_run = nodes.first.sync("get_run", held.run_id)
    assert held_run["status"] == "attention"
    body = nodes.first.sync("get_call", held.run_id, "tool:0:0")
    assert body["status"] == "completed" and body["result"]["response"]["message"] == "Done"
    nodes.second.scan()
    assert len(paths) == 2 and (original / "value.txt").read_text() == "owner checkout"
