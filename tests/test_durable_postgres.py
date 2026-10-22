"""Shared PostgreSQL contract tests; opt in only with a disposable test DSN."""
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

from helpers.durable.postgres import PostgresStore
from helpers.durable.store import ConflictError, DurableStoreError, IntegrityError, OwnershipError, StaleRunError


DSN = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")


@unittest.skipUnless(DSN, "Disposable A0_TEST_DURABILITY_POSTGRES_DSN is required")
class DurablePostgresTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.pg = psycopg
        self.namespace = "a0_test_" + uuid.uuid4().hex
        self.stores = []
        self.first = self.store("first")
        self.second = self.store("second")

    def tearDown(self):
        for store in self.stores:
            store.close()
        from psycopg import sql
        with self.pg.connect(DSN, autocommit=True) as cleanup:
            cleanup.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.namespace)))

    def store(self, worker):
        store = PostgresStore(DSN, namespace=self.namespace, worker_id=worker)
        self.stores.append(store)
        return store

    def admit(self, context="context", input_id="input", checkpoint=None):
        return self.first.admit(context, input_id, {"text": "synthetic"}, checkpoint or {"paused": False})

    def test_claims_are_exclusive_live_and_fenced_across_connections(self):
        run = self.admit()
        run_id = run["run_id"]
        self.assertTrue(self.first.claim(run_id))
        self.assertTrue(self.first.claim(run_id))
        fence = self.first.ownership(run_id)["fence"]
        self.assertFalse(self.second.claim(run_id))
        self.assertFalse(self.second.owns(run_id))
        with self.assertRaises(OwnershipError):
            self.second.start_call(run_id, "effect", "tool", {})
        self.assertTrue(self.second.ownership(run_id)["claimed"])
        self.first.release(run_id)
        self.first.release(run_id)
        self.assertTrue(self.second.claim(run_id))
        self.assertGreater(self.second.ownership(run_id)["fence"], fence)
        with self.assertRaises(OwnershipError):
            self.first.transition(run_id, "tools", {})

    def test_connection_loss_releases_claim_but_old_worker_never_reconnects(self):
        run_id = self.admit()["run_id"]
        self.first.claim(run_id)
        self.first.start_call(run_id, "effect", "tool", {"external": True})
        with self.pg.connect(DSN, autocommit=True) as killer:
            killer.execute("SELECT pg_terminate_backend(%s)", (self.first._backend_pid,))
        with self.assertRaises(DurableStoreError):
            self.first.finish_call(run_id, "effect", {"done": True})
        self.assertTrue(self.second.claim(run_id))
        self.assertEqual(self.second.get_call(run_id, "effect")["status"], "intent")
        with self.assertRaises(DurableStoreError):
            self.first.get_run(run_id)

    def test_cancel_preserves_late_outcome_but_successor_waits_for_old_context_owner(self):
        run_id = self.admit()["run_id"]
        self.first.claim(run_id)
        self.first.start_call(run_id, "effect", "tool", {})
        self.second.control("context", "cancel")
        self.first.finish_call(run_id, "effect", {"known": True})
        successor = self.second.admit("context", "next", {}, {})
        self.assertFalse(self.second.claim(successor["run_id"]))
        self.first.release(run_id)
        self.assertTrue(self.second.claim(successor["run_id"]))
        reset = self.second.control_request("context", "reset", "reset-request")
        with self.assertRaises(StaleRunError):
            self.second.start_call(successor["run_id"], "new-effect", "tool", {})
        self.second.release(successor["run_id"])
        newest = self.second.admit("context", "newest", {}, {})
        self.assertTrue(self.second.claim(newest["run_id"]))
        self.assertEqual(self.first.control_request("context", "reset", "reset-request"), reset)
        self.assertEqual(self.second.get_run(newest["run_id"])["status"], "running")
        self.second.start_call(newest["run_id"], "newest-effect", "tool", {})
        with self.assertRaises(ConflictError):
            self.first.control_request("context", "cancel", "reset-request")

    def test_blobs_results_documents_and_conflicts_share_database_transactions(self):
        large = {"text": "synthetic" * 10000}
        run = self.first.admit("context", "input", large, large)
        run_id = run["run_id"]
        self.first.claim(run_id)
        self.first.start_call(run_id, "model", "model", large)
        self.first.finish_call(run_id, "model", large, checkpoint=large, phase="model_result")
        self.assertEqual(self.second.get_run(run_id)["checkpoint"], large)
        self.assertEqual(self.second.get_call(run_id, "model")["result"], large)
        self.first.write_document("context", "todo", 1, {"current": True}, 0, "app")
        self.first.start_call(run_id, "tool", "tool", {})
        body = {"actual_external_result": "retained"}
        call = self.first.finish_call(run_id, "tool", body, document_edits=[
            {"kind": "todo", "schema_version": 1, "expected_revision": 0, "value": {"proposed": True}}])
        self.assertEqual(call["result"], body)
        self.assertEqual(len(self.second.list_document_conflicts(run_id)), 1)
        self.assertEqual(self.second.read_document("context", "todo")["value"], {"current": True})
        self.first._connection.execute("UPDATE blobs SET data=?", (b"bad",))
        with self.assertRaises(IntegrityError):
            self.second.get_run(run_id)

    def test_rollback_and_idempotency_preserve_business_contracts(self):
        with patch.object(self.first, "_event", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                self.admit()
        self.assertEqual(self.second.list_run_headers(), [])
        run = self.admit()
        self.assertEqual(self.second.admit("context", "input", {"text": "synthetic"}, {})["run_id"], run["run_id"])
        with self.assertRaises(ConflictError):
            self.second.admit("context", "input", {}, {})
        self.assertEqual(self.second.read_events(run["run_id"])[0]["kind"], "admitted")

    def test_command_application_and_ack_are_atomic_and_idempotent(self):
        run_id = self.admit()["run_id"]
        self.first.claim(run_id)
        receipt = self.second.enqueue_command(run_id, "pause", {"paused": True}, "request")
        self.assertEqual(receipt["status"], "pending")
        self.assertEqual(len(self.first.pending_commands(run_id)), 1)
        with patch.object(self.first, "_event", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                self.first.apply_command(run_id, "request", checkpoint={"paused": True}, phase="tools")
        self.assertEqual(self.second.get_command(run_id, "request")["status"], "pending")
        result = self.first.apply_command(run_id, "request", checkpoint={"paused": True}, phase="tools", result={"accepted": True})
        self.assertEqual(result["status"], "applied")
        self.first.apply_command(run_id, "request", checkpoint={"paused": False}, phase="wrong", result={"accepted": False})
        self.assertEqual(self.second.get_run(run_id)["checkpoint"], {"paused": True})
        self.assertEqual(self.second.get_command(run_id, "request")["result"], {"accepted": True})
        self.assertEqual(self.second.enqueue_command(run_id, "pause", {"paused": True}, "request")["status"], "applied")
        with self.assertRaises(ConflictError):
            self.second.enqueue_command(run_id, "pause", {"paused": False}, "request")
        self.first._connection.execute("UPDATE commands SET result_digest=NULL WHERE request_id='request'")
        with self.assertRaises(IntegrityError):
            self.second.get_command(run_id, "request")

    def test_shared_projection_cas_claim_fencing_and_delete(self):
        self.assertEqual(self.first.put_projection("chat:context", {"before_admission": True}, 0)["version"], 1)
        run_id = self.admit()["run_id"]
        self.first.claim(run_id)
        self.first.put_projection("chat:context", {"owned": True}, 1)
        with self.assertRaises(OwnershipError):
            self.second.put_projection("chat:context", {"stale": True}, 2)
        with self.assertRaises(ConflictError):
            self.first.put_projection("chat:context", {}, 0)
        self.second.control("context", "delete")
        self.assertIsNone(self.first.get_projection("chat:context"))
        with self.assertRaises(StaleRunError):
            self.first.put_projection("chat:context", {"resurrect": True}, 0)

    def test_roles_and_restore_hold_cannot_take_over_live_workers(self):
        run_id = self.admit()["run_id"]
        self.first.enqueue_command(run_id, "pause", {"paused": True}, "old-command")
        self.first.claim(run_id)
        with self.assertRaises(OwnershipError):
            self.second.begin_restore_review()
        self.first.release(run_id)
        self.assertTrue(self.first.try_role("scheduler"))
        self.assertTrue(self.first.try_role("scheduler"))
        self.assertFalse(self.second.try_role("scheduler"))
        with self.assertRaises(OwnershipError):
            self.second.begin_restore_review()
        self.first.release_role("scheduler")
        state = self.second.begin_restore_review()
        self.assertTrue(state["required"])
        self.assertFalse(self.first.can_resume(run_id))
        self.assertFalse(self.first.claim(run_id))
        self.assertEqual(self.first.pending_commands(run_id), [])
        self.assertFalse(self.first.get_command(run_id, "old-command")["epoch_valid"])
        with self.assertRaises(ConflictError):
            self.first.enqueue_command(run_id, "pause", {"paused": True}, "old-command")
        self.first.select_restore([run_id], state["epoch"], {run_id: self.first.get_review(run_id)["version"]}, "select")
        self.assertTrue(self.first.claim(run_id))
        with self.assertRaises(ConflictError):
            self.first.ack_command(run_id, "old-command")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DurableStoreError):
                self.first.backup(directory + "/misleading.sqlite3")

    def test_terminal_compaction_preserves_command_retry_identity_and_reclaims_blobs(self):
        run_id = self.admit()["run_id"]
        self.first.claim(run_id)
        payload = {"text": "synthetic" * 10000}
        self.second.enqueue_command(run_id, "intervention", payload, "request")
        self.first.ack_command(run_id, "request", result={"accepted": True})
        self.first.transition(run_id, "completed", status="completed")
        # A fast requester clock must not expire another host's fresh result.
        with patch("helpers.durable.store.time.time", return_value=10**12):
            self.assertEqual(self.second.compact(retain_terminal=100, max_age_days=30)["runs_pruned"], 0)
        result = self.second.compact(retain_terminal=0)
        self.assertEqual(result["runs_pruned"], 1)
        self.assertEqual(self.first._connection.execute("SELECT COUNT(*) FROM blobs").fetchone()[0], 0)
        receipt = self.second.enqueue_command(run_id, "intervention", payload, "request")
        self.assertTrue(receipt["payloads_pruned"])
        self.assertEqual(receipt["status"], "applied")
        with self.assertRaises(ConflictError):
            self.second.enqueue_command(run_id, "intervention", {}, "request")


if __name__ == "__main__":
    unittest.main()
