"""File-backed recovery payloads, portable backups and safe terminal retention."""

import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from helpers.durable.store import (
    ConflictError, DurableStoreError, IntegrityError, LocalStore, OwnershipError,
)


LARGE = {"text": "synthetic-recovery-value-" * 4096}


class DurableBlobTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name).resolve()
        self.root = self.directory / "recovery"
        self.addCleanup(self.temporary.cleanup)

    def store(self):
        store = LocalStore(self.root)
        self.addCleanup(store.close)
        return store

    def files(self, store):
        return sorted(store.blob_root.glob("*.json"))

    def admit(self, store, context="context-1", input_id="input-1", payload=LARGE, checkpoint=LARGE):
        return store.admit(context, input_id, payload, checkpoint)

    def settled(self, store, context, payload=LARGE):
        run = self.admit(store, context, payload=payload, checkpoint=payload)
        store.start_call(run["run_id"], "call-1", "tool", payload)
        store.finish_call(run["run_id"], "call-1", payload)
        return store.transition(run["run_id"], "complete", status="completed")

    def child(self, body):
        code = "\n".join([
            "import os, sys, time",
            "from pathlib import Path",
            "from helpers.durable.store import LocalStore",
            "root = Path(sys.argv[1])",
            "large = {'text': 'synthetic-recovery-value-' * 4096}",
            body,
        ])
        process = subprocess.Popen([sys.executable, "-u", "-c", code, str(self.root)],
                                   cwd=Path(__file__).resolve().parents[1],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: self.stop(process))
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)

    def barrier(self, process):
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(10), "Child did not reach the crash barrier")
        text = process.stdout.readline().strip()
        self.assertTrue(text, process.stderr.read() if process.poll() is not None else "Empty barrier")
        return text

    @staticmethod
    def kill(process):
        if os.name == "posix":
            os.kill(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=10)

    def test_large_input_checkpoint_calls_results_and_events_offload_and_deduplicate(self):
        store = self.store()
        run = self.admit(store)
        run_id = run["run_id"]
        self.assertEqual(run["input_payload"], LARGE)
        self.assertEqual(run["checkpoint"], LARGE)
        self.assertEqual(len(self.files(store)), 1)
        blob = self.files(store)[0]
        self.assertEqual(blob.stem, hashlib.sha256(blob.read_bytes()).hexdigest())
        store.start_call(run_id, "call-1", "model", LARGE)
        store.finish_call(run_id, "call-1", LARGE)
        store.transition(run_id, "model_ready", checkpoint=LARGE, payload=LARGE)
        self.assertEqual(store.get_call(run_id, "call-1")["result"], LARGE)
        self.assertEqual(store.read_events(run_id)[-1]["payload"]["detail"], LARGE)
        row = store._connection.execute("SELECT input_payload,checkpoint FROM runs WHERE run_id=?", (run_id,)).fetchone()
        self.assertTrue(row["input_payload"].startswith("@blob:"))
        self.assertEqual(row["input_payload"], row["checkpoint"])
        call = store._connection.execute("SELECT payload,result FROM calls WHERE run_id=?", (run_id,)).fetchone()
        self.assertEqual(call["payload"], row["input_payload"])
        self.assertEqual(call["result"], row["input_payload"])
        self.assertEqual(store._connection.execute("SELECT COUNT(*) FROM blobs").fetchone()[0], 2)
        store.close()
        with LocalStore(self.root) as reopened:
            self.assertEqual(reopened.get_run(run_id)["checkpoint"], LARGE)
            self.assertEqual(reopened.get_call(run_id, "call-1")["payload"], LARGE)

    def test_inline_json_and_reference_like_user_strings_remain_compatible(self):
        store = self.store()
        payload = "@blob:" + "a" * 64
        run = self.admit(store, payload=payload, checkpoint={"small": True})
        self.assertEqual(store.get_run(run["run_id"])["input_payload"], payload)
        self.assertEqual(self.files(store), [])
        value = store._connection.execute("SELECT input_payload FROM runs").fetchone()[0]
        self.assertEqual(json.loads(value), payload)

    def test_blob_digest_and_size_corruption_are_isolated_from_other_contexts(self):
        store = self.store()
        damaged = self.admit(store)
        healthy = self.admit(store, "context-2", payload={"small": True}, checkpoint={"small": True})
        blob = self.files(store)[0]
        original = blob.read_bytes()
        for corrupt in (b"x", b"x" * len(original)):
            blob.write_bytes(corrupt)
            with self.assertRaises(IntegrityError):
                store.get_run(damaged["run_id"])
            self.assertEqual(len(store.list_run_headers()), 2)
            self.assertEqual(store.get_run(healthy["run_id"]), healthy)
        blob.write_bytes(original)
        blob.unlink()
        with self.assertRaises(IntegrityError):
            store.get_run(damaged["run_id"])

    def test_catalog_and_reference_validation_fail_closed(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        store._connection.execute("UPDATE blobs SET size=size+1")
        with self.assertRaises(IntegrityError):
            store.get_run(run_id)
        store._connection.execute("UPDATE runs SET checkpoint='@blob:../../escape' WHERE run_id=?", (run_id,))
        with self.assertRaises(IntegrityError):
            store.get_run(run_id)
        with self.assertRaises(IntegrityError):
            store.garbage_collect()
        self.assertEqual(len(self.files(store)), 1)

    @unittest.skipUnless(os.name == "posix", "POSIX custody checks")
    def test_blob_modes_and_symlink_rejection(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        blob = self.files(store)[0]
        self.assertEqual(stat.S_IMODE(store.blob_root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(blob.stat().st_mode), 0o600)
        data = blob.read_bytes()
        other = self.directory / "other.json"
        other.write_bytes(data)
        blob.unlink()
        blob.symlink_to(other)
        with self.assertRaises(OwnershipError):
            store.get_run(run_id)
        with self.assertRaises(OwnershipError):
            self.admit(store, "context-2")
        self.assertEqual(other.read_bytes(), data)

    def test_publish_failure_rolls_back_before_a_reference_becomes_visible(self):
        store = self.store()
        with patch("helpers.durable.store.os.fsync", side_effect=OSError("synthetic disk full")):
            with self.assertRaises(DurableStoreError):
                self.admit(store)
        self.assertEqual(store.list_run_headers(), [])
        self.assertEqual(self.files(store), [])
        self.assertEqual(list(store.blob_root.iterdir()), [])
        self.assertEqual(store._connection.execute("SELECT COUNT(*) FROM blobs").fetchone()[0], 0)

    def test_published_orphan_and_abandoned_temporary_file_are_collected(self):
        store = self.store()
        with patch.object(store, "_event", side_effect=sqlite3.OperationalError("synthetic transaction rollback")):
            with self.assertRaises(DurableStoreError):
                self.admit(store)
        self.assertEqual(len(self.files(store)), 1)
        (store.blob_root / ".pending-orphan").write_bytes(b"partial private bytes")
        counts = store.garbage_collect()
        self.assertEqual(counts["blobs_removed"], 2)
        self.assertGreater(counts["bytes_removed"], 0)
        self.assertEqual(list(store.blob_root.iterdir()), [])

    def test_portable_single_file_backup_embeds_and_lazily_hydrates_blobs(self):
        store = self.store()
        run_id = self.admit(store)["run_id"]
        store.start_call(run_id, "call-1", "model", {"request": LARGE})
        store.finish_call(run_id, "call-1", {"outcome": LARGE})
        snapshot = store.backup(self.directory / "snapshot.sqlite3")
        connection = sqlite3.connect(snapshot)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM backup_blobs").fetchone()[0], 3)
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        connection.close()
        restored_root = self.directory / "restored"
        restored_root.mkdir()
        shutil.copyfile(snapshot, restored_root / "state.sqlite3")
        with LocalStore(restored_root) as restored:
            self.assertTrue(restored.requires_restore_review())
            self.assertEqual(self.files(restored), [])
            self.assertEqual(restored.get_run(run_id)["input_payload"], LARGE)
            self.assertEqual(restored.get_call(run_id, "call-1")["result"], {"outcome": LARGE})
            self.assertEqual(len(self.files(restored)), 3)
            self.assertEqual(restored._connection.execute("SELECT COUNT(*) FROM backup_blobs").fetchone()[0], 0)
        with LocalStore(restored_root) as reopened:
            self.assertEqual(reopened.get_run(run_id)["checkpoint"], LARGE)

    def test_corrupt_backup_bytes_hold_only_the_referencing_context(self):
        store = self.store()
        damaged = self.admit(store)
        healthy = self.admit(store, "context-2", payload={}, checkpoint={})
        restored_root = self.directory / "restored"
        restored_root.mkdir()
        store.backup(restored_root / "state.sqlite3")
        connection = sqlite3.connect(restored_root / "state.sqlite3")
        connection.execute("UPDATE backup_blobs SET data=?", (b"invalid backup bytes",))
        connection.commit()
        connection.close()
        with LocalStore(restored_root) as restored:
            with self.assertRaises(IntegrityError):
                restored.get_run(damaged["run_id"])
            self.assertEqual(restored.get_run(healthy["run_id"]), healthy)
            self.assertEqual(len(restored.list_run_headers()), 2)

    def test_backup_failure_does_not_publish_an_incomplete_snapshot(self):
        store = self.store()
        self.admit(store)
        self.files(store)[0].unlink()
        destination = self.directory / "snapshot.sqlite3"
        with self.assertRaises(IntegrityError):
            store.backup(destination)
        self.assertFalse(destination.exists())

    def test_delete_reclaims_unreachable_blobs_and_preserves_shared_context_data(self):
        store = self.store()
        first = self.admit(store)
        second = self.admit(store, "context-2")
        self.assertEqual(len(self.files(store)), 1)
        store.control("context-1", "delete")
        self.assertIsNone(store.get_run(first["run_id"])["input_payload"])
        self.assertEqual(store.get_run(second["run_id"])["checkpoint"], LARGE)
        self.assertEqual(len(self.files(store)), 1)
        store.control("context-2", "delete")
        self.assertEqual(self.files(store), [])
        self.assertEqual(store._connection.execute("SELECT COUNT(*) FROM blobs").fetchone()[0], 0)

    def test_batch_delete_scrubs_parent_and_child_payloads_and_all_blob_references(self):
        store = self.store()
        parent = self.admit(store)
        child = self.admit(store, "child-context", payload={"child": LARGE}, checkpoint={"child": LARGE})
        for run in (parent, child):
            store.start_call(run["run_id"], "call-1", "tool", {"request": LARGE})
        updated = store.control_many(["context-1", "child-context"], "delete")
        self.assertTrue(all(row["deleted"] for row in updated))
        self.assertEqual(self.files(store), [])
        self.assertEqual(store._connection.execute("SELECT COUNT(*) FROM blobs").fetchone()[0], 0)
        self.assertEqual(store._connection.execute("SELECT COUNT(*) FROM backup_blobs").fetchone()[0], 0)
        for run in (parent, child):
            self.assertIsNone(store.get_run(run["run_id"])["checkpoint"])
            self.assertIsNone(store.get_call(run["run_id"], "call-1")["payload"])

    def test_retention_preserves_retry_headers_fingerprints_and_event_sequences(self):
        store = self.store()
        run = self.settled(store, "context-1")
        run_id = run["run_id"]
        before = store.read_events(run_id)
        counts = store.compact(retain_terminal=0, max_age_days=None)
        self.assertEqual(counts["runs_pruned"], 1)
        self.assertEqual(counts["calls_pruned"], 1)
        self.assertEqual(counts["events_pruned"], len(before))
        retained = store.get_run(run_id)
        self.assertTrue(retained["payloads_pruned"])
        self.assertIsNone(retained["input_payload"])
        self.assertIsNone(retained["checkpoint"])
        self.assertTrue(store.matches_input(run_id, LARGE))
        self.assertFalse(store.matches_input(run_id, {"changed": True}))
        self.assertTrue(store.matches_call(run_id, "call-1", LARGE))
        self.assertFalse(store.matches_call(run_id, "call-1", {}))
        call = store.get_call(run_id, "call-1")
        self.assertTrue(call["payloads_pruned"])
        self.assertIsNone(call["payload"])
        self.assertIsNone(call["result"])
        self.assertTrue(call["fingerprint"] and call["result_digest"])
        self.assertEqual([event["seq"] for event in store.read_events(run_id)], [event["seq"] for event in before])
        self.assertTrue(all(event["payloads_pruned"] and event["payload"] is None for event in store.read_events(run_id)))
        self.assertEqual(self.admit(store)["run_id"], run_id)
        with self.assertRaises(ConflictError):
            self.admit(store, payload={"changed": True})
        self.assertEqual(self.files(store), [])

    def test_retention_never_prunes_active_unresolved_or_protected_work(self):
        store = self.store()
        active = self.admit(store)
        unresolved = self.admit(store, "context-2")
        store.start_call(unresolved["run_id"], "call-1", "tool", LARGE)
        store.control("context-2", "cancel")
        protected = self.settled(store, "context-3")
        counts = store.compact(retain_terminal=0, max_age_days=0, protected_run_ids=(protected["run_id"],))
        self.assertEqual(counts["runs_pruned"], 0)
        for run in (active, unresolved, protected):
            self.assertFalse(store.get_run(run["run_id"])["payloads_pruned"])
            self.assertEqual(store.get_run(run["run_id"])["checkpoint"], LARGE)
        # A late known outcome closes the unresolved call; it is now eligible.
        store.finish_call(unresolved["run_id"], "call-1", LARGE)
        counts = store.compact(retain_terminal=0, max_age_days=0, protected_run_ids=(protected["run_id"],))
        self.assertEqual(counts["runs_pruned"], 1)
        self.assertTrue(store.get_run(unresolved["run_id"])["payloads_pruned"])

    def test_default_terminal_count_and_age_limits_are_bounded(self):
        store = self.store()
        runs = [self.settled(store, f"context-{index}", payload={"index": index}) for index in range(102)]
        counts = store.compact()
        self.assertEqual(counts["runs_pruned"], 2)
        self.assertEqual(sum(not run["payloads_pruned"] for run in store.list_runs()), 100)
        store._connection.execute("UPDATE runs SET updated_at=? WHERE run_id=?", (time.time() - 31 * 86400, runs[-1]["run_id"]))
        self.assertEqual(store.compact()["runs_pruned"], 1)
        self.assertEqual(store.compact()["runs_pruned"], 0)

    def test_invalid_retention_policy_is_rejected_before_mutation(self):
        store = self.store()
        run = self.settled(store, "context-1")
        for kwargs in ({"retain_terminal": -1}, {"retain_terminal": True},
                       {"max_age_days": -1}, {"max_age_days": float("nan")},
                       {"protected_run_ids": ("../unsafe",)}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    store.compact(**kwargs)
        self.assertFalse(store.get_run(run["run_id"])["payloads_pruned"])

    def test_schema_two_inline_data_migrates_without_changing_identity(self):
        store = self.store()
        run = self.admit(store, payload={"small": True}, checkpoint={"schema": 1})
        for table in ("documents", "document_events", "document_mutations", "document_conflicts", "review_requests", "review_resolutions", "restore_selections", "retry_grants"):
            store._connection.execute(f"DROP TABLE {table}")
        for column in ("document_edits_digest", "logical_call_id", "attempt"):
            store._connection.execute(f"ALTER TABLE calls DROP COLUMN {column}")
        for table in ("runs", "events", "calls"):
            store._connection.execute(f"ALTER TABLE {table} DROP COLUMN payloads_pruned")
        store._connection.execute("DROP TABLE backup_blobs")
        store._connection.execute("DROP TABLE blobs")
        store._connection.execute("PRAGMA user_version=2")
        store.close()
        with LocalStore(self.root) as reopened:
            self.assertEqual(reopened.get_run(run["run_id"]), run)
            self.assertEqual(self.admit(reopened, "context-2")["checkpoint"], LARGE)
            self.assertEqual(len(self.files(reopened)), 1)

    def test_process_kill_after_blob_publish_before_sql_commit_leaves_only_collectable_orphan(self):
        process = self.child("""store = LocalStore(root)
original = store._event
def park(*args, **kwargs):
    sequence = original(*args, **kwargs)
    print('published', flush=True)
    time.sleep(300)
    return sequence
store._event = park
store.admit('context-1', 'input-1', large, large)
""")
        self.assertEqual(self.barrier(process), "published")
        self.assertEqual(len(list((self.root / "blobs").glob("*.json"))), 1)
        self.kill(process)
        with LocalStore(self.root) as reopened:
            self.assertEqual(reopened.list_run_headers(), [])
            self.assertEqual(reopened.garbage_collect()["blobs_removed"], 1)

    def test_process_kill_after_offloaded_result_commit_reuses_verified_bytes(self):
        process = self.child("""store = LocalStore(root)
run = store.admit('context-1', 'input-1', {}, {})
store.start_call(run['run_id'], 'call-1', 'model', {})
store.finish_call(run['run_id'], 'call-1', large, checkpoint={'result': large}, phase='model_result')
print(run['run_id'], flush=True)
time.sleep(300)
""")
        run_id = self.barrier(process)
        self.kill(process)
        with LocalStore(self.root) as reopened:
            self.assertEqual(reopened.get_call(run_id, "call-1")["result"], LARGE)
            self.assertEqual(reopened.get_run(run_id)["checkpoint"], {"result": LARGE})
            self.assertEqual(reopened.garbage_collect()["blobs_removed"], 0)


if __name__ == "__main__":
    unittest.main()
