"""Typed document CAS, atomic tool drafts and preserved external outcomes."""
import os
from pathlib import Path
import selectors
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from helpers.durable.store import ConflictError, DurableStoreError, LocalStore, StaleRunError


class DurableDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve() / "store"
        self.store = LocalStore(self.root)
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.store.close)

    def run_call(self):
        run = self.store.admit("context-1", "input-1", {}, {"paused": False})
        self.store.start_call(run["run_id"], "call-1", "tool", {})
        return run["run_id"]

    def edit(self, kind="plan", expected=0, value=None, version=1):
        return {"kind": kind, "schema_version": version, "expected_revision": expected,
                "value": value if value is not None else {"items": ["synthetic"]}}

    def test_app_cas_idempotency_generations_and_schema_migration(self):
        document = self.store.write_document("context-1", "plan", 1, {"items": []}, 0, "mutation-1", 0)
        self.assertEqual(document["revision"], 1)
        self.assertEqual(self.store.write_document("context-1", "plan", 1, {"items": []}, 0, "mutation-1", 0), document)
        with self.assertRaises(ConflictError):
            self.store.write_document("context-1", "plan", 1, {"changed": True}, 0, "mutation-1", 0)
        with self.assertRaises(ConflictError):
            self.store.write_document("context-1", "plan", 1, {}, 0, "mutation-2", 0)
        migrated = self.store.write_document("context-1", "plan", 2, {"items": [], "version": 2}, 1, "migration", 0)
        self.assertEqual((migrated["revision"], migrated["schema_version"]), (2, 2))
        with self.assertRaises(ConflictError):
            self.store.write_document("context-1", "plan", 1, {}, 2, "downgrade", 0)
        self.store.control("context-1", "reset")
        refreshed = self.store.read_document("context-1", "plan")
        self.assertEqual(refreshed["generation"], 1)
        self.assertEqual(refreshed["revision"], 2)
        with self.assertRaises(StaleRunError):
            self.store.write_document("context-1", "plan", 2, {}, 2, "stale", 0)
        self.assertEqual(self.store.write_document("context-1", "plan", 2, {}, 2, "fresh", 1)["revision"], 3)

    def test_document_bounds_and_strict_json_are_checked_before_mutation(self):
        for value in ("x" * (64 * 1024), float("nan"), {1: "invalid"}):
            with self.assertRaises(ValueError):
                self.store.write_document("context-1", "plan", 1, value, 0, "mutation")
        for version, revision in ((0, 0), (True, 0), (1, -1), (1, True)):
            with self.assertRaises(ValueError):
                self.store.write_document("context-1", "plan", version, {}, revision, "mutation")
        self.assertIsNone(self.store.read_document("context-1", "plan"))

    def test_tool_edits_commit_with_unchanged_body_and_retries_never_reapply(self):
        run_id = self.run_call()
        edits = [self.edit(), self.edit("todo", value={"done": False})]
        self.assertIsNone(self.store.read_document("context-1", "plan"))
        body = {"response": {"message": "external effect completed", "break_loop": False}}
        call = self.store.finish_call(run_id, "call-1", body, document_edits=edits)
        self.assertEqual(call["result"], body)
        self.assertEqual(call["document_conflicts"], [])
        self.assertEqual(self.store.read_document("context-1", "plan")["revision"], 1)
        self.store.finish_call(run_id, "call-1", body, document_edits=edits)
        self.assertEqual(self.store.read_document("context-1", "plan")["revision"], 1)
        with self.assertRaises(ConflictError):
            self.store.finish_call(run_id, "call-1", body, document_edits=[self.edit(value={"changed": True})])
        events = self.store.read_document_events("context-1")
        self.assertEqual(len(events), 2)
        self.assertTrue(all("value" not in event for event in events))

    def test_any_cas_conflict_preserves_body_applies_no_edit_and_records_all_proposals(self):
        self.store.write_document("context-1", "plan", 1, {"app": "newer"}, 0, "app-write")
        run_id = self.run_call()
        body = {"actual_external_result": "committed"}
        call = self.store.finish_call(run_id, "call-1", body, document_edits=[self.edit(), self.edit("todo")])
        self.assertEqual(call["result"], body)
        self.assertEqual(len(call["document_conflicts"]), 2)
        self.assertEqual(self.store.read_document("context-1", "plan")["value"], {"app": "newer"})
        self.assertIsNone(self.store.read_document("context-1", "todo"))
        self.assertEqual({item["reason"] for item in call["document_conflicts"]}, {"revision_conflict", "transaction_conflict"})
        self.assertTrue(all(item["proposed"] == {"items": ["synthetic"]} for item in call["document_conflicts"]))
        self.store.transition(run_id, "needs_attention", status="attention")
        conflict = next(item for item in call["document_conflicts"] if item["kind"] == "plan")
        version = self.store.get_review(run_id)["version"]
        receipt = self.store.resolve_document_conflict(run_id, conflict["conflict_id"], "apply_proposed", 1, version, "resolution-1")
        self.assertEqual(self.store.read_document("context-1", "plan")["revision"], 2)
        self.assertEqual(self.store.get_call(run_id, "call-1")["result"], body)
        self.assertEqual(self.store.resolve_document_conflict(run_id, conflict["conflict_id"], "apply_proposed", 1, version, "resolution-1"), receipt)
        self.assertEqual(self.store.read_document("context-1", "plan")["revision"], 2)

    def test_stale_conflict_review_or_revision_cannot_modify_document(self):
        run_id = self.run_call()
        self.store.write_document("context-1", "plan", 1, {}, 0, "app")
        call = self.store.finish_call(run_id, "call-1", {"body": True}, document_edits=[self.edit()])
        conflict = call["document_conflicts"][0]
        token = self.store.get_review(run_id)["version"]
        self.store.write_document("context-1", "plan", 1, {"newer": True}, 1, "newer")
        with self.assertRaises(ConflictError):
            self.store.resolve_document_conflict(run_id, conflict["conflict_id"], "apply_proposed", 2, token, "stale")
        with self.assertRaises(ConflictError):
            self.store.resolve_document_conflict(run_id, conflict["conflict_id"], "keep_current", 1, self.store.get_review(run_id)["version"], "stale-revision")
        self.assertEqual(self.store.read_document("context-1", "plan")["value"], {"newer": True})

    def test_cancel_preserves_known_body_but_conflicts_and_blocks_its_staged_edit(self):
        run_id = self.run_call()
        self.store.control("context-1", "cancel")
        body = {"late_external_outcome": "known"}
        call = self.store.finish_call(run_id, "call-1", body, document_edits=[self.edit()])
        self.assertEqual(call["result"], body)
        self.assertIsNone(self.store.read_document("context-1", "plan"))
        conflict = call["document_conflicts"][0]
        self.assertEqual(conflict["reason"], "cancelled")
        with self.assertRaises(StaleRunError):
            self.store.resolve_document_conflict(run_id, conflict["conflict_id"], "apply_proposed", 0, mutation_id="unsafe")
        self.assertEqual(self.store.compact(retain_terminal=0, max_age_days=0)["runs_pruned"], 0)
        self.store.resolve_document_conflict(run_id, conflict["conflict_id"], "keep_current", 0, mutation_id="keep")
        self.assertEqual(self.store.compact(retain_terminal=0, max_age_days=0)["runs_pruned"], 1)

    def test_write_failure_rolls_back_body_documents_conflicts_and_events(self):
        run_id = self.run_call()
        original = self.store._event
        def fail(run, kind, *args):
            if kind == "call_result":
                raise sqlite3.OperationalError("synthetic disk write failure")
            return original(run, kind, *args)
        with patch.object(self.store, "_event", fail):
            with self.assertRaises(DurableStoreError):
                self.store.finish_call(run_id, "call-1", {"external": "known"}, document_edits=[self.edit()])
        self.assertIsNone(self.store.read_document("context-1", "plan"))
        self.assertEqual(self.store.get_call(run_id, "call-1")["status"], "intent")
        self.assertEqual(self.store.list_document_conflicts(run_id), [])
        self.assertEqual(self.store.read_document_events("context-1"), [])

    def test_retention_preserves_live_documents_and_delete_scrubs_all_new_private_rows(self):
        run_id = self.run_call()
        self.store.finish_call(run_id, "call-1", {}, document_edits=[self.edit()])
        self.store.transition(run_id, "complete", status="completed")
        self.assertEqual(self.store.compact(retain_terminal=0, max_age_days=0)["runs_pruned"], 1)
        self.assertEqual(self.store.read_document("context-1", "plan")["value"], {"items": ["synthetic"]})
        self.store.control("context-1", "delete")
        for table in ("documents", "document_events", "document_mutations", "document_conflicts", "review_requests", "review_resolutions"):
            self.assertEqual(self.store._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_process_crash_commits_both_document_and_result_or_neither(self):
        self.store.close()
        for committed in (False, True):
            root = self.root.parent / ("committed" if committed else "uncommitted")
            code = """import sys,time
from pathlib import Path
from helpers.durable.store import LocalStore
store=LocalStore(Path(sys.argv[1]))
run=store.admit('context-1','input-1',{}, {})
store.start_call(run['run_id'],'call-1','tool',{})
"""
            if not committed:
                code += """original=store._event
def park(*args,**kwargs):
    value=original(*args,**kwargs)
    print(run['run_id'],flush=True)
    time.sleep(300)
    return value
store._event=park
"""
            code += """store.finish_call(run['run_id'],'call-1',{'external':'known'},document_edits=[{'kind':'plan','schema_version':1,'expected_revision':0,'value':{'items':['saved']}}])
print(run['run_id'],flush=True)
time.sleep(300)
"""
            process = subprocess.Popen([sys.executable, "-u", "-c", code, str(root)], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(10))
                run_id = process.stdout.readline().strip()
                self.assertTrue(run_id)
                process.kill()
                process.wait(timeout=10)
                with LocalStore(root) as reopened:
                    self.assertEqual(reopened.get_call(run_id, "call-1")["status"], "completed" if committed else "intent")
                    document = reopened.read_document("context-1", "plan")
                    self.assertEqual(document["value"] if document else None, {"items": ["saved"]} if committed else None)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
