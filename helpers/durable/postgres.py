"""Shared PostgreSQL recovery storage with pinned-session execution ownership.

The existing LocalStore business operations retain their strict JSON/digest,
generation, CAS, idempotency and review rules. This adapter translates their
small, internal SQL dialect; it is not a general SQLite compatibility layer.
Short write transactions share an advisory mutex, preserving BEGIN IMMEDIATE
semantics while independently claimed contexts execute concurrently. Reads use
repeatable snapshots. Blob bytes live in the same database transaction as their
references. There is no local authoritative state and no automatic reconnect.

Claims are session locks, not expiring leases. Losing a session fences subsequent
journal writes, but cannot retract an external request already sent. Recovery
must still hold unresolved effects according to the normal replay policy.
Direct/session-pooled PostgreSQL connections are required; transaction pooling
cannot preserve session ownership. Database WAL/backups retain their own custody
and deletion policies; SQL deletion is not a physical secure-erase promise.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
import re
import threading
import uuid

from helpers.durable.store import (
    LocalStore, DurableStoreError, OwnershipError, IntegrityError, ConflictError,
    StaleRunError, _ACTIVE, _MAX_JSON, _BLOB_THRESHOLD, _BLOB_PREFIX,
    _identity, _json, _digest,
)
from helpers.durable.resource_store import ResourceStore


class _Row(dict):
    """Match the mapping/index access used by LocalStore's sqlite3.Row calls."""
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class _Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def fetchone(self):
        row = self.cursor.fetchone()
        return None if row is None else _Row(row)

    def fetchall(self):
        return [_Row(row) for row in self.cursor.fetchall()]

    def __iter__(self):
        return (_Row(row) for row in self.cursor)


class _Connection:
    def __init__(self, connection):
        self.driver = connection

    @staticmethod
    def sql(statement, parameters):
        statement = statement.replace("instr(", "strpos(")
        if statement.startswith("INSERT OR IGNORE INTO "):
            statement = statement.replace("INSERT OR IGNORE INTO ", "INSERT INTO ", 1) + " ON CONFLICT DO NOTHING"
        elif statement.startswith("INSERT OR REPLACE INTO restore_selections"):
            statement = statement.replace("INSERT OR REPLACE INTO ", "INSERT INTO ", 1)
            statement += " ON CONFLICT(run_id) DO UPDATE SET epoch=excluded.epoch,request_id=excluded.request_id,selected_at=excluded.selected_at"
        elif "INSERT OR REPLACE" in statement:
            raise IntegrityError("Unsupported PostgreSQL recovery SQL")
        # All statements are static, repository-owned SQL. Literal percent signs
        # must be escaped only when psycopg is also binding parameters.
        return statement if parameters is None else statement.replace("%", "%%").replace("?", "%s")

    def execute(self, statement, parameters=None):
        return _Cursor(self.driver.execute(self.sql(statement, parameters), parameters))

    def close(self):
        self.driver.close()


def _lock_key(namespace, kind, identity=""):
    encoded = f"agent-zero-durable:{namespace}:{kind}:{identity}".encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big", signed=True)


