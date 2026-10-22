"""PostgreSQL custody for encrypted resources and append-only job receipts."""
from __future__ import annotations

import hashlib
import hmac
import re

from helpers.durable.store import ConflictError, IntegrityError, OwnershipError, _identity, _json, _digest

MAX_RESOURCE = 8 * 1024 * 1024
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")


class ResourceStore:
    def _initialize_resources(self):
        for statement in (
            """CREATE TABLE IF NOT EXISTS resource_objects(context_id TEXT NOT NULL,resource_id TEXT NOT NULL,
                metadata TEXT NOT NULL,body BYTEA NOT NULL,body_digest TEXT NOT NULL,created_at DOUBLE PRECISION NOT NULL,
                PRIMARY KEY(context_id,resource_id))""",
            """CREATE TABLE IF NOT EXISTS resource_manifests(context_id TEXT NOT NULL,kind TEXT NOT NULL,
                version BIGINT NOT NULL,value TEXT NOT NULL,digest TEXT NOT NULL,generation BIGINT NOT NULL,
                PRIMARY KEY(context_id,kind))""",
            """CREATE TABLE IF NOT EXISTS resource_jobs(job_id TEXT PRIMARY KEY,context_id TEXT NOT NULL,
                run_id TEXT NOT NULL REFERENCES runs(run_id),generation BIGINT NOT NULL,epoch TEXT NOT NULL,
                fingerprint TEXT NOT NULL,token_digest TEXT NOT NULL,status TEXT NOT NULL,result TEXT,result_digest TEXT)""",
        ):
            self._connection.execute(statement)

    def _resource_authorize(self, context_id, run_id=None, job_id=None, job_token=None):
        _identity(context_id, "resource context")
        self._document_context(context_id)  # Includes tombstone checks, even before first admission.
        if job_id:
            row = self._resource_job(job_id, job_token)
            if row["context_id"] != context_id or row["status"] != "submitted":
                raise OwnershipError("Resource job capability is unavailable")
        elif run_id:
            self.assert_owner(run_id)
            row = self._review_run(run_id)
            if row["context_id"] != context_id:
                raise OwnershipError("Resource does not belong to this run")
        # Unclaimed admission may publish immutable bytes, never manifests or execution.

    def put_resource(self, context_id, metadata, body, *, run_id=None, job_id=None, job_token=None):
        if (type(metadata) is not dict or set(metadata) != {"id", "kind", "name", "digest", "size"}
                or not _DIGEST.fullmatch(metadata.get("id", ""))
                or not _DIGEST.fullmatch(metadata.get("digest", ""))
                or type(metadata.get("size")) is not int or not 0 <= metadata["size"] <= MAX_RESOURCE
                or not isinstance(metadata.get("name"), str) or len(metadata["name"]) > 240
                or not isinstance(body, bytes) or not 0 < len(body) <= 2 * MAX_RESOURCE):
            raise ValueError("Invalid encrypted resource")
        _identity(metadata["kind"], "resource kind")
        encoded = _json(metadata)
        with self._transaction():
            self._resource_authorize(context_id, run_id, job_id, job_token)
            old = self._connection.execute("SELECT metadata FROM resource_objects WHERE context_id=? AND resource_id=?",
                                           (context_id, metadata["id"])).fetchone()
            if old and old["metadata"] != encoded:
                raise ConflictError("Resource identity changed")
            if old:
                self._connection.execute("UPDATE resource_objects SET created_at=? WHERE context_id=? AND resource_id=?", (self._now(), context_id, metadata["id"]))
            if not old:
                total = self._connection.execute("SELECT COALESCE(SUM(octet_length(body)),0) AS size FROM resource_objects WHERE context_id=?", (context_id,)).fetchone()["size"]
                if total + len(body) > 256 * 1024 * 1024:
                    raise ValueError("Context resource storage exceeds the 256 MiB encrypted quota")
                self._connection.execute("INSERT INTO resource_objects VALUES(?,?,?,?,?,?)",
                    (context_id, metadata["id"], encoded, body, hashlib.sha256(body).hexdigest(), self._now()))
            return metadata

    def get_resource(self, context_id, resource_id):
        _identity(context_id, "resource context")
        if not isinstance(resource_id, str) or not _DIGEST.fullmatch(resource_id):
            raise ValueError("Invalid resource identity")
        with self._snapshot():
            self._document_context(context_id)
            row = self._connection.execute("SELECT metadata,body,body_digest FROM resource_objects WHERE context_id=? AND resource_id=?",
                                           (context_id, resource_id)).fetchone()
            if row is None:
                raise KeyError("Resource is unavailable in this context")
            body = bytes(row["body"])
            if hashlib.sha256(body).hexdigest() != row["body_digest"]:
                raise IntegrityError("Encrypted resource integrity check failed")
            import json
            return {"metadata": json.loads(row["metadata"]), "body": body}

    def get_resource_manifest(self, context_id, kind):
        _identity(kind, "resource kind")
        with self._snapshot():
            self._document_context(context_id)
            row = self._connection.execute("SELECT * FROM resource_manifests WHERE context_id=? AND kind=?", (context_id, kind)).fetchone()
            if row is None or row["generation"] != self.document_generation(context_id):
                return None
            return {"version": row["version"], "value": self._read(row["value"], row["digest"], required=True)}

    def stage_resource(self, context_id, resource_id):
        with self._transaction():
            value = self.get_resource(context_id, resource_id)
            self._connection.execute("UPDATE resource_objects SET created_at=? WHERE context_id=? AND resource_id=?", (self._now(), context_id, resource_id))
            return value["metadata"]

    def _verify_resources(self, context_id, value):
        if isinstance(value, dict):
            if set(value) == {"id", "kind", "name", "digest", "size"}:
                if self.get_resource(context_id, value["id"])["metadata"] != value:
                    raise IntegrityError("Checkpoint resource reference changed")
            for child in value.values():
                self._verify_resources(context_id, child)
        elif isinstance(value, list):
            for child in value:
                self._verify_resources(context_id, child)

    def publish_resource_manifest(self, context_id, kind, value, expected_version, run_id):
        _identity(kind, "resource kind")
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("Invalid resource manifest version")
        encoded = _json(value)
        with self._transaction():
            if not run_id:
                raise OwnershipError("Resource publication requires a claimed run")
            self._resource_authorize(context_id, run_id)
            self._verify_resources(context_id, value)
            old = self.get_resource_manifest(context_id, kind)
            if (old["version"] if old else 0) != expected_version:
                raise ConflictError("Resource manifest changed")
            self._connection.execute("""INSERT INTO resource_manifests VALUES(?,?,?,?,?,?) ON CONFLICT(context_id,kind)
                DO UPDATE SET version=excluded.version,value=excluded.value,digest=excluded.digest,generation=excluded.generation""",
                (context_id, kind, expected_version + 1, self._encode(encoded), _digest(encoded), self.document_generation(context_id)))
            return self.get_resource_manifest(context_id, kind)

    def register_resource_job(self, run_id, job_id, fingerprint, token_digest):
        _identity(job_id, "job id")
        if not all(isinstance(item, str) and _DIGEST.fullmatch(item) for item in (fingerprint, token_digest)):
            raise ValueError("Invalid job fingerprint")
        with self._transaction():
            self.assert_owner(run_id)
            run = self._review_run(run_id)
            previous = self.get_resource_job(job_id)
            if previous:
                if previous["run_id"] != run_id or previous["fingerprint"] != fingerprint:
                    raise ConflictError("Job identity changed")
                return previous
            self._connection.execute("INSERT INTO resource_jobs VALUES(?,?,?,?,?,?,?,'submitted',NULL,NULL)",
                (job_id, run["context_id"], run_id, run["generation"], self.get_restore_state()["epoch"], fingerprint, token_digest))
            return self.get_resource_job(job_id)

    def get_resource_job(self, job_id):
        _identity(job_id, "job id")
        with self._snapshot():
            row = self._connection.execute("SELECT * FROM resource_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                return None
            self._document_context(row["context_id"])
            result = dict(row)
            result.pop("token_digest")
            if row["status"] not in ("submitted", "completed") or (row["status"] == "submitted" and (row["result"] is not None or row["result_digest"] is not None)):
                raise IntegrityError("Resource job status is invalid")
            result["result"] = self._read(row["result"], row["result_digest"], required=row["status"] == "completed")
            return result

    def _resource_job(self, job_id, token):
        row = self._connection.execute("SELECT * FROM resource_jobs WHERE job_id=?", (_identity(job_id, "job id"),)).fetchone()
        if (row is None or not isinstance(token, str) or len(token) > 200
                or not hmac.compare_digest(row["token_digest"], hashlib.sha256(token.encode()).hexdigest())
                or row["epoch"] != self.get_restore_state()["epoch"]
                or row["generation"] != self.document_generation(row["context_id"])):
            raise OwnershipError("Resource job capability is unavailable")
        self._document_context(row["context_id"])
        return row

    def finish_resource_job(self, job_id, token, result):
        encoded = _json(result)
        with self._transaction():
            row = self._resource_job(job_id, token)
            self._verify_resources(row["context_id"], result)
            if row["status"] == "completed":
                if row["result_digest"] != _digest(encoded):
                    raise ConflictError("Completed job result changed")
            else:
                self._connection.execute("UPDATE resource_jobs SET status='completed',result=?,result_digest=? WHERE job_id=?",
                                         (self._encode(encoded), _digest(encoded), job_id))
            return self.get_resource_job(job_id)

    def _delete_resources(self, context_id):
        for table in ("resource_jobs", "resource_manifests", "resource_objects"):
            self._connection.execute(f"DELETE FROM {table} WHERE context_id=?", (context_id,))

    def collect_resources(self, grace_seconds=86400):
        """Reachability includes retained runs, current heads, sessions and jobs.

        An admission can publish bytes before its run, so unreferenced objects
        have a one-day grace period. Corrupt roots abort collection, preserving
        evidence rather than guessing which private bytes are disposable.
        """
        reachable = set()
        def visit(value):
            if isinstance(value, dict):
                resource_id = value.get("id")
                if isinstance(resource_id, str) and _DIGEST.fullmatch(resource_id):
                    reachable.add(resource_id)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
            elif isinstance(value, str):
                reachable.update(re.findall(r"a0-resource://([a-f0-9]{64})", value))
        with self._transaction():
            for row in self._connection.execute("SELECT run_id FROM runs WHERE payloads_pruned=0"):
                self.get_run(row["run_id"])
            for row in self._connection.execute("SELECT payload,payload_digest FROM events WHERE payloads_pruned=0"):
                self._read(row["payload"], row["payload_digest"], required=True)
            for table, columns in (
                ("runs", (("input_payload", "input_digest"), ("checkpoint", "checkpoint_digest"))),
                ("context_heads", (("checkpoint", "digest"),)), ("events", (("payload", "payload_digest"),)),
                ("documents", (("value", "digest"),)), ("document_conflicts", (("proposed", "digest"),)),
                ("projections", (("value", "digest"),)), ("resource_manifests", (("value", "digest"),)),
                ("resource_jobs", (("result", "result_digest"),)),
            ):
                for column, digest in columns:
                    for row in self._connection.execute(f"SELECT {column} AS value,{digest} AS digest FROM {table} WHERE {column} IS NOT NULL"):
                        visit(self._read(row["value"], row["digest"], required=True))
            for row in self._connection.execute("SELECT run_id,call_id FROM calls WHERE payloads_pruned=0"):
                call = self._call(row["run_id"], row["call_id"])
                visit(call["payload"])
                visit(call["result"])
            for row in self._connection.execute("SELECT * FROM commands WHERE payloads_pruned=0"):
                command = self._command(row)
                visit(command["payload"])
                visit(command["result"])
            for row in self._connection.execute("SELECT job_id FROM resource_jobs"):
                visit(self.get_resource_job(row["job_id"])["result"])
            count = 0
            for row in self._connection.execute("SELECT context_id,resource_id FROM resource_objects WHERE created_at<?", (self._now() - grace_seconds,)).fetchall():
                if row["resource_id"] not in reachable:
                    count += self._connection.execute("DELETE FROM resource_objects WHERE context_id=? AND resource_id=?", (row["context_id"], row["resource_id"])).rowcount
            return {"resources_removed": count}
