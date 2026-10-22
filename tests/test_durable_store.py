"""Local storage guarantees, including actual process death at commit boundaries."""

import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from helpers.durable.store import (
    ConflictError,
    DurableStoreError,
    IntegrityError,
    LocalStore,
    OwnershipError,
    StaleRunError,
)


class DurableStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        # macOS /var and /tmp aliases are deliberately not recovery paths.
        self.directory = Path(self.temporary.name).resolve()
        self.root = self.directory / "recovery"
        self.addCleanup(self.temporary.cleanup)

    def store(self):
        store = LocalStore(self.root)
        self.addCleanup(store.close)
        return store

    def admit(self, store, input_id="input-1"):
        return store.admit("context-1", input_id, {"text": "synthetic input"}, {"schema": 1, "history": []})

    def child(self, body):
        code = "\n".join([
            "import json, os, sys, time",
            "from pathlib import Path",
            "from helpers.durable.store import LocalStore, OwnershipError",
            "root = Path(sys.argv[1])",
            body,
        ])
        process = subprocess.Popen([sys.executable, "-u", "-c", code, str(self.root)], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: self.stop_child(process))
        return process

    @staticmethod
    def stop_child(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)

    def barrier(self, process):
        # communicate() cannot be used while parked at the intentional crash barrier.
        import selectors
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(10), "Child never reached the commit barrier")
        value = process.stdout.readline().strip()
        self.assertTrue(value, process.stderr.read() if process.poll() is not None else "Empty barrier")
        return value

    def kill(self, process):
        if os.name == "posix":
            os.kill(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=10)

    def test_admission_is_idempotent_and_genesis_survives_reopen(self):
        store = self.store()
        run = self.admit(store)
        self.assertEqual(run["phase"], "admitted")
        self.assertEqual(run["checkpoint"]["schema"], 1)
        self.assertEqual(self.admit(store)["run_id"], run["run_id"])
        self.assertEqual(len(store.read_events(run["run_id"])), 1)
        with self.assertRaises(ConflictError):
            store.admit("context-1", "input-1", {"text": "different"}, {})
        with self.assertRaises(ConflictError):
            self.admit(store, "input-2")
        store.close()
        with LocalStore(self.root) as reopened:
            self.assertEqual(reopened.get_run(run["run_id"]), run)

    def test_atomic_rollback_leaves_no_input_or_orphan_context(self):
        store = self.store()
        with patch.object(store, "_event", side_effect=sqlite3.OperationalError("synthetic storage failure")):
            with self.assertRaises(DurableStoreError):
                self.admit(store)
        self.assertEqual(store.list_runs(), [])
        self.assertEqual(store._connection.execute("SELECT COUNT(*) FROM contexts").fetchone()[0], 0)
        self.assertEqual(self.admit(store)["generation"], 0)

    def test_checkpoint_and_event_update_are_one_transaction(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        run = store.transition(run_id, "process_model_result", {"schema": 1, "cursor": 2}, payload={"step": 2})
        events = store.read_events(run_id)
        self.assertEqual(run["checkpoint_seq"], events[-1]["seq"])
        self.assertEqual(store.read_events(run_id, after=events[0]["seq"]), events[1:])
        self.assertEqual(run["checkpoint"]["cursor"], 2)
        store.transition(run_id, "complete", status="completed")
        self.assertEqual(store.list_runs(statuses=("running",)), [])
        self.assertEqual(len(store.list_runs(statuses=("completed",))), 1)
        self.assertNotEqual(self.admit(store, "input-2")["run_id"], run_id)

    def test_call_intent_and_result_are_idempotent_and_checked(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        intent = store.start_call(run_id, "call-1", "tool", {"arg": "value"})
        self.assertEqual(intent["status"], "intent")
        self.assertEqual(store.start_call(run_id, "call-1", "tool", {"arg": "value"}), intent)
        with self.assertRaises(ConflictError):
            store.start_call(run_id, "call-1", "tool", {"arg": "changed"})
        outcome = store.finish_call(run_id, "call-1", {"message": "done", "break_loop": True})
        self.assertEqual(store.finish_call(run_id, "call-1", outcome["result"]), outcome)
        with self.assertRaises(ConflictError):
            store.finish_call(run_id, "call-1", {"message": "different"})
        self.assertEqual(len(store.calls(run_id)), 1)
        self.assertEqual([event["kind"] for event in store.read_events(run_id)], ["admitted", "call_intent", "call_result"])

    def test_cancel_stops_new_work_but_keeps_racing_outcome(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        store.start_call(run_id, "call-1", "tool", {})
        store.control("context-1")
        self.assertEqual(store.get_run(run_id)["status"], "cancelled")
        self.assertEqual(store.finish_call(run_id, "call-1", {"late": True})["status"], "completed")
        with self.assertRaises(StaleRunError):
            store.start_call(run_id, "call-2", "tool", {})
        with self.assertRaises(StaleRunError):
            store.transition(run_id, "prepare_model")

    def test_finalized_call_atomically_advances_projection_and_does_not_reapply(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        store.start_call(run_id, "call-1:final", "finalization", {})
        outcome = store.finish_call(run_id, "call-1:final", {"message": "done"}, checkpoint={"history": ["done"]}, phase="prepare_model")
        run = store.get_run(run_id)
        self.assertEqual(run["checkpoint"], {"history": ["done"]})
        self.assertEqual(run["checkpoint_seq"], store.read_events(run_id)[-1]["seq"])
        self.assertEqual(run["phase"], "prepare_model")
        store.transition(run_id, "dispatch_tool:1", checkpoint={"history": ["done", "later"]})
        self.assertEqual(store.finish_call(run_id, "call-1:final", {"message": "done"}, checkpoint={"history": ["done"]}, phase="prepare_model"), outcome)
        self.assertEqual(store.get_run(run_id)["checkpoint"], {"history": ["done", "later"]})
        self.assertEqual(store.get_run(run_id)["phase"], "dispatch_tool:1")

    def test_cancelled_run_cannot_commit_new_finalization_projection(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        store.start_call(run_id, "call-1:final", "finalization", {})
        store.control("context-1")
        with self.assertRaises(StaleRunError):
            store.finish_call(run_id, "call-1:final", {}, checkpoint={"history": ["late"]}, phase="prepare_model")
        self.assertEqual(store.get_call(run_id, "call-1:final")["status"], "intent")

    def test_reset_fences_old_generation_and_allows_new_admission(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        store.start_call(run_id, "call-1", "tool", {})
        self.assertEqual(store.control("context-1", "reset")["generation"], 1)
        with self.assertRaises(StaleRunError):
            store.finish_call(run_id, "call-1", {"late": True})
        self.assertEqual(self.admit(store, "input-2")["generation"], 1)

    def test_batch_controls_rollback_every_context_when_second_write_fails(self):
        store = self.store()
        parent = self.admit(store)
        child = store.admit("child-context", "child-input", {}, {})
        original = store._event
        def fail_child(run_id, *args, **kwargs):
            if run_id == child["run_id"]:
                raise sqlite3.OperationalError("synthetic second-context failure")
            return original(run_id, *args, **kwargs)
        with patch.object(store, "_event", fail_child):
            with self.assertRaises(DurableStoreError):
                store.control_many(["context-1", "child-context"], "reset")
        self.assertEqual(store.get_run(parent["run_id"]), parent)
        self.assertEqual(store.get_run(child["run_id"]), child)
        self.assertEqual(len(store.read_events(parent["run_id"])), 1)
        generations = store._connection.execute("SELECT generation FROM contexts").fetchall()
        self.assertEqual([row[0] for row in generations], [0, 0])

    def test_batch_reset_validates_all_ids_deduplicates_and_fences_all_generations(self):
        store = self.store()
        parent = self.admit(store)
        child = store.admit("child-context", "child-input", {}, {})
        for run in (parent, child):
            store.start_call(run["run_id"], "call-1", "tool", {})
        with self.assertRaises(ValueError):
            store.control_many(["context-1", "../bad"], "reset")
        with self.assertRaises(ValueError):
            store.control_many("context-1", "cancel")
        self.assertEqual(store.get_run(parent["run_id"])["status"], "running")
        updated = store.control_many(["context-1", "child-context", "context-1"], "reset")
        self.assertEqual([row["generation"] for row in updated], [1, 1])
        self.assertEqual([row["context_id"] for row in updated], ["context-1", "child-context"])
        for run in (parent, child):
            self.assertEqual(store.get_run(run["run_id"])["status"], "cancelled")
            with self.assertRaises(StaleRunError):
                store.finish_call(run["run_id"], "call-1", {})

    def test_delete_scrubs_private_payloads_and_tombstone_survives(self):
        store = self.store()
        sentinel = "PRIVATE_RECOVERY_PAYLOAD_82be74d32"
        run_id = store.admit("context-1", "input-1", {"text": sentinel}, {"history": [sentinel]})["run_id"]
        store.start_call(run_id, "call-1", "tool", {"arg": sentinel})
        store.finish_call(run_id, "call-1", {"result": sentinel})
        store.transition(run_id, "complete", status="completed", payload=sentinel)
        deleted = store.control("context-1", "delete")
        self.assertEqual(deleted["deleted"], 1)
        self.assertIsNone(store.get_run(run_id)["checkpoint"])
        self.assertIsNone(store.get_run(run_id)["input_payload"])
        self.assertIsNone(store.get_call(run_id, "call-1")["payload"])
        self.assertIsNone(store.get_call(run_id, "call-1")["result"])
        self.assertTrue(all(event["payload"] is None for event in store.read_events(run_id)))
        for path in self.root.iterdir():
            if path.is_file():
                self.assertNotIn(sentinel.encode(), path.read_bytes())
        store.close()
        with LocalStore(self.root) as reopened:
            with self.assertRaises(StaleRunError):
                self.admit(reopened)

    def test_checkpoint_and_call_corruption_raise_without_replacement(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        store.start_call(run_id, "call-1", "tool", {})
        store._connection.execute("UPDATE calls SET payload='{}x' WHERE run_id=?", (run_id,))
        with self.assertRaises(IntegrityError):
            store.get_call(run_id, "call-1")
        store._connection.execute("UPDATE runs SET checkpoint='{}' WHERE run_id=?", (run_id,))
        with self.assertRaises(IntegrityError):
            store.get_run(run_id)
        self.assertEqual(store._connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)

    def test_metadata_inventory_isolates_one_corrupt_checkpoint(self):
        store = self.store()
        corrupt = self.admit(store)
        healthy = store.admit("context-2", "input-2", {}, {"history": []})
        store._connection.execute("UPDATE runs SET checkpoint='{}' WHERE run_id=?", (corrupt["run_id"],))
        headers = store.list_run_headers(statuses=("running",))
        self.assertEqual(len(headers), 2)
        self.assertTrue(all("checkpoint" not in row and "input_payload" not in row for row in headers))
        self.assertEqual(store.list_run_headers(context_id="context-2")[0]["run_id"], healthy["run_id"])
        self.assertEqual(store.get_run(healthy["run_id"]), healthy)
        with self.assertRaises(IntegrityError):
            store.get_run(corrupt["run_id"])
        with self.assertRaises(ValueError):
            store.list_run_headers(context_id="../bad")
        with self.assertRaises(ValueError):
            store.list_run_headers(statuses=("invalid",))

    def test_schema_and_database_corruption_fail_closed(self):
        self.root.mkdir()
        path = self.root / "state.sqlite3"
        path.write_bytes(b"not sqlite")
        with self.assertRaises(IntegrityError):
            LocalStore(self.root)
        self.assertEqual(path.read_bytes(), b"not sqlite")
        path.unlink()
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA user_version=100")
        conn.close()
        with self.assertRaises(IntegrityError):
            LocalStore(self.root)
        conn = sqlite3.connect(path)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 100)
        conn.close()

    def test_strict_json_size_and_path_validation(self):
        store = self.store()
        for value in [float("nan"), {1: "wrong key"}, {"tuple": (1,)}, object()]:
            with self.subTest(value=type(value)):
                with self.assertRaises(ValueError):
                    store.admit("context-1", "input-1", value, {})
        with self.assertRaises(ValueError):
            store.admit("../escape", "input-1", {}, {})
        with patch("helpers.durable.store._MAX_JSON", 10):
            with self.assertRaises(ValueError):
                store.admit("context-1", "input-1", "x" * 20, {})
        self.assertEqual(store.list_runs(), [])

    @unittest.skipUnless(os.name == "posix", "POSIX private mode and symlink checks")
    def test_owner_only_permissions_and_symlink_rejection(self):
        store = self.store()
        self.admit(store)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        for path in self.root.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)
        link = self.directory / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OwnershipError):
            LocalStore(link)
        with self.assertRaises(OwnershipError):
            LocalStore(link / "nested")
        store.close()
        (self.root / "state.sqlite3-shm").symlink_to(self.directory / "missing")
        with self.assertRaises(OwnershipError):
            LocalStore(self.root)

    def test_live_owner_never_expires_and_release_allows_reopen(self):
        store = self.store()
        self.admit(store)
        with self.assertRaises(OwnershipError):
            LocalStore(self.root)
        process = self.child("try:\n    LocalStore(root)\nexcept OwnershipError:\n    print('owned', flush=True)")
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), "owned")
        store.close()
        with LocalStore(self.root) as reopened:
            self.assertEqual(len(reopened.list_runs()), 1)

    def test_removed_ownership_file_blocks_new_effect_intents(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        (self.root / "owner.lock").unlink()
        with self.assertRaises(OwnershipError):
            store.start_call(run_id, "call-1", "tool", {})
        self.assertIsNone(store.get_call(run_id, "call-1"))

    def test_consistent_private_backup_includes_wal_outcomes(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        store.start_call(run_id, "call-1", "model", {})
        store.finish_call(run_id, "call-1", {"text": "persisted outcome"})
        backup_path = store.backup(self.directory / "snapshots" / "snapshot.sqlite3")
        conn = sqlite3.connect(backup_path)
        self.assertEqual(json.loads(conn.execute("SELECT result FROM calls").fetchone()[0])["text"], "persisted outcome")
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        conn.close()
        with self.assertRaises(FileExistsError):
            store.backup(backup_path)

    def test_backup_marks_only_snapshot_inert_and_marker_survives_reopen(self):
        store = self.store()
        self.admit(store)
        self.assertFalse(store.requires_restore_review())
        restored_root = self.directory / "restored"
        restored_root.mkdir()
        store.backup(restored_root / "state.sqlite3")
        self.assertFalse(store.requires_restore_review())
        with LocalStore(restored_root) as restored:
            self.assertTrue(restored.requires_restore_review())
            self.assertEqual(len(restored.list_runs(statuses=("running",))), 1)
        with LocalStore(restored_root) as reopened:
            self.assertTrue(reopened.requires_restore_review())

    def test_schema_one_migrates_metadata_without_changing_run(self):
        store = self.store()
        original = self.admit(store)
        for table in ("documents", "document_events", "document_mutations", "document_conflicts", "review_requests", "review_resolutions", "restore_selections", "retry_grants"):
            store._connection.execute(f"DROP TABLE {table}")
        for column in ("document_edits_digest", "logical_call_id", "attempt"):
            store._connection.execute(f"ALTER TABLE calls DROP COLUMN {column}")
        for table in ("runs", "events", "calls"):
            store._connection.execute(f"ALTER TABLE {table} DROP COLUMN payloads_pruned")
        store._connection.execute("DROP TABLE backup_blobs")
        store._connection.execute("DROP TABLE blobs")
        store._connection.execute("DROP TABLE metadata")
        store._connection.execute("PRAGMA user_version=1")
        store.close()
        with LocalStore(self.root) as reopened:
            self.assertEqual(reopened.get_run(original["run_id"]), original)
            self.assertFalse(reopened.requires_restore_review())

    def test_process_kill_before_backup_publication_leaves_no_visible_snapshot(self):
        process = self.child("""store = LocalStore(root)
store.admit('context-1', 'input-1', {}, {'schema': 1})
# Park at snapshot fsync, before atomic destination publication.
original_fsync = os.fsync
def park(fd):
    print('before_publish', flush=True)
    time.sleep(300)
    original_fsync(fd)
os.fsync = park
store.backup(root.parent / 'backup.sqlite3')
""")
        self.assertEqual(self.barrier(process), "before_publish")
        self.kill(process)
        self.assertFalse((self.root.parent / "backup.sqlite3").exists())

    def test_threads_share_atomic_single_context_admission(self):
        store = self.store()
        outcomes = []
        def submit(index):
            try:
                outcomes.append(self.admit(store, f"input-{index}")["run_id"])
            except ConflictError:
                outcomes.append(None)
        threads = [threading.Thread(target=submit, args=(index,)) for index in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(outcome is not None for outcome in outcomes), 1)
        self.assertEqual(len(store.list_runs()), 1)

    def test_process_kill_before_admission_commit_leaves_no_orphan(self):
        process = self.child("""store = LocalStore(root)
original = store._event
def park(*args, **kwargs):
    sequence = original(*args, **kwargs)
    print('before_commit', flush=True)
    time.sleep(300)
    return sequence
store._event = park
store.admit('context-1', 'input-1', {'text': 'synthetic'}, {'schema': 1})""")
        self.assertEqual(self.barrier(process), "before_commit")
        self.kill(process)
        with LocalStore(self.root) as reopened:
            self.assertEqual(reopened.list_runs(), [])
            self.assertEqual(reopened._connection.execute("SELECT COUNT(*) FROM contexts").fetchone()[0], 0)

    def test_process_kill_during_or_after_finalization_commits_result_and_projection_together(self):
        for committed in (False, True):
            with self.subTest(committed=committed):
                self.root = self.directory / ("committed" if committed else "uncommitted")
                setup = """store = LocalStore(root)
run = store.admit('context-1', 'input-1', {}, {'history': []})
store.start_call(run['run_id'], 'call-1:final', 'finalization', {})
"""
                if not committed:
                    setup += """original = store._event
def park(*args, **kwargs):
    sequence = original(*args, **kwargs)
    print(run['run_id'], flush=True)
    time.sleep(300)
    return sequence
store._event = park
"""
                setup += """store.finish_call(run['run_id'], 'call-1:final', {'message': 'done'}, checkpoint={'history': ['done']}, phase='prepare_model')
print(run['run_id'], flush=True)
time.sleep(300)
"""
                process = self.child(setup)
                run_id = self.barrier(process)
                self.kill(process)
                with LocalStore(self.root) as reopened:
                    run = reopened.get_run(run_id)
                    call = reopened.get_call(run_id, "call-1:final")
                    self.assertEqual(call["status"], "completed" if committed else "intent")
                    self.assertEqual(run["checkpoint"], {"history": ["done"] if committed else []})
                    self.assertEqual(run["phase"], "prepare_model" if committed else "admitted")

    def test_process_kill_after_commits_preserves_admission_intent_and_result(self):
        for boundary in ("admission", "intent", "result"):
            with self.subTest(boundary=boundary):
                self.root = self.directory / boundary
                process = self.child("\n".join([
                    "store = LocalStore(root)",
                    "run = store.admit('context-1', 'input-1', {'text': 'synthetic'}, {'schema': 1})",
                    *( ["store.start_call(run['run_id'], 'call-1', 'tool', {'effect': 'synthetic'})"] if boundary != "admission" else []),
                    *( ["store.finish_call(run['run_id'], 'call-1', {'outcome': 'committed'})"] if boundary == "result" else []),
                    "print(run['run_id'], flush=True)",
                    "time.sleep(300)",
                ]))
                run_id = self.barrier(process)
                self.kill(process)
                with LocalStore(self.root) as reopened:
                    run = reopened.get_run(run_id)
                    self.assertEqual(run["checkpoint"], {"schema": 1})
                    self.assertEqual(len(reopened.list_runs()), 1)
                    self.assertEqual(reopened.admit("context-1", "input-1", {"text": "synthetic"}, {})["run_id"], run_id)
                    call = reopened.get_call(run_id, "call-1")
                    if boundary == "admission":
                        self.assertIsNone(call)
                    else:
                        self.assertEqual(call["status"], "completed" if boundary == "result" else "intent")
                        self.assertEqual(call["replay"], "never")
                        self.assertEqual(call["result"], {"outcome": "committed"} if boundary == "result" else None)


if __name__ == "__main__":
    unittest.main()
