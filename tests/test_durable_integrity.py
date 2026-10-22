"""Missing integrity metadata cannot turn verification off for retained data."""
from pathlib import Path
import tempfile
import unittest

from helpers.durable.store import IntegrityError, LocalStore


class DurableIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.temporary.name).resolve() / "store")
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.store.close)
        self.run_id = self.store.admit("context", "input", None, None)["run_id"]
        self.store.start_call(self.run_id, "call", "tool", None)
        self.store.finish_call(self.run_id, "call", None)

    def test_run_input_and_checkpoint_require_digest_and_payload(self):
        for payload, digest in (("input_payload", "input_digest"), ("checkpoint", "checkpoint_digest")):
            original = self.store._connection.execute(f"SELECT {payload},{digest} FROM runs").fetchone()
            for invalid in (None, "", "bad", "A" * 64):
                with self.subTest(column=digest, invalid=invalid):
                    self.store._connection.execute(f"UPDATE runs SET {digest}=?", (invalid,))
                    with self.assertRaises(IntegrityError):
                        self.store.get_run(self.run_id)
            self.store._connection.execute(f"UPDATE runs SET {digest}=?,{payload}=NULL", (original[digest],))
            with self.assertRaises(IntegrityError):
                self.store.get_run(self.run_id)
            self.store._connection.execute(f"UPDATE runs SET {payload}=?,{digest}=?", tuple(original))
        self.assertIsNone(self.store.get_run(self.run_id)["checkpoint"])

    def test_completed_results_and_call_fingerprints_cannot_lose_integrity_metadata(self):
        for column in ("result_digest", "fingerprint"):
            original = self.store._connection.execute(f"SELECT {column} FROM calls").fetchone()[0]
            for invalid in (None, "", "bad"):
                with self.subTest(column=column, invalid=invalid):
                    self.store._connection.execute(f"UPDATE calls SET {column}=?", (invalid,))
                    with self.assertRaises(IntegrityError):
                        self.store.get_call(self.run_id, "call")
            self.store._connection.execute(f"UPDATE calls SET {column}=?", (original,))
        for column in ("result", "payload"):
            original = self.store._connection.execute(f"SELECT {column} FROM calls").fetchone()[0]
            self.store._connection.execute(f"UPDATE calls SET {column}=NULL")
            with self.assertRaises(IntegrityError):
                self.store.get_call(self.run_id, "call")
            self.store._connection.execute(f"UPDATE calls SET {column}=?", (original,))
        self.store.start_call(self.run_id, "unresolved", "model", None)
        self.assertIsNone(self.store.get_call(self.run_id, "unresolved")["result"])

    def test_retained_events_require_digest_even_for_json_null(self):
        self.store._connection.execute("UPDATE events SET payload='null',payload_digest=NULL")
        with self.assertRaises(IntegrityError):
            self.store.read_events(self.run_id)

    def test_documents_and_conflict_proposals_require_integrity_metadata(self):
        self.store.write_document("context", "todo", 1, None, 0, "mutation")
        digest = self.store._connection.execute("SELECT digest FROM documents").fetchone()[0]
        self.store._connection.execute("UPDATE documents SET digest='' ")
        with self.assertRaises(IntegrityError):
            self.store.read_document("context", "todo")
        self.store._connection.execute("UPDATE documents SET digest=?", (digest,))
        self.store.start_call(self.run_id, "draft", "tool", {})
        self.store.finish_call(self.run_id, "draft", {}, document_edits=[
            {"kind": "todo", "schema_version": 1, "expected_revision": 0, "value": None}])
        conflict = self.store.list_document_conflicts(self.run_id)[0]
        self.store._connection.execute("UPDATE document_conflicts SET digest=NULL")
        with self.assertRaises(IntegrityError):
            self.store.list_document_conflicts(self.run_id)
        self.store._connection.execute("UPDATE document_conflicts SET digest=?", (conflict["digest"],))
        self.store._connection.execute("UPDATE document_conflicts SET proposed=NULL,digest=NULL,status='resolved'")
        with self.assertRaises(IntegrityError):
            self.store.list_document_conflicts(self.run_id)

    def test_pruned_payloads_and_resolved_proposals_remain_readable_as_tombstones(self):
        self.store.write_document("context", "todo", 1, None, 0, "mutation")
        self.store.start_call(self.run_id, "draft", "tool", {})
        self.store.finish_call(self.run_id, "draft", {}, document_edits=[
            {"kind": "todo", "schema_version": 1, "expected_revision": 0, "value": None}])
        conflict = self.store.list_document_conflicts(self.run_id)[0]
        self.store.resolve_document_conflict(self.run_id, conflict["conflict_id"], "keep_current", 1,
            self.store.get_review(self.run_id)["version"], "resolve")
        self.store.transition(self.run_id, "complete", status="completed")
        self.store.compact(retain_terminal=0)
        self.assertTrue(self.store.get_run(self.run_id)["payloads_pruned"])
        self.assertTrue(self.store.get_call(self.run_id, "draft")["payloads_pruned"])
        self.assertIsNone(self.store.list_document_conflicts(self.run_id)[0]["proposed"])
        self.assertTrue(all(row["payloads_pruned"] for row in self.store.read_events(self.run_id)))
        self.store.control("context", "delete")
        self.assertTrue(self.store.get_call(self.run_id, "call")["payloads_pruned"])


if __name__ == "__main__":
    unittest.main()