class PostgresStore(ResourceStore, LocalStore):
    distributed = True

    def __init__(self, dsn, *, namespace="agent_zero", worker_id=None):
        if not isinstance(namespace, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,62}", namespace) is None:
            raise ValueError("Invalid PostgreSQL recovery namespace")
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("PostgreSQL recovery DSN is required")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise DurableStoreError("PostgreSQL recovery requires psycopg") from exc
        self._pg = psycopg
        self._mutex = threading.RLock()
        self._pid = os.getpid()
        self._connection = None
        self._lock_file = None
        self._failed = False
        self._depth = 0
        self._read_only = False
        self._ready = False
        self.namespace = namespace
        self.worker_id = _identity(worker_id or uuid.uuid4().hex, "worker id")
        self._claims = {}
        self._roles = set()
        self._writer_key = _lock_key(namespace, "writer")
        try:
            driver = psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=10)
            self._connection = _Connection(driver)
            self._connection.execute("SET synchronous_commit=on")
            durability = self._connection.execute("SELECT current_setting('fsync') AS fsync,current_setting('full_page_writes') AS full_page_writes").fetchone()
            if durability["fsync"] != "on" or durability["full_page_writes"] != "on":
                raise IntegrityError("PostgreSQL recovery requires fsync and full_page_writes")
            identity = self._connection.execute("SELECT pg_backend_pid() AS pid,backend_start::text AS started FROM pg_stat_activity WHERE pid=pg_backend_pid()").fetchone()
            self._backend_pid, self._backend_started = identity["pid"], identity["started"]
            self._initialize()
            self._ready = True
        except Exception as exc:
            self.close()
            if isinstance(exc, (DurableStoreError, ValueError)):
                raise
            raise DurableStoreError("Cannot open PostgreSQL recovery database") from exc

    def _now(self):
        # Workers may have different wall clocks. Retention and shared audit
        # timestamps use the database clock; journal sequences own ordering.
        with self._snapshot():
            return float(self._connection.execute("SELECT EXTRACT(EPOCH FROM clock_timestamp()) AS value").fetchone()["value"])

    def _ensure_open(self):
        if os.getpid() != self._pid:
            raise OwnershipError("Recovery store must not be reused after fork")
        if self._failed or self._connection is None or self._connection.driver.closed:
            raise DurableStoreError("PostgreSQL recovery connection is unavailable; create a new worker")

    def _check_files(self):
        self._ensure_open()

    def _rollback(self):
        try:
            self._connection.driver.rollback()
        except Exception:
            self._failed = True

    def _database_failure(self, exc):
        if self._connection.driver.closed or (getattr(exc, "sqlstate", "") or "").startswith("08"):
            self._failed = True
        return DurableStoreError("PostgreSQL recovery transaction failed")

    @contextmanager
    def _transaction(self):
        with self._mutex:
            self._ensure_open()
            if self._depth:
                if self._read_only:
                    raise DurableStoreError("Recovery mutation attempted inside a read snapshot")
                yield
                return
            self._depth, self._read_only = 1, False
            claims_before, roles_before = dict(self._claims), set(self._roles)
            try:
                self._connection.execute("BEGIN")
                self._connection.execute("SELECT pg_advisory_xact_lock(?)", (self._writer_key,))
                if self._ready:
                    row = self._connection.execute("SELECT value FROM backend_metadata WHERE key='protocol'").fetchone()
                    if row is None or row["value"] != "3":
                        raise IntegrityError("Unsupported PostgreSQL recovery protocol")
                yield
                self._connection.execute("COMMIT")
            except self._pg.Error as exc:
                self._rollback()
                self._restore_session_state(claims_before, roles_before)
                raise self._database_failure(exc) from exc
            except BaseException:
                self._rollback()
                self._restore_session_state(claims_before, roles_before)
                raise
            finally:
                self._depth, self._read_only = 0, False

    def _restore_session_state(self, claims, roles):
        # Session advisory locks survive transaction rollback. Release locks
        # acquired by a failed claim/role transaction; do not resurrect locks
        # already explicitly released by a transaction with an uncertain commit.
        try:
            for run_id in self._claims.keys() - claims.keys():
                self._connection.execute("SELECT pg_advisory_unlock(?)", (self._claims[run_id]["key"],))
            for name in self._roles - roles:
                self._connection.execute("SELECT pg_advisory_unlock(?)", (_lock_key(self.namespace, "role", name),))
        except Exception:
            self._failed = True
        self._claims = {key: value for key, value in claims.items() if key in self._claims}
        self._roles.intersection_update(roles)

    @contextmanager
    def _snapshot(self):
        with self._mutex:
            self._ensure_open()
            if self._depth:
                yield
                return
            self._depth, self._read_only = 1, True
            try:
                self._connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
                yield
                self._connection.execute("COMMIT")
            except self._pg.Error as exc:
                self._rollback()
                raise self._database_failure(exc) from exc
            except BaseException:
                self._rollback()
                raise
            finally:
                self._depth, self._read_only = 0, False

    def _initialize(self):
        # Namespace creation and all upgrades serialize across workers. Native
        # backend versions are separate from the portable LocalStore schema 4.
        with self._transaction():
            self._connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.namespace}"')
            self._connection.execute(f'SET search_path TO "{self.namespace}",pg_catalog')
            self._connection.execute("CREATE TABLE IF NOT EXISTS backend_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            row = self._connection.execute("SELECT value FROM backend_metadata WHERE key='protocol'").fetchone()
            if row is not None:
                if row["value"] not in ("1", "2", "3"):
                    raise IntegrityError("Unsupported PostgreSQL recovery protocol")
                if row["value"] != "3":
                    self._quiescent_upgrade()
                self._initialize_resources()
                self._initialize_maintenance()
                self._connection.execute("UPDATE backend_metadata SET value='3' WHERE key='protocol'")
                return
            statements = [
                "CREATE TABLE contexts(context_id TEXT PRIMARY KEY,generation BIGINT NOT NULL,deleted SMALLINT NOT NULL DEFAULT 0)",
                """CREATE TABLE runs(run_id TEXT PRIMARY KEY,context_id TEXT NOT NULL REFERENCES contexts(context_id),
                    input_id TEXT NOT NULL,input_payload TEXT,input_digest TEXT,generation BIGINT NOT NULL,phase TEXT NOT NULL,
                    status TEXT NOT NULL,checkpoint TEXT,checkpoint_digest TEXT,checkpoint_seq BIGINT NOT NULL DEFAULT 0,
                    created_at DOUBLE PRECISION NOT NULL,updated_at DOUBLE PRECISION NOT NULL,payloads_pruned SMALLINT NOT NULL DEFAULT 0,
                    UNIQUE(context_id,input_id))""",
                "CREATE UNIQUE INDEX one_active_run ON runs(context_id) WHERE status IN ('running','blocked','attention')",
                """CREATE TABLE events(seq BIGSERIAL PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(run_id),kind TEXT NOT NULL,
                    payload TEXT,payload_digest TEXT,created_at DOUBLE PRECISION NOT NULL,payloads_pruned SMALLINT NOT NULL DEFAULT 0)""",
                "CREATE INDEX events_by_run ON events(run_id,seq)",
                """CREATE TABLE calls(run_id TEXT NOT NULL REFERENCES runs(run_id),call_id TEXT NOT NULL,kind TEXT NOT NULL,
                    payload TEXT,fingerprint TEXT,replay TEXT NOT NULL,status TEXT NOT NULL,result TEXT,result_digest TEXT,
                    created_at DOUBLE PRECISION NOT NULL,updated_at DOUBLE PRECISION NOT NULL,payloads_pruned SMALLINT NOT NULL DEFAULT 0,
                    document_edits_digest TEXT,logical_call_id TEXT,attempt INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(run_id,call_id))""",
                "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
                "CREATE TABLE blobs(digest TEXT PRIMARY KEY,size BIGINT NOT NULL,created_at DOUBLE PRECISION NOT NULL,data BYTEA NOT NULL)",
                """CREATE TABLE documents(context_id TEXT NOT NULL REFERENCES contexts(context_id),kind TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,revision BIGINT NOT NULL,value TEXT NOT NULL,digest TEXT NOT NULL,
                    generation BIGINT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,PRIMARY KEY(context_id,kind))""",
                """CREATE TABLE document_events(seq BIGSERIAL PRIMARY KEY,context_id TEXT NOT NULL REFERENCES contexts(context_id),
                    kind TEXT NOT NULL,revision BIGINT NOT NULL,schema_version INTEGER NOT NULL,digest TEXT NOT NULL,
                    mutation_id TEXT NOT NULL,run_id TEXT,call_id TEXT,created_at DOUBLE PRECISION NOT NULL)""",
                """CREATE TABLE document_mutations(context_id TEXT NOT NULL REFERENCES contexts(context_id),mutation_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,receipt TEXT NOT NULL,PRIMARY KEY(context_id,mutation_id))""",
                """CREATE TABLE document_conflicts(conflict_id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(run_id),call_id TEXT NOT NULL,
                    kind TEXT NOT NULL,schema_version INTEGER NOT NULL,expected_revision BIGINT NOT NULL,current_revision BIGINT NOT NULL,
                    proposed TEXT,digest TEXT,status TEXT NOT NULL,reason TEXT NOT NULL,decision TEXT,created_at DOUBLE PRECISION NOT NULL,resolved_at DOUBLE PRECISION)""",
                "CREATE INDEX document_conflicts_by_run ON document_conflicts(run_id,status)",
                """CREATE TABLE review_requests(request_id TEXT PRIMARY KEY,operation TEXT NOT NULL,run_id TEXT REFERENCES runs(run_id),
                    fingerprint TEXT NOT NULL,request TEXT,result TEXT NOT NULL,created_at DOUBLE PRECISION NOT NULL)""",
                """CREATE TABLE review_resolutions(seq BIGSERIAL PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(run_id),call_id TEXT,
                    decision TEXT NOT NULL,note TEXT,request_id TEXT NOT NULL UNIQUE,created_at DOUBLE PRECISION NOT NULL)""",
                """CREATE TABLE restore_selections(run_id TEXT PRIMARY KEY REFERENCES runs(run_id),epoch TEXT NOT NULL,
                    request_id TEXT,selected_at DOUBLE PRECISION NOT NULL)""",
                """CREATE TABLE retry_grants(seq BIGSERIAL PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(run_id),logical_call_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,attempt INTEGER NOT NULL,epoch TEXT NOT NULL,state TEXT NOT NULL,request_id TEXT NOT NULL UNIQUE,created_at DOUBLE PRECISION NOT NULL)""",
                """CREATE TABLE execution_claims(context_id TEXT PRIMARY KEY REFERENCES contexts(context_id),run_id TEXT NOT NULL REFERENCES runs(run_id),
                    worker_id TEXT,backend_pid INTEGER,backend_started TEXT,fence BIGINT NOT NULL)""",
                """CREATE TABLE context_heads(context_id TEXT PRIMARY KEY REFERENCES contexts(context_id),run_id TEXT NOT NULL REFERENCES runs(run_id),
                    generation BIGINT NOT NULL,checkpoint TEXT NOT NULL,digest TEXT NOT NULL,checkpoint_seq BIGINT NOT NULL,admission_seq BIGINT NOT NULL)""",
                "CREATE TABLE projections(key TEXT PRIMARY KEY,version BIGINT NOT NULL,value TEXT NOT NULL,digest TEXT NOT NULL)",
                "CREATE TABLE coordinator_roles(name TEXT PRIMARY KEY,worker_id TEXT NOT NULL,backend_pid INTEGER NOT NULL,backend_started TEXT NOT NULL)",
                """CREATE TABLE control_requests(request_id TEXT PRIMARY KEY,context_id TEXT NOT NULL,action TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,result TEXT NOT NULL,result_digest TEXT NOT NULL)""",
                """CREATE TABLE commands(command_id BIGSERIAL PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(run_id),kind TEXT NOT NULL,
                    payload TEXT,fingerprint TEXT NOT NULL,request_id TEXT NOT NULL UNIQUE,status TEXT NOT NULL,
                    result TEXT,result_digest TEXT,created_at DOUBLE PRECISION NOT NULL,payloads_pruned SMALLINT NOT NULL DEFAULT 0,epoch TEXT NOT NULL)""",
                "CREATE INDEX commands_by_run ON commands(run_id,status,command_id)",
            ]
            for statement in statements:
                self._connection.execute(statement)
            self._initialize_resources()
            self._initialize_maintenance()
            self._connection.execute("INSERT INTO backend_metadata(key,value) VALUES('protocol','3')")
            self._connection.execute("INSERT INTO metadata(key,value) VALUES('deployment_epoch',?)", (uuid.uuid4().hex,))

    def _quiescent_upgrade(self):
        message = "Stop all recovery workers and settle submitted/running resource jobs before upgrading PostgreSQL durability"
        for row in self._connection.execute("SELECT context_id,backend_pid FROM execution_claims WHERE worker_id IS NOT NULL"):
            if self._held(_lock_key(self.namespace, "context", row["context_id"]), row["backend_pid"]):
                raise OwnershipError(message)
        for row in self._connection.execute("SELECT name,backend_pid FROM coordinator_roles"):
            if self._held(_lock_key(self.namespace, "role", row["name"]), row["backend_pid"]):
                raise OwnershipError(message)
        if self._connection.execute("SELECT to_regclass('resource_jobs') AS present").fetchone()["present"] is not None:
            if self._connection.execute("SELECT 1 FROM resource_jobs WHERE status IN ('submitted','running') LIMIT 1").fetchone():
                raise OwnershipError(message)

    def _initialize_maintenance(self):
        self._connection.execute("""CREATE TABLE IF NOT EXISTS maintenance_contexts(
            request_id TEXT NOT NULL,context_id TEXT NOT NULL,run_id TEXT NOT NULL,generation BIGINT NOT NULL,
            PRIMARY KEY(request_id,context_id))""")
        self._connection.execute("""CREATE TABLE IF NOT EXISTS maintenance_effects(
            request_id TEXT NOT NULL,effect_id TEXT NOT NULL,fingerprint TEXT NOT NULL,status TEXT NOT NULL,
            result TEXT,result_digest TEXT,PRIMARY KEY(request_id,effect_id))""")

    def _event(self, run_id, kind, payload=None):
        encoded = _json(payload)
        return self._connection.execute("INSERT INTO events(run_id,kind,payload,payload_digest,created_at) VALUES(?,?,?,?,?) RETURNING seq",
            (run_id, kind, self._encode(encoded), _digest(encoded), self._now())).fetchone()["seq"]

    def _encode(self, encoded):
        data = encoded.encode("utf-8")
        if len(data) < _BLOB_THRESHOLD:
            return encoded
        digest = _digest(encoded)
        self._connection.execute("INSERT INTO blobs(digest,size,created_at,data) VALUES(?,?,?,?) ON CONFLICT(digest) DO NOTHING",
                                 (digest, len(data), self._now(), data))
        if self._blob_bytes(digest) != data:
            raise IntegrityError("Recovery blob identity has conflicting bytes")
        return _BLOB_PREFIX + digest

    def _blob_bytes(self, digest):
        row = self._connection.execute("SELECT size,data FROM blobs WHERE digest=?", (digest,)).fetchone()
        if row is None or type(row["size"]) is not int or not 0 <= row["size"] <= _MAX_JSON:
            raise IntegrityError("Recovery database blob is missing or invalid")
        data = bytes(row["data"])
        if len(data) != row["size"] or hashlib.sha256(data).hexdigest() != digest:
            raise IntegrityError("Recovery database blob integrity check failed")
        return data

    def garbage_collect(self):
        removed = size = 0
        with self._transaction():
            reachable = self._referenced_blobs()
            for row in self._connection.execute("SELECT digest,size FROM blobs").fetchall():
                if row["digest"] not in reachable:
                    self._connection.execute("DELETE FROM blobs WHERE digest=?", (row["digest"],))
                    removed += 1
                    size += row["size"]
        return {"blobs_removed": removed, "bytes_removed": size}

    def _reclaim_pages(self):
        # PostgreSQL MVCC/WAL/replica/backup custody is administered separately.
        pass

    def backup(self, destination):
        raise DurableStoreError("PostgreSQL recovery requires a consistent native database backup; SQLite backup export is unavailable")

    def _claim_row(self, run_id):
        return self._connection.execute("""SELECT e.*,r.generation AS run_generation,c.generation AS current_generation,c.deleted
            FROM execution_claims e JOIN runs r ON r.context_id=e.context_id JOIN contexts c ON c.context_id=e.context_id
            WHERE r.run_id=?""", (run_id,)).fetchone()

    def _held(self, key, pid):
        unsigned = key & ((1 << 64) - 1)
        return self._connection.execute("""SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=? AND granted
            AND database=(SELECT oid FROM pg_database WHERE datname=current_database())
            AND classid::bigint=? AND objid::bigint=? AND objsubid=1""", (pid, unsigned >> 32, unsigned & 0xffffffff)).fetchone() is not None

    def claim(self, run_id):
        return self._claim(run_id)

    def claim_maintenance(self, run_id):
        """Take the same context lock for idle maintenance, without running a turn."""
        return self._claim(run_id, maintenance=True)

    def _claim(self, run_id, maintenance=False):
        _identity(run_id, "run id")
        with self._transaction():
            if run_id in self._claims:
                self.assert_owner(run_id)
                return True
            run = self._review_run(run_id)
            if maintenance:
                latest = self._connection.execute("""SELECT r.run_id FROM runs r JOIN events e ON e.run_id=r.run_id
                    AND e.kind='admitted' WHERE r.context_id=? AND r.generation=? ORDER BY e.seq DESC LIMIT 1""",
                    (run["context_id"], run["generation"])).fetchone()
                if not latest or latest["run_id"] != run_id:
                    return False
            elif run["status"] not in _ACTIVE or not self.can_resume(run_id):
                return False
            # A context lock also prevents overlap between successive cancelled
            # and newly admitted runs while an old body is still unwinding.
            if any(item["context_id"] == run["context_id"] for item in self._claims.values()):
                return False
            key = _lock_key(self.namespace, "context", run["context_id"])
            if not self._connection.execute("SELECT pg_try_advisory_lock(?) AS acquired", (key,)).fetchone()["acquired"]:
                return False
            try:
                row = self._connection.execute("""INSERT INTO execution_claims(context_id,run_id,worker_id,backend_pid,backend_started,fence)
                    VALUES(?,?,?,?,?,1) ON CONFLICT(context_id) DO UPDATE SET run_id=excluded.run_id,worker_id=excluded.worker_id,
                    backend_pid=excluded.backend_pid,backend_started=excluded.backend_started,fence=execution_claims.fence+1 RETURNING fence""",
                    (run["context_id"], run_id, self.worker_id, self._backend_pid, self._backend_started)).fetchone()
                self._claims[run_id] = {"context_id": run["context_id"], "fence": row["fence"], "key": key}
            except BaseException:
                self._connection.execute("SELECT pg_advisory_unlock(?)", (key,))
                raise
        return True

    def _assert_claim(self, run_id):
        claim = self._claims.get(run_id)
        row = self._claim_row(run_id) if claim else None
        if row is None or row["run_id"] != run_id or row["worker_id"] != self.worker_id or row["backend_pid"] != self._backend_pid or row["backend_started"] != self._backend_started or row["fence"] != claim["fence"] or not self._held(claim["key"], self._backend_pid):
            raise OwnershipError("Recovery execution claim is not owned by this worker")
        return row

    def assert_owner(self, run_id):
        _identity(run_id, "run id")
        with self._snapshot():
            row = self._assert_claim(run_id)
            if row["deleted"] or row["run_generation"] != row["current_generation"]:
                raise StaleRunError("Recovery execution belongs to a reset or deleted context")

    def owns(self, run_id):
        try:
            self.assert_owner(run_id)
            return True
        except (OwnershipError, StaleRunError):
            return False

    def ownership(self, run_id):
        _identity(run_id, "run id")
        with self._snapshot():
            row = self._claim_row(run_id)
            live = row and row["run_id"] == run_id and row["worker_id"] and self._connection.execute(
                "SELECT 1 FROM pg_stat_activity WHERE pid=? AND backend_start=?::timestamptz", (row["backend_pid"], row["backend_started"])).fetchone()
            live = live and self._held(_lock_key(self.namespace, "context", row["context_id"]), row["backend_pid"])
            return {"claimed": bool(live), "worker_id": row["worker_id"] if live else None, "fence": row["fence"] if row else None}

    def release(self, run_id):
        _identity(run_id, "run id")
        with self._transaction():
            claim = self._claims.get(run_id)
            if claim is None:
                return
            self._assert_claim(run_id)
            self._connection.execute("UPDATE execution_claims SET worker_id=NULL,backend_pid=NULL,backend_started=NULL WHERE context_id=? AND fence=?",
                                     (claim["context_id"], claim["fence"]))
            self._connection.execute("SELECT pg_advisory_unlock(?)", (claim["key"],))
            self._claims.pop(run_id)

    def try_role(self, name):
        _identity(name, "coordinator role")
        with self._transaction():
            if name in self._roles:
                return self._held(_lock_key(self.namespace, "role", name), self._backend_pid)
            acquired = self._connection.execute("SELECT pg_try_advisory_lock(?) AS acquired", (_lock_key(self.namespace, "role", name),)).fetchone()["acquired"]
            if acquired:
                self._roles.add(name)
                self._connection.execute("""INSERT INTO coordinator_roles(name,worker_id,backend_pid,backend_started) VALUES(?,?,?,?)
                    ON CONFLICT(name) DO UPDATE SET worker_id=excluded.worker_id,backend_pid=excluded.backend_pid,backend_started=excluded.backend_started""",
                    (name, self.worker_id, self._backend_pid, self._backend_started))
            return acquired

    def release_role(self, name):
        _identity(name, "coordinator role")
        with self._transaction():
            if name in self._roles:
                self._connection.execute("DELETE FROM coordinator_roles WHERE name=? AND worker_id=? AND backend_pid=?", (name, self.worker_id, self._backend_pid))
                self._connection.execute("SELECT pg_advisory_unlock(?)", (_lock_key(self.namespace, "role", name),))
                self._roles.remove(name)

    def _publish_head(self, run_id):
        row = self._connection.execute("SELECT r.*,(SELECT MIN(seq) FROM events WHERE run_id=r.run_id AND kind='admitted') AS admission_seq FROM runs r WHERE run_id=?", (run_id,)).fetchone()
        if row["checkpoint"] is None or row["payloads_pruned"]:
            return
        context = self._document_context(row["context_id"])
        if context["generation"] != row["generation"]:
            return
        checkpoint = self._read(row["checkpoint"], row["checkpoint_digest"], required=True)
        self._verify_resources(row["context_id"], checkpoint.get("resources", {}))
        if self.owns(run_id):
            workspace = (checkpoint.get("resources") or {}).get("workspace")
            if workspace:
                previous = self.get_resource_manifest(row["context_id"], "workspace")
                if previous is None or previous["value"] != workspace:
                    self.publish_resource_manifest(row["context_id"], "workspace", workspace,
                                                   previous["version"] if previous else 0, run_id)
        self._connection.execute("""INSERT INTO context_heads(context_id,run_id,generation,checkpoint,digest,checkpoint_seq,admission_seq)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(context_id) DO UPDATE SET run_id=excluded.run_id,generation=excluded.generation,
            checkpoint=excluded.checkpoint,digest=excluded.digest,checkpoint_seq=excluded.checkpoint_seq,admission_seq=excluded.admission_seq
            WHERE excluded.admission_seq>=context_heads.admission_seq""",
            (row["context_id"], run_id, row["generation"], row["checkpoint"], row["checkpoint_digest"], row["checkpoint_seq"], row["admission_seq"]))

    def get_context_head(self, context_id):
        with self._snapshot():
            self._document_context(context_id)
            row = self._connection.execute("SELECT * FROM context_heads WHERE context_id=?", (context_id,)).fetchone()
            return None if row is None else {**dict(row), "checkpoint": self._read(row["checkpoint"], row["digest"], required=True)}

    def ensure_maintenance_anchor(self, context_id):
        """Promote a verified unsent draft to an inert head, without a runner."""
        _identity(context_id, "context id")
        with self._transaction():
            rows = self.list_run_headers(context_id=context_id)
            if rows:
                return max(rows, key=lambda row: (row.get("admission_seq", 0), row["run_id"]))["run_id"]
            saved = self.get_projection("genesis:" + context_id)
            if not saved or (saved["value"].get("context") or {}).get("id") != context_id:
                raise KeyError("Unknown shared chat")
            checkpoint = saved["value"]
            run = super().admit(context_id, "maintenance-seed", {}, checkpoint)
            seq = self._event(run["run_id"], "maintenance_anchor", {"genesis_version": saved["version"]})
            self._connection.execute("UPDATE runs SET status='completed',phase='completed',checkpoint_seq=?,updated_at=? WHERE run_id=?",
                                     (seq, self._now(), run["run_id"]))
            self._publish_head(run["run_id"])
            self._connection.execute("DELETE FROM projections WHERE key=?", ("genesis:" + context_id,))
            return run["run_id"]

    def admit(self, context_id, input_id, input_payload, checkpoint, *, expected_generation=None):
        with self._transaction():
            existing = self._connection.execute("SELECT 1 FROM runs WHERE context_id=? AND input_id=?", (context_id, input_id)).fetchone()
            if not existing and self._connection.execute("""SELECT 1 FROM commands c JOIN runs r USING(run_id)
                    WHERE (r.context_id=? OR EXISTS(SELECT 1 FROM maintenance_contexts m
                        WHERE m.request_id=c.request_id AND m.context_id=?))
                    AND c.kind='maintenance_delete' AND c.status='pending' AND c.epoch=?""",
                    (context_id, context_id, self.get_restore_state()["epoch"])).fetchone():
                raise ConflictError("Chat removal is pending; new work is held")
            for uri in input_payload.get("attachments", []):
                if isinstance(uri, str) and uri.startswith("a0-resource://"):
                    self.get_resource(context_id, uri[len("a0-resource://"):])
            if expected_generation is not None:
                existing = self._connection.execute("SELECT 1 FROM runs WHERE context_id=? AND input_id=?", (context_id, input_id)).fetchone()
                if not existing and self.document_generation(context_id) != expected_generation:
                    raise ConflictError("Shared context was reset during admission; refresh before sending")
            run = super().admit(context_id, input_id, input_payload, checkpoint)
            self._publish_head(run["run_id"])
            self._connection.execute("DELETE FROM projections WHERE key=?", ("genesis:" + context_id,))
            return run

    def transition(self, run_id, *args, **kwargs):
        with self._transaction():
            self.assert_owner(run_id)
            result = super().transition(run_id, *args, **kwargs)
            self._publish_head(run_id)
            return result

    def start_call(self, run_id, *args, **kwargs):
        with self._transaction():
            self.assert_owner(run_id)
            return super().start_call(run_id, *args, **kwargs)

    def finish_call(self, run_id, *args, **kwargs):
        with self._transaction():
            self.assert_owner(run_id)
            result = super().finish_call(run_id, *args, **kwargs)
            self._publish_head(run_id)
            return result

    def begin_retry(self, run_id, *args, **kwargs):
        with self._transaction():
            self.assert_owner(run_id)
            return super().begin_retry(run_id, *args, **kwargs)

    def list_projections(self, prefix="chat:"):
        _identity(prefix, "projection prefix")
        with self._snapshot():
            rows = self._connection.execute("SELECT key,version,value,digest FROM projections WHERE starts_with(key,?) ORDER BY key", (prefix,)).fetchall()
            result = []
            for row in rows:
                try:
                    value = self._read(row["value"], row["digest"], required=True)
                except IntegrityError:
                    # Inventory cannot promote corrupt data to authority, but
                    # one broken draft must not hide every healthy shared chat.
                    continue
                result.append({"key": row["key"], "version": row["version"], "value": value})
            return result

    def snapshot_revision(self):
        """Small shared invalidation watermark; private payloads never leave SQL."""
        with self._snapshot():
            row = self._connection.execute("""SELECT
                (SELECT COALESCE(MAX(seq),0) FROM events) AS events,
                (SELECT COALESCE(MAX(seq),0) FROM document_events) AS documents,
                (SELECT COALESCE(SUM(version),0) FROM projections) AS projections,
                (SELECT COALESCE(MAX(command_id),0) FROM commands) AS commands,
                (SELECT COUNT(*) FROM commands WHERE status!='pending') AS delivered,
                (SELECT COUNT(*) FROM control_requests) AS controls,
                (SELECT COALESCE(SUM(generation),0) FROM contexts) AS generations,
                (SELECT COUNT(*) FROM runs WHERE payloads_pruned=1) AS pruned""").fetchone()
            return _digest(_json({**{key: int(value) for key, value in row.items()}, "epoch": self.get_restore_state()["epoch"]}))

    def get_projection(self, key):
        _identity(key, "projection key")
        with self._snapshot():
            row = self._connection.execute("SELECT version,value,digest FROM projections WHERE key=?", (key,)).fetchone()
            return None if row is None else {"version": row["version"], "value": self._read(row["value"], row["digest"], required=True)}

    def put_projection(self, key, value, expected_version):
        _identity(key, "projection key")
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("Projection version must be nonnegative")
        encoded = _json(value)
        with self._transaction():
            if key.startswith("chat:"):
                context_id = _identity(key[5:], "context id")
                context = self._document_context(context_id)
                if context is not None:
                    owned = next((run_id for run_id, claim in self._claims.items() if claim["context_id"] == context_id), None)
                    if owned is None:
                        raise OwnershipError("Shared chat projection requires its execution owner")
                    self.assert_owner(owned)
                    self._review_run(owned)
            old = self.get_projection(key)
            if (old["version"] if old else 0) != expected_version:
                raise ConflictError("Shared projection version changed")
            self._connection.execute("""INSERT INTO projections(key,version,value,digest) VALUES(?,?,?,?) ON CONFLICT(key)
                DO UPDATE SET version=excluded.version,value=excluded.value,digest=excluded.digest""",
                (key, expected_version + 1, self._encode(encoded), _digest(encoded)))
            return self.get_projection(key)

    def commit_memory_patch(self, key, expected_revision, operation_key, fingerprint, value, receipt,
                            *, run_id=None, job_id=None, job_token=None, control_role=None):
        """Atomically replace an encrypted typed index and retain its operation receipt."""
        if not key.startswith("memory:") or not operation_key.startswith("memory-op:"):
            raise ValueError("Invalid memory custody key")
        with self._transaction():
            epoch = self.get_restore_state()["epoch"]
            if value.get("epoch") != epoch or receipt.get("epoch") != epoch:
                raise ConflictError("Shared memory request belongs to another restore epoch")
            if run_id:
                self.assert_owner(run_id)
                run = self._review_run(run_id)
                if run["status"] != "running":
                    raise OwnershipError("Shared memory writer is paused or stopped")
            elif job_id:
                claim = self.assert_resource_job(job_id, job_token)
                run = self.get_run(claim["run_id"])
                if run["status"] not in {"running", "completed"} or (run.get("checkpoint") or {}).get("paused"):
                    raise OwnershipError("Shared memory background writer is paused or stopped")
            elif control_role not in self._roles or not self.try_role(control_role):
                raise OwnershipError("Shared memory mutation requires its owner")
            prior = self.get_projection(operation_key)
            if prior:
                if prior["value"]["fingerprint"] != fingerprint or prior["value"]["epoch"] != self.get_restore_state()["epoch"]:
                    raise ConflictError("Memory operation identity changed")
                return prior["value"]["receipt"]
            self.put_projection(key, value, expected_revision)
            self.put_projection(operation_key, {"epoch": self.get_restore_state()["epoch"],
                "fingerprint": fingerprint, "receipt": receipt}, 0)
            return receipt

    def _command(self, row):
        if row is None:
            raise KeyError("Unknown recovery command")
        if row["payloads_pruned"]:
            return dict(row, payload=None,
                        result=self._read(row["result"], row["result_digest"], required=True) if row["result"] is not None else None,
                        payloads_pruned=True, epoch_valid=row["epoch"] == self.get_restore_state()["epoch"])
        if row["payload"] is None:
            raise IntegrityError("Recovery command payload is missing")
        payload = self._read(row["payload"])
        expected = _digest(_json({"run_id": row["run_id"], "kind": row["kind"], "payload": payload}))
        if expected != row["fingerprint"]:
            raise IntegrityError("Recovery command integrity check failed")
        if row["status"] == "pending" and (row["result"] is not None or row["result_digest"] is not None):
            raise IntegrityError("Pending recovery command has an unexpected result")
        return dict(row, payload=payload, result=self._read(row["result"], row["result_digest"], required=row["status"] == "applied"),
                    epoch_valid=row["epoch"] == self.get_restore_state()["epoch"])

    def enqueue_command(self, run_id, kind, payload, request_id):
        _identity(run_id, "run id")
        _identity(kind, "command kind")
        _identity(request_id, "command request id")
        encoded = _json(payload)
        fingerprint = _digest(_json({"run_id": run_id, "kind": kind, "payload": payload}))
        with self._transaction():
            prior = self._connection.execute("SELECT * FROM commands WHERE request_id=?", (request_id,)).fetchone()
            if prior:
                if prior["fingerprint"] != fingerprint:
                    raise ConflictError("Recovery command request has different content")
                if prior["epoch"] != self.get_restore_state()["epoch"]:
                    raise ConflictError("Recovery command belongs to another deployment epoch")
                return self._command(prior)
            run = self._review_run(run_id)
            if kind == "intervention" and (run["phase"] in {"terminal_ready", "finalizing", "scheduler_finalizing"} or run["status"] not in _ACTIVE):
                raise ConflictError("The current response is finishing; send new input after it completes")
            self._connection.execute("""INSERT INTO commands(run_id,kind,payload,fingerprint,request_id,status,created_at,epoch)
                VALUES(?,?,?,?,?,'pending',?,?)""", (run_id, kind, self._encode(encoded), fingerprint, request_id, self._now(), self.get_restore_state()["epoch"]))
            return self._command(self._connection.execute("SELECT * FROM commands WHERE request_id=?", (request_id,)).fetchone())

    def pending_commands(self, run_id):
        _identity(run_id, "run id")
        with self._snapshot():
            return [self._command(row) for row in self._connection.execute("SELECT * FROM commands WHERE run_id=? AND status='pending' AND epoch=? ORDER BY command_id", (run_id, self.get_restore_state()["epoch"])).fetchall()]

    def get_command(self, run_id, request_id):
        _identity(run_id, "run id")
        _identity(request_id, "command request id")
        with self._snapshot():
            row = self._connection.execute("SELECT * FROM commands WHERE run_id=? AND request_id=?", (run_id, request_id)).fetchone()
            return self._command(row) if row else None

    def ack_command(self, run_id, request_id, *, result=None):
        _identity(run_id, "run id")
        _identity(request_id, "command request id")
        encoded = _json(result)
        with self._transaction():
            self.assert_owner(run_id)
            row = self._connection.execute("SELECT * FROM commands WHERE run_id=? AND request_id=?", (run_id, request_id)).fetchone()
            if row is None:
                raise KeyError("Unknown recovery command")
            if row["epoch"] != self.get_restore_state()["epoch"]:
                raise ConflictError("Recovery command belongs to another deployment epoch")
            if row["status"] == "pending":
                self._connection.execute("UPDATE commands SET status='applied',result=?,result_digest=? WHERE command_id=?", (self._encode(encoded), _digest(encoded), row["command_id"]))
            return self._command(self._connection.execute("SELECT * FROM commands WHERE command_id=?", (row["command_id"],)).fetchone())

    def apply_command(self, run_id, request_id, *, checkpoint, phase, status="running", result=None):
        with self._transaction():
            self.assert_owner(run_id)
            row = self._connection.execute("SELECT * FROM commands WHERE run_id=? AND request_id=?", (run_id, request_id)).fetchone()
            if row is None:
                raise KeyError("Unknown recovery command")
            if row["epoch"] != self.get_restore_state()["epoch"]:
                raise ConflictError("Recovery command belongs to another deployment epoch")
            if row["status"] == "pending":
                self.transition(run_id, phase, checkpoint=checkpoint, status=status)
            return self.ack_command(run_id, request_id, result=result)

    def list_command_runs(self, kinds):
        kinds = tuple(_identity(kind, "command kind") for kind in kinds)
        if not kinds:
            return []
        placeholders = ",".join("?" for _ in kinds)
        with self._snapshot():
            return [dict(row) for row in self._connection.execute(f"""SELECT r.run_id,r.context_id,MIN(c.command_id) AS command_id
                FROM commands c JOIN runs r USING(run_id) JOIN contexts x USING(context_id)
                WHERE c.status='pending' AND c.epoch=? AND c.kind IN ({placeholders}) AND x.deleted=0
                GROUP BY r.run_id,r.context_id ORDER BY MIN(c.command_id)""", (self.get_restore_state()["epoch"], *kinds))]

    def enqueue_maintenance(self, run_id, kind, payload, request_id):
        if kind not in ("maintenance_document", "maintenance_conflict", "maintenance_delete"):
            raise ValueError("Unknown maintenance kind")
        with self._transaction():
            prior = self._connection.execute("SELECT 1 FROM commands WHERE request_id=?", (request_id,)).fetchone()
            if not prior:
                run = self._review_run(run_id)
                self._document_context(run["context_id"], payload["generation"])
                if payload["epoch"] != self.get_restore_state()["epoch"]:
                    raise ConflictError("Maintenance belongs to another deployment epoch")
                if self.get_review(run_id)["version"] != payload["version"]:
                    raise ConflictError("Maintenance review changed")
                self._verify_resources(run["context_id"], payload["ref"])
            return self.enqueue_command(run_id, kind, payload, request_id)

    def apply_document_command(self, run_id, request_id, *, kind=None, schema_version=None,
                               value=None, expected_revision=None, conflict_id=None, decision=None):
        with self._transaction():
            self.assert_owner(run_id)
            command = self.get_command(run_id, request_id)
            if command is None:
                raise KeyError("Unknown maintenance request")
            if command["status"] != "pending":
                return command
            run = self._review_run(run_id)
            payload = command["payload"]
            self._document_context(run["context_id"], payload["generation"])
            if not command["epoch_valid"]:
                raise ConflictError("Maintenance belongs to another deployment epoch")
            if conflict_id is not None:
                self.resolve_document_conflict(run_id, conflict_id, decision, expected_revision,
                                               payload["version"], request_id)
            else:
                self.write_document(run["context_id"], kind, schema_version, value, expected_revision,
                                    request_id, expected_generation=payload["generation"])
            return self.ack_command(run_id, request_id, result={"accepted": True})

    def maintenance_effect(self, run_id, request_id, effect_id, fingerprint):
        _identity(effect_id, "maintenance effect id")
        with self._transaction():
            self.assert_owner(run_id)
            command = self.get_command(run_id, request_id)
            if command is None or command["status"] != "pending" or not command["epoch_valid"]:
                raise ConflictError("Maintenance is no longer pending")
            row = self._connection.execute("SELECT * FROM maintenance_effects WHERE request_id=? AND effect_id=?", (request_id,effect_id)).fetchone()
            if row is None:
                self._connection.execute("INSERT INTO maintenance_effects(request_id,effect_id,fingerprint,status) VALUES(?,?,?,'intent')", (request_id,effect_id,fingerprint))
                return {"status": "intent"}
            if row["fingerprint"] != fingerprint:
                raise ConflictError("Maintenance target changed")
            return {"status": row["status"], "result": self._read(row["result"], row["result_digest"], required=row["status"] == "completed")}

    def finish_maintenance_effect(self, run_id, request_id, effect_id, fingerprint):
        with self._transaction():
            self.maintenance_effect(run_id, request_id, effect_id, fingerprint)
            result = _json({"deleted": True})
            self._connection.execute("UPDATE maintenance_effects SET status='completed',result=?,result_digest=? WHERE request_id=? AND effect_id=?", (result,_digest(result),request_id,effect_id))

    def deletion_contexts(self, request_id):
        _identity(request_id, "deletion request id")
        with self._snapshot():
            return [dict(row) for row in self._connection.execute("SELECT * FROM maintenance_contexts WHERE request_id=? ORDER BY context_id", (request_id,))]

    def begin_deletion(self, run_id, request_id):
        """Freeze verified current descendant ownership and stop it atomically."""
        from types import SimpleNamespace
        from helpers.durable.workflows import descendant_context_ids
        with self._transaction():
            self.assert_owner(run_id)
            command = self.get_command(run_id, request_id)
            if command is None or command["kind"] != "maintenance_delete" or command["status"] != "pending" or not command["epoch_valid"]:
                raise ConflictError("Deletion is no longer pending")
            bindings = self._connection.execute("SELECT * FROM maintenance_contexts WHERE request_id=? ORDER BY context_id", (request_id,)).fetchall()
            if bindings:
                for item in bindings:
                    self._document_context(item["context_id"], item["generation"])
                return [dict(item) for item in bindings]
            run = self._review_run(run_id)
            proxy = SimpleNamespace(sync=lambda name, *args, **kwargs: getattr(self, name)(*args, **kwargs), distributed=True)
            context_ids = {run["context_id"]}
            for header in self.list_run_headers(context_id=run["context_id"]):
                context_ids.update(descendant_context_ids(proxy, header["run_id"]))
            bindings = []
            for context_id in sorted(context_ids):
                latest = self.list_run_headers(context_id=context_id)[-1]
                context = self._document_context(context_id)
                item = {"request_id": request_id, "context_id": context_id, "run_id": latest["run_id"], "generation": context["generation"]}
                self._connection.execute("INSERT INTO maintenance_contexts VALUES(?,?,?,?)", tuple(item.values()))
                bindings.append(item)
            self._control_rows(sorted(context_ids), "cancel")
            return bindings

    def deletion_provider_snapshot(self, request_id):
        """Version the complete frozen graph's cleanup evidence, including late outcomes."""
        _identity(request_id, "deletion request id")
        with self._snapshot():
            rows = {}
            for table, query in (
                ("runs", "SELECT r.run_id,r.checkpoint_digest,r.payloads_pruned FROM runs r"),
                ("calls", "SELECT r.run_id,c.call_id,c.status,c.result_digest,c.fingerprint,c.payloads_pruned FROM calls c JOIN runs r USING(run_id)"),
                ("heads", "SELECT r.run_id,h.digest FROM context_heads h JOIN runs r ON h.run_id=r.run_id")):
                query += " WHERE r.context_id IN (SELECT context_id FROM maintenance_contexts WHERE request_id=?)"
                if table == "calls":
                    query += " AND c.kind='model'"
                records = self._connection.execute(query, (request_id,)).fetchall()
                rows[table] = sorted((dict(row) for row in records), key=_json)
            return _digest(_json(rows))

    def complete_deletion(self, run_id, request_id, context_ids, *, unresolved_provider_calls=0,
                          expected_provider_snapshot):
        with self._transaction():
            self.assert_owner(run_id)
            command = self.get_command(run_id, request_id)
            if command is None or command["kind"] != "maintenance_delete" or not command["epoch_valid"]:
                raise ConflictError("Unknown or stale deletion request")
            if command["status"] != "pending":
                return command
            bindings = self._connection.execute("SELECT * FROM maintenance_contexts WHERE request_id=?", (request_id,)).fetchall()
            if set(context_ids) != {item["context_id"] for item in bindings}:
                raise ConflictError("Deletion context selection changed")
            for item in bindings:
                self._document_context(item["context_id"], item["generation"])
                context_id = item["context_id"]
                claim = next((identity for identity, item in self._claims.items() if item["context_id"] == context_id), None)
                if claim is None:
                    raise OwnershipError("Chat deletion requires every descendant context lock")
                self.assert_owner(claim)
            if self.deletion_provider_snapshot(request_id) != expected_provider_snapshot:
                return None  # A late known outcome must enter the next cleanup plan.
            self.ack_command(run_id, request_id, result={"accepted": True, "deleted": True, "unresolved_provider_calls": unresolved_provider_calls})
            self._control_rows(list(context_ids), "delete")
            return self.get_command(run_id, request_id)

    def _referenced_blobs(self):
        reachable = super()._referenced_blobs()
        for row in self._connection.execute("SELECT checkpoint AS value FROM context_heads WHERE checkpoint LIKE '@blob:%'").fetchall():
            reachable.add(self._blob_digest(row["value"]))
        for table, columns in (("projections", ("value",)), ("commands", ("payload", "result")),
                               ("resource_manifests", ("value",)), ("resource_jobs", ("result",))):
            for column in columns:
                for row in self._connection.execute(f"SELECT {column} AS value FROM {table} WHERE {column} LIKE '@blob:%'").fetchall():
                    reachable.add(self._blob_digest(row["value"]))
        return reachable

    def _control_rows(self, context_ids, action):
        if action == "reset":
            for context_id in context_ids:
                self._connection.execute("""UPDATE commands SET status='invalidated',payload=NULL,result=NULL,
                    result_digest=NULL,payloads_pruned=1 WHERE status='pending' AND kind LIKE 'maintenance_%'
                    AND (run_id IN (SELECT run_id FROM runs WHERE context_id=?) OR request_id IN
                        (SELECT request_id FROM maintenance_contexts WHERE context_id=?))""", (context_id, context_id))
        if action == "delete":
            for context_id in context_ids:
                self._delete_resources(context_id)
                self._connection.execute("DELETE FROM context_heads WHERE context_id=?", (context_id,))
                safe_result = _json({"accepted": False, "error": "context_deleted"})
                self._connection.execute("""UPDATE commands SET payload=NULL,payloads_pruned=1,
                    status=CASE WHEN status='pending' THEN 'applied' ELSE status END,
                    result=CASE WHEN status='pending' THEN ? ELSE result END,
                    result_digest=CASE WHEN status='pending' THEN ? ELSE result_digest END
                    WHERE run_id IN (SELECT run_id FROM runs WHERE context_id=?)""", (safe_result, _digest(safe_result), context_id))
                self._connection.execute("DELETE FROM projections WHERE key IN (?,?)", ("chat:" + context_id, "genesis:" + context_id))
        return super()._control_rows(context_ids, action)

    def control_request(self, context_id, action, request_id, *, context_ids=()):
        """Retry a shared reset/stop acknowledgement without repeating its fence.

        Descendants are captured only for the first accepted request. A retry
        acknowledges that original decision, even after later admissions change
        the graph; it must never reset those newly admitted generations.
        """
        _identity(context_id, "context id")
        _identity(request_id, "control request id")
        if action not in ("reset", "cancel"):
            raise ValueError("Shared control requests support reset or cancel")
        if isinstance(context_ids, (str, bytes)):
            raise ValueError("Related contexts must be a collection")
        related = list(dict.fromkeys([context_id, *(_identity(item, "context id") for item in context_ids)]))
        fingerprint = _digest(_json({"context_id": context_id, "action": action}))
        with self._transaction():
            prior = self._connection.execute("SELECT * FROM control_requests WHERE request_id=?", (request_id,)).fetchone()
            if prior is not None:
                if prior["context_id"] != context_id or prior["action"] != action or prior["fingerprint"] != fingerprint:
                    raise ConflictError("Control request id already has different content")
                result = self._read(prior["result"], prior["result_digest"], required=True)
                if result["epoch"] != self.get_restore_state()["epoch"]:
                    raise ConflictError("Control request belongs to another deployment epoch")
                return result
            contexts = self._control_rows(related, action)
            result = {"context_id": context_id, "action": action, "request_id": request_id,
                      "contexts": contexts, "epoch": self.get_restore_state()["epoch"]}
            encoded = _json(result)
            self._connection.execute("INSERT INTO control_requests(request_id,context_id,action,fingerprint,result,result_digest) VALUES(?,?,?,?,?,?)",
                (request_id, context_id, action, fingerprint, encoded, _digest(encoded)))
            return result

    def compact(self, *, retain_terminal=100, max_age_days=30, protected_run_ids=()):
        with self._transaction():
            pending = {row["run_id"] for row in self._connection.execute("SELECT DISTINCT run_id FROM commands WHERE status='pending' AND epoch=?", (self.get_restore_state()["epoch"],)).fetchall()}
            result = super().compact(retain_terminal=retain_terminal, max_age_days=max_age_days,
                protected_run_ids=set(protected_run_ids) | pending)
            for command in self._connection.execute("""SELECT run_id,request_id,result,result_digest FROM commands
                    WHERE status='applied' AND payloads_pruned=0 AND run_id IN
                    (SELECT run_id FROM runs WHERE payloads_pruned=1)""").fetchall():
                outcome = self._read(command["result"], command["result_digest"], required=True)
                # Keep the immutable acknowledgment, without retaining drafts,
                # provider identifiers or other private result projections.
                safe = {"accepted": outcome.get("accepted") is True}
                if outcome.get("deleted") is True:
                    safe["deleted"] = True
                unresolved = outcome.get("unresolved_provider_calls")
                if type(unresolved) is int and unresolved >= 0:
                    safe["unresolved_provider_calls"] = unresolved
                encoded = _json(safe)
                self._connection.execute("""UPDATE commands SET payload=NULL,result=?,result_digest=?,payloads_pruned=1
                    WHERE run_id=? AND request_id=?""", (encoded, _digest(encoded), command["run_id"], command["request_id"]))
            extra = self.garbage_collect()
            result["blobs_removed"] += extra["blobs_removed"]
            result["bytes_removed"] += extra["bytes_removed"]
            result.update(self.collect_resources())
            return result

    def begin_restore_review(self):
        """After a native restore, hold historical runs before starting workers.

        This explicit maintenance operation refuses live execution/coordinator
        sessions. Stop every worker before restoring a database, then invoke it
        before any worker's recovery scan. Native database restore cannot itself
        distinguish restored bytes from the original live database.
        """
        with self._transaction():
            for row in self._connection.execute("SELECT context_id,backend_pid FROM execution_claims WHERE worker_id IS NOT NULL").fetchall():
                if self._held(_lock_key(self.namespace, "context", row["context_id"]), row["backend_pid"]):
                    raise OwnershipError("Stop all recovery workers before beginning restore review")
            for row in self._connection.execute("SELECT name,backend_pid FROM coordinator_roles").fetchall():
                if self._held(_lock_key(self.namespace, "role", row["name"]), row["backend_pid"]):
                    raise OwnershipError("Stop all recovery coordinators before beginning restore review")
            epoch = uuid.uuid4().hex
            self._connection.execute("INSERT INTO metadata(key,value) VALUES('restore_requires_review','true') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
            self._connection.execute("UPDATE metadata SET value=? WHERE key='deployment_epoch'", (epoch,))
            self._connection.execute("DELETE FROM restore_selections")
            self._connection.execute("UPDATE commands SET status='invalidated',payload=NULL,result=NULL,result_digest=NULL,payloads_pruned=1 WHERE status='pending'")
            self._connection.execute("UPDATE execution_claims SET worker_id=NULL,backend_pid=NULL,backend_started=NULL")
            self._connection.execute("DELETE FROM coordinator_roles")
            return {"required": True, "epoch": epoch}

    def list_run_headers(self, statuses=None, context_id=None):
        with self._snapshot():
            headers = super().list_run_headers(statuses, context_id)
            order = {row["run_id"]: row for row in self._connection.execute("""SELECT r.run_id,r.checkpoint_seq,MIN(e.seq) AS admission_seq
                FROM runs r LEFT JOIN events e ON e.run_id=r.run_id AND e.kind='admitted'
                GROUP BY r.run_id,r.checkpoint_seq""").fetchall()}
            for header in headers:
                header.update(order[header["run_id"]])
            return sorted(headers, key=lambda row: (row["admission_seq"] or 0, row["run_id"]))

    def close(self):
        with self._mutex:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            self._claims.clear()
            self._roles.clear()


def _snapshot_method(name):
    def method(self, *args, **kwargs):
        with self._snapshot():
            return getattr(super(PostgresStore, self), name)(*args, **kwargs)
    method.__name__ = name
    return method


# Keep inherited read methods within one database snapshot, including dependent
# blob reads. A concurrent GC cannot remove bytes visible to that MVCC snapshot.
for _name in ("get_run", "matches_input", "matches_call", "read_document", "document_generation",
              "read_document_events", "list_document_conflicts", "get_restore_state", "can_resume",
              "get_review", "get_review_request", "list_resolutions", "get_retry", "list_runs",
              "read_events", "get_call", "calls", "requires_restore_review"):
    setattr(PostgresStore, _name, _snapshot_method(_name))
