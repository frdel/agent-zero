"""Versioned operator evidence, bounded retries and selected backup restoration."""
from pathlib import Path
import hashlib
import selectors
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from helpers.durable.store import ConflictError, DurableStoreError, LocalStore, StaleRunError


class DurableReviewStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve() / "store"
        self.store = LocalStore(self.root)
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.store.close)

    def admit(self, context="context-1", input_id="input-1"):
        return self.store.admit(context, input_id, {}, {"paused": True, "schema": 1})

    def token(self, run_id):
        return self.store.get_review(run_id)["version"]

    def unresolved(self, kind="model", eligible=True):
        run = self.admit()
        self.store.start_call(run["run_id"], "call-1", kind, {"retry_eligible": eligible, "request": "synthetic"})
        self.store.transition(run["run_id"], "needs_attention", status="attention")
        return run["run_id"]

    def test_review_token_changes_with_controls_documents_and_new_context_owner(self):
        run_id = self.admit()["run_id"]
        token = self.token(run_id)
        self.store.write_document("context-1", "plan", 1, {}, 0, "app")
        self.assertNotEqual(self.token(run_id), token)
        with self.assertRaises(ConflictError):
            self.store.record_resolution(run_id, token, "stop", "evidence", "old-review")
        self.store.control("context-1", "cancel")
        stopped = self.token(run_id)
        newer = self.admit(input_id="input-2")
        self.assertNotEqual(self.token(run_id), stopped)
        with self.assertRaises(StaleRunError):
            self.store.record_resolution(run_id, self.token(run_id), "stop", "stale owner", "old-owner")
        self.assertEqual(self.store.get_run(newer["run_id"])["status"], "running")
        self.store.control("context-1", "reset")
        with self.assertRaises(StaleRunError):
            self.store.record_resolution(run_id, self.token(run_id), "stop", "old generation", "old-generation")

    def test_confirmation_records_evidence_and_stops_without_inventing_a_result(self):
        run_id = self.unresolved()
        token = self.token(run_id)
        receipt = self.store.record_resolution(run_id, token, "confirmed_completed", "Operator verified target receipt.", "review-1", "call-1")
        self.assertEqual(self.store.get_run(run_id)["status"], "cancelled")
        call = self.store.get_call(run_id, "call-1")
        self.assertEqual(call["status"], "intent")
        self.assertIsNone(call["result"])
        self.assertEqual(self.store.list_resolutions(run_id)[0]["note"], "Operator verified target receipt.")
        self.assertEqual(self.store.record_resolution(run_id, token, "confirmed_completed", "Operator verified target receipt.", "review-1", "call-1"), receipt)
        with self.assertRaises(ConflictError):
            self.store.record_resolution(run_id, token, "confirmed_not_completed", "changed", "review-1", "call-1")
        request = self.store.get_review_request(run_id, "review-1")
        self.assertEqual(request["decision"], "confirmed_completed")
        self.assertEqual(request["call_id"], "call-1")
        self.assertEqual(request["result"], receipt)

    def test_resume_atomically_clears_pause_and_advances_watermark_but_never_revives_terminal(self):
        run_id = self.admit()["run_id"]
        self.store.transition(run_id, "held", status="blocked")
        token = self.token(run_id)
        receipt = self.store.record_resolution(run_id, token, "resume", "Reviewed compatible phase", "resume-1", phase="iteration_ready")
        run = self.store.get_run(run_id)
        self.assertFalse(run["checkpoint"]["paused"])
        self.assertEqual((run["status"], run["phase"]), ("running", "iteration_ready"))
        self.assertEqual(run["checkpoint_seq"], self.store.read_events(run_id)[-1]["seq"])
        self.assertEqual(self.store.read_events(run_id)[-1]["payload"]["phase"], "iteration_ready")
        self.assertEqual(self.store.record_resolution(run_id, token, "resume", "Reviewed compatible phase", "resume-1", phase="iteration_ready"), receipt)
        self.store.control("context-1", "cancel")
        with self.assertRaises(StaleRunError):
            self.store.record_resolution(run_id, self.token(run_id), "resume", "Stopped", "resume-stopped", phase="iteration_ready")

    def test_operator_stop_and_descendant_stop_roll_back_as_one_transaction(self):
        parent = self.admit()
        child = self.admit("child-context", "child-input")
        original = self.store._event
        def fail(run_id, *args):
            if run_id == child["run_id"]:
                raise sqlite3.OperationalError("synthetic descendant write failure")
            return original(run_id, *args)
        token = self.token(parent["run_id"])
        with patch.object(self.store, "_event", fail):
            with self.assertRaises(DurableStoreError):
                self.store.record_resolution(parent["run_id"], token, "stop", "Stop family", "stop-family", context_ids=[child["context_id"]])
        self.assertEqual(self.store.get_run(parent["run_id"])["status"], "running")
        self.assertEqual(self.store.get_run(child["run_id"])["status"], "running")
        self.assertEqual(self.store.list_resolutions(parent["run_id"]), [])
        self.store.record_resolution(parent["run_id"], token, "stop", "Stop family", "stop-family", context_ids=[child["context_id"]])
        self.assertEqual(self.store.get_run(child["run_id"])["status"], "cancelled")

    def test_retry_grants_are_single_use_aliases_bounded_to_three_total_attempts(self):
        run_id = self.unresolved()
        original = self.store.get_call(run_id, "call-1")
        token = self.token(run_id)
        grant = self.store.prepare_retry(run_id, "call-1", token, "retry-2", "model_retry", eligible=True, note="Approved possible extra cost")
        self.assertEqual((grant["attempt"], grant["state"]), (2, "pending"))
        self.assertFalse(self.store.get_run(run_id)["checkpoint"]["paused"])
        alias = self.store.begin_retry(run_id, "call-1")
        self.assertEqual(alias["call_id"], "call-1:attempt:2")
        self.assertEqual(alias["original_id"], "call-1")
        self.assertEqual(alias["payload"], original["payload"])
        self.assertEqual(self.store.get_call(run_id, "call-1"), original)
        with self.assertRaises(StaleRunError):
            self.store.begin_retry(run_id, "call-1")
        self.assertEqual(self.store.prepare_retry(run_id, "call-1", token, "retry-2", "model_retry", eligible=True, note="Approved possible extra cost"), grant)
        with self.assertRaises(ConflictError):
            self.store.prepare_retry(run_id, "call-1", token, "retry-2", "model_retry", eligible=True, note="Different evidence")
        self.store.prepare_retry(run_id, "call-1", self.token(run_id), "retry-3", "model_retry", eligible=True)
        self.assertEqual(self.store.begin_retry(run_id, "call-1")["attempt"], 3)
        with self.assertRaises(ConflictError):
            self.store.prepare_retry(run_id, "call-1", self.token(run_id), "retry-4", "model_retry", eligible=True)

    def test_retry_rejects_missing_eligibility_effectful_models_or_known_outcomes(self):
        run_id = self.unresolved(eligible=False)
        with self.assertRaises(StaleRunError):
            self.store.prepare_retry(run_id, "call-1", self.token(run_id), "no-grant", "model_retry")
        with self.assertRaises(StaleRunError):
            self.store.prepare_retry(run_id, "call-1", self.token(run_id), "effectful", "model_retry", eligible=True)
        self.store.finish_call(run_id, "call-1", {"known": True})
        with self.assertRaises(ConflictError):
            self.store.prepare_retry(run_id, "call-1", self.token(run_id), "known", "model_retry", eligible=True)

    def test_completed_alias_cannot_be_retried_and_request_receipt_is_still_idempotent(self):
        run_id = self.unresolved(kind="tool")
        token = self.token(run_id)
        grant = self.store.prepare_retry(run_id, "call-1", token, "retry", "tools", eligible=True)
        alias = self.store.begin_retry(run_id, "call-1")
        self.store.finish_call(run_id, alias["call_id"], {"body": "known"})
        with self.assertRaises(ConflictError):
            self.store.prepare_retry(run_id, "call-1", self.token(run_id), "unnecessary", "tools", eligible=True)
        request = self.store.get_review_request(run_id, "retry")
        self.assertEqual(request["result"], grant)
        self.assertEqual(request["decision"], "new_attempt")
        self.assertEqual(self.store.get_retry(run_id, "call-1")["state"], "started")

    def test_backup_rotates_epoch_invalidates_old_grants_and_requires_per_run_selection(self):
        run_id = self.unresolved()
        self.store.prepare_retry(run_id, "call-1", self.token(run_id), "retry", "model_retry", eligible=True)
        source_epoch = self.store.get_restore_state()["epoch"]
        destination = self.root.parent / "restored"
        destination.mkdir()
        self.store.backup(destination / "state.sqlite3")
        with LocalStore(destination) as restored:
            state = restored.get_restore_state()
            self.assertTrue(state["required"])
            self.assertNotEqual(state["epoch"], source_epoch)
            self.assertFalse(restored.can_resume(run_id))
            self.assertFalse(restored.get_retry(run_id, "call-1")["epoch_valid"])
            with self.assertRaises(StaleRunError):
                restored.begin_retry(run_id, "call-1")
            token = restored.get_review(run_id)["version"]
            selection = restored.select_restore([run_id], state["epoch"], {run_id: token}, "select")
            self.assertTrue(restored.can_resume(run_id))
            self.assertEqual(restored.select_restore([run_id], state["epoch"], {run_id: token}, "select"), selection)
            new_grant = restored.prepare_retry(run_id, "call-1", restored.get_review(run_id)["version"], "new-epoch-retry", "model_retry", eligible=True)
            self.assertEqual(new_grant["attempt"], 2)  # an unused old grant did not execute
            self.assertEqual(restored.begin_retry(run_id, "call-1")["attempt"], 2)
            fresh = restored.admit("new-context", "new-input", {}, {})
            self.assertTrue(restored.can_resume(fresh["run_id"]))
            nested = self.root.parent / "another-backup.sqlite3"
            restored.backup(nested)
        third = self.root.parent / "third"
        third.mkdir()
        shutil.copyfile(nested, third / "state.sqlite3")
        with LocalStore(third) as another:
            self.assertFalse(another.can_resume(run_id))
            self.assertFalse(another.can_resume(fresh["run_id"]))
            self.assertNotEqual(another.get_restore_state()["epoch"], state["epoch"])

    def test_restore_selection_validates_all_versions_before_any_run_is_selected(self):
        first = self.admit()
        second = self.admit("context-2", "input-2")
        destination = self.root.parent / "restore"
        destination.mkdir()
        self.store.backup(destination / "state.sqlite3")
        with LocalStore(destination) as restored:
            versions = {run["run_id"]: restored.get_review(run["run_id"])["version"] for run in (first, second)}
            versions[second["run_id"]] = "stale"
            state = restored.get_restore_state()
            with self.assertRaises(ConflictError):
                restored.select_restore(list(versions), state["epoch"], versions, "select")
            self.assertFalse(restored.can_resume(first["run_id"]))
            self.assertFalse(restored.can_resume(second["run_id"]))
            with self.assertRaises(ConflictError):
                restored.select_restore([first["run_id"]], "old-epoch", {first["run_id"]: versions[first["run_id"]]}, "old")

    def test_context_delete_removes_shared_restore_selection_receipt(self):
        run_id = self.admit()["run_id"]
        state = self.store.get_restore_state()
        self.store.select_restore([run_id], state["epoch"], {run_id: self.token(run_id)}, "selection")
        self.assertIsNotNone(self.store.get_review_request(run_id, "selection"))
        self.store.control("context-1", "delete")
        self.assertIsNone(self.store.get_review_request(run_id, "selection"))
        self.assertEqual(self.store._connection.execute("SELECT COUNT(*) FROM restore_selections").fetchone()[0], 0)

    def test_documents_survive_single_file_backup_and_context_delete_scrubs_review_evidence(self):
        # Exactly 64 KiB canonical JSON exercises a file-backed document as well.
        value = "x" * (64 * 1024 - 2)
        self.store.write_document("context-1", "plan", 1, value, 0, "app")
        run_id = self.unresolved()
        self.store.record_resolution(run_id, self.token(run_id), "confirmed_not_completed", "PRIVATE_OPERATOR_NOTE", "evidence", "call-1")
        restored_root = self.root.parent / "restored"
        restored_root.mkdir()
        self.store.backup(restored_root / "state.sqlite3")
        with LocalStore(restored_root) as restored:
            self.assertEqual(restored.read_document("context-1", "plan")["value"], value)
        self.store.control("context-1", "delete")
        self.assertEqual(self.store.list_resolutions(run_id), [])
        self.assertIsNone(self.store.get_review_request(run_id, "evidence"))
        for path in self.root.iterdir():
            if path.is_file():
                self.assertNotIn(b"PRIVATE_OPERATOR_NOTE", path.read_bytes())

    def test_compacted_review_keeps_idempotency_without_retaining_note_or_stopping_new_work(self):
        run_id = self.admit()["run_id"]
        token, note = self.token(run_id), "PRIVATE_REVIEW_NOTE_754e"
        receipt = self.store.record_resolution(run_id, token, "stop", note, "review")
        self.assertEqual(self.store.compact(retain_terminal=0, max_age_days=0)["runs_pruned"], 1)
        request = self.store.get_review_request(run_id, "review")
        self.assertEqual(request["decision"], "stop")
        self.assertEqual(request["expected_version"], token)
        self.assertIsNone(request["note"])
        self.assertEqual(request["note_digest"], hashlib.sha256(note.encode()).hexdigest())
        self.assertEqual(request["result"], receipt)
        self.assertIsNone(self.store.list_resolutions(run_id)[0]["note"])
        newer = self.admit(input_id="input-2")
        self.assertEqual(self.store.record_resolution(run_id, token, "stop", note, "review"), receipt)
        self.assertEqual(self.store.get_run(newer["run_id"])["status"], "running")
        with self.assertRaises(ConflictError):
            self.store.record_resolution(run_id, token, "stop", "changed", "review")
        for path in self.root.iterdir():
            if path.is_file():
                self.assertNotIn(note.encode(), path.read_bytes())

    def test_schema_three_migration_preserves_existing_blob_and_call(self):
        run = self.admit()
        self.store.start_call(run["run_id"], "call-1", "tool", {"synthetic": "x" * 70000})
        for table in ("documents", "document_events", "document_mutations", "document_conflicts", "review_requests", "review_resolutions", "restore_selections", "retry_grants"):
            self.store._connection.execute(f"DROP TABLE {table}")
        for column in ("document_edits_digest", "logical_call_id", "attempt"):
            self.store._connection.execute(f"ALTER TABLE calls DROP COLUMN {column}")
        self.store._connection.execute("PRAGMA user_version=3")
        self.store.close()
        with LocalStore(self.root) as migrated:
            self.assertEqual(migrated.get_run(run["run_id"]), run)
            self.assertEqual(migrated.get_call(run["run_id"], "call-1")["payload"], {"synthetic": "x" * 70000})
            self.assertTrue(migrated.can_resume(run["run_id"]))

    def test_process_kill_during_or_after_restore_selection_commits_all_or_none(self):
        first = self.admit()
        second = self.admit("context-2", "input-2")
        for committed in (False, True):
            root = self.root.parent / ("selected" if committed else "unselected")
            root.mkdir()
            self.store.backup(root / "state.sqlite3")
            code = """import sys,time
from pathlib import Path
from helpers.durable.store import LocalStore
store=LocalStore(Path(sys.argv[1]))
runs=store.list_run_headers()
versions={run['run_id']:store.get_review(run['run_id'])['version'] for run in runs}
"""
            if not committed:
                code += """original=store._event
def park(*args,**kwargs):
    value=original(*args,**kwargs)
    print('barrier',flush=True)
    time.sleep(300)
    return value
store._event=park
"""
            code += """store.select_restore(list(versions),store.get_restore_state()['epoch'],versions,'selection')
print('barrier',flush=True)
time.sleep(300)
"""
            process = subprocess.Popen([sys.executable, "-u", "-c", code, str(root)], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(10))
                self.assertEqual(process.stdout.readline().strip(), "barrier")
                process.kill()
                process.wait(timeout=10)
                with LocalStore(root) as reopened:
                    self.assertEqual(reopened.can_resume(first["run_id"]), committed)
                    self.assertEqual(reopened.can_resume(second["run_id"]), committed)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
