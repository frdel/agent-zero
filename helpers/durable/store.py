"""Transactional, single-owner local recovery storage using only the stdlib."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import threading
import time
import uuid


class DurableStoreError(RuntimeError):
    """Recovery storage failed; callers must stop new external effects."""


class OwnershipError(DurableStoreError):
    """Another process owns this data root or its custody is unsafe."""


class IntegrityError(DurableStoreError):
    """Stored recovery data is corrupt or uses an unsupported schema."""


class ConflictError(DurableStoreError):
    """An idempotency identity was reused with different content."""


class StaleRunError(DurableStoreError):
    """A stopped, reset or deleted run cannot start new work."""


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")
_ACTIVE = ("running", "blocked", "attention")
_STATUSES = frozenset((*_ACTIVE, "completed", "cancelled", "failed"))
_MAX_JSON = 16 * 1024 * 1024
_BLOB_THRESHOLD = 64 * 1024
_BLOB_PREFIX = "@blob:"
_BLOB_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_MAX_DOCUMENT = 64 * 1024
_SCHEMA = 4


def _identity(value: str, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"Invalid {name}")
    return value


def _json(value) -> str:
    # Reject custom serializers, non-string keys, tuples and nonfinite floats.
    def validate(item, depth=0):
        if depth > 100:
            raise ValueError("Recovery JSON is nested too deeply")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                validate(child, depth + 1)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                validate(child, depth + 1)
            return
        raise ValueError("Recovery payload must contain strict JSON values")

    validate(value)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > _MAX_JSON:
        raise ValueError("Recovery JSON exceeds the 16 MiB limit")
    return encoded


def _digest(encoded: str) -> str:
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _decode(encoded, digest=None):
    if encoded is None:
        if digest is not None:
            raise IntegrityError("Recovery payload digest has no payload")
        return None
    if not isinstance(encoded, str):
        raise IntegrityError("Recovery JSON has an invalid storage type")
    if digest is not None and _digest(encoded) != digest:
        raise IntegrityError("Recovery payload integrity check failed")
    try:
        value = json.loads(encoded, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        _json(value)
        return value
    except (ValueError, TypeError, RecursionError) as exc:
        raise IntegrityError("Invalid recovery JSON") from exc


def _private_path(path: Path, *, directory=False, create=False):
    """Check all existing path components before creating an owned leaf."""
    for component in (path, *path.parents):
        if component.is_symlink():
            raise OwnershipError("Recovery paths must not traverse symlinks")
    if create and directory:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists():
        info = path.lstat()
        if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
            raise OwnershipError("Recovery path has an unsafe file type")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise OwnershipError("Recovery path belongs to another user")
        path.chmod(0o700 if directory else 0o600)


class LocalStore:
    """One process owns a data root until close or OS process termination.

    Returned objects are detached JSON data, never live database cursors. Each
    mutation commits a short transaction before returning to its caller.
    """

    def __init__(self, root: Path):
        self.root = Path(os.path.abspath(root))
        self.blob_root = self.root / "blobs"
        self._mutex = threading.RLock()
        self._connection = None
        self._lock_file = None
        self._pid = os.getpid()
        try:
            _private_path(self.root, directory=True, create=True)
            lock_path = self.root / "owner.lock"
            _private_path(lock_path)
            descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            self._lock_file = os.fdopen(descriptor, "r+b", buffering=0)
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, 0o600)
            self._acquire_lock()
            self._lock_identity = (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino)
            self.path = self.root / "state.sqlite3"
            self._check_files()
            # SQLite otherwise creates the database with process umask permissions.
            descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(descriptor)
            self._connection = sqlite3.connect(self.path, timeout=5, isolation_level=None, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA synchronous=FULL")
            if self._connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                raise IntegrityError("Recovery database does not support WAL")
            self._connection.execute("PRAGMA secure_delete=ON")
            self._initialize()
            _private_path(self.blob_root, directory=True, create=True)
            self._check_files()
            self._sync_directory(self.root)
            self._sync_directory(self.root.parent)
        except sqlite3.Error as exc:
            self.close()
            raise IntegrityError("Cannot open recovery database") from exc
        except BaseException:
            self.close()
            raise

    def _acquire_lock(self):
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(self._lock_file.fileno()).st_size == 0:
                    self._lock_file.write(b"\0")
                self._lock_file.seek(0)
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise OwnershipError("Recovery data root already has an owner") from exc

    def _check_files(self):
        if self._lock_file is not None:
            lock_path = self.root / "owner.lock"
            _private_path(lock_path)
            if not lock_path.exists():
                raise OwnershipError("Recovery ownership file was removed")
            info = lock_path.stat()
            if (info.st_dev, info.st_ino) != self._lock_identity:
                raise OwnershipError("Recovery ownership file changed")
        for suffix in ("", "-wal", "-shm", "-journal"):
            _private_path(self.root / ("state.sqlite3" + suffix))
        _private_path(self.blob_root, directory=True)

    def _initialize(self):
        conn = self._connection
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2, 3, _SCHEMA):
            raise IntegrityError("Unsupported recovery database schema")
        if version == 0:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if tables:
                raise IntegrityError("Unrecognized recovery database schema")
            statements = [
                "CREATE TABLE contexts(context_id TEXT PRIMARY KEY,generation INTEGER NOT NULL,deleted INTEGER NOT NULL DEFAULT 0)",
                """CREATE TABLE runs(run_id TEXT PRIMARY KEY,context_id TEXT NOT NULL REFERENCES contexts(context_id),
                    input_id TEXT NOT NULL,input_payload TEXT,input_digest TEXT,generation INTEGER NOT NULL,
                    phase TEXT NOT NULL,status TEXT NOT NULL,checkpoint TEXT,checkpoint_digest TEXT,
                    checkpoint_seq INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL,updated_at REAL NOT NULL,
                    payloads_pruned INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(context_id,input_id))""",
                "CREATE UNIQUE INDEX one_active_run ON runs(context_id) WHERE status IN ('running','blocked','attention')",
                """CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL REFERENCES runs(run_id),
                    kind TEXT NOT NULL,payload TEXT,payload_digest TEXT,created_at REAL NOT NULL,
                    payloads_pruned INTEGER NOT NULL DEFAULT 0)""",
                "CREATE INDEX events_by_run ON events(run_id,seq)",
                """CREATE TABLE calls(run_id TEXT NOT NULL REFERENCES runs(run_id),call_id TEXT NOT NULL,
                    kind TEXT NOT NULL,payload TEXT,fingerprint TEXT,replay TEXT NOT NULL,status TEXT NOT NULL,
                    result TEXT,result_digest TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL,
                    payloads_pruned INTEGER NOT NULL DEFAULT 0,document_edits_digest TEXT,
                    logical_call_id TEXT,attempt INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(run_id,call_id))""",
                "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
                "CREATE TABLE blobs(digest TEXT PRIMARY KEY,size INTEGER NOT NULL,created_at REAL NOT NULL)",
                "CREATE TABLE backup_blobs(digest TEXT PRIMARY KEY REFERENCES blobs(digest) ON DELETE CASCADE,data BLOB NOT NULL)",
            ]
            with self._transaction():
                for statement in statements:
                    conn.execute(statement)
                self._create_review_schema()
                conn.execute(f"PRAGMA user_version={_SCHEMA}")
        elif version in (1, 2, 3):
            with self._transaction():
                if version == 1:
                    conn.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
                if version <= 2:
                    for table in ("runs", "events", "calls"):
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN payloads_pruned INTEGER NOT NULL DEFAULT 0")
                    conn.execute("CREATE TABLE blobs(digest TEXT PRIMARY KEY,size INTEGER NOT NULL,created_at REAL NOT NULL)")
                    conn.execute("CREATE TABLE backup_blobs(digest TEXT PRIMARY KEY REFERENCES blobs(digest) ON DELETE CASCADE,data BLOB NOT NULL)")
                conn.execute("ALTER TABLE calls ADD COLUMN document_edits_digest TEXT")
                conn.execute("ALTER TABLE calls ADD COLUMN logical_call_id TEXT")
                conn.execute("ALTER TABLE calls ADD COLUMN attempt INTEGER NOT NULL DEFAULT 1")
                self._create_review_schema()
                conn.execute(f"PRAGMA user_version={_SCHEMA}")
        with self._transaction():
            conn.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('deployment_epoch',?)", (uuid.uuid4().hex,))
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise IntegrityError("Recovery database integrity check failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise IntegrityError("Recovery database reference integrity check failed")
        # Missing columns/tables fail at startup instead of silently disabling work.
        for table, columns in {
            "contexts": "context_id,generation,deleted",
            "runs": "run_id,context_id,input_id,input_payload,input_digest,generation,phase,status,checkpoint,checkpoint_digest,checkpoint_seq,created_at,updated_at,payloads_pruned",
            "events": "seq,run_id,kind,payload,payload_digest,created_at,payloads_pruned",
            "calls": "run_id,call_id,kind,payload,fingerprint,replay,status,result,result_digest,created_at,updated_at,payloads_pruned,document_edits_digest,logical_call_id,attempt",
            "metadata": "key,value",
            "blobs": "digest,size,created_at",
            "backup_blobs": "digest,data",
            "documents": "context_id,kind,schema_version,revision,value,digest,generation,updated_at",
            "document_events": "seq,context_id,kind,revision,schema_version,digest,mutation_id,run_id,call_id,created_at",
            "document_mutations": "context_id,mutation_id,fingerprint,receipt",
            "document_conflicts": "conflict_id,run_id,call_id,kind,schema_version,expected_revision,current_revision,proposed,digest,status,reason,decision,created_at,resolved_at",
            "review_requests": "request_id,operation,run_id,fingerprint,request,result,created_at",
            "review_resolutions": "seq,run_id,call_id,decision,note,request_id,created_at",
            "restore_selections": "run_id,epoch,request_id,selected_at",
            "retry_grants": "seq,run_id,logical_call_id,call_id,attempt,epoch,state,request_id,created_at",
        }.items():
            conn.execute(f"SELECT {columns} FROM {table} LIMIT 0")

    def _create_review_schema(self):
        statements = [
            """CREATE TABLE documents(context_id TEXT NOT NULL REFERENCES contexts(context_id),kind TEXT NOT NULL,
                schema_version INTEGER NOT NULL,revision INTEGER NOT NULL,value TEXT NOT NULL,digest TEXT NOT NULL,
                generation INTEGER NOT NULL,updated_at REAL NOT NULL,PRIMARY KEY(context_id,kind))""",
            """CREATE TABLE document_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,context_id TEXT NOT NULL REFERENCES contexts(context_id),
                kind TEXT NOT NULL,revision INTEGER NOT NULL,schema_version INTEGER NOT NULL,digest TEXT NOT NULL,
                mutation_id TEXT NOT NULL,run_id TEXT,call_id TEXT,created_at REAL NOT NULL)""",
            """CREATE TABLE document_mutations(context_id TEXT NOT NULL REFERENCES contexts(context_id),mutation_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,receipt TEXT NOT NULL,PRIMARY KEY(context_id,mutation_id))""",
            """CREATE TABLE document_conflicts(conflict_id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(run_id),
                call_id TEXT NOT NULL,kind TEXT NOT NULL,schema_version INTEGER NOT NULL,expected_revision INTEGER NOT NULL,
                current_revision INTEGER NOT NULL,proposed TEXT,digest TEXT,status TEXT NOT NULL,reason TEXT NOT NULL,
                decision TEXT,created_at REAL NOT NULL,resolved_at REAL)""",
            "CREATE INDEX document_conflicts_by_run ON document_conflicts(run_id,status)",
            """CREATE TABLE review_requests(request_id TEXT PRIMARY KEY,operation TEXT NOT NULL,run_id TEXT REFERENCES runs(run_id),
                fingerprint TEXT NOT NULL,request TEXT,result TEXT NOT NULL,created_at REAL NOT NULL)""",
            """CREATE TABLE review_resolutions(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL REFERENCES runs(run_id),
                call_id TEXT,decision TEXT NOT NULL,note TEXT,request_id TEXT NOT NULL UNIQUE,created_at REAL NOT NULL)""",
            """CREATE TABLE restore_selections(run_id TEXT PRIMARY KEY REFERENCES runs(run_id),epoch TEXT NOT NULL,
                request_id TEXT,selected_at REAL NOT NULL)""",
            """CREATE TABLE retry_grants(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL REFERENCES runs(run_id),
                logical_call_id TEXT NOT NULL,call_id TEXT NOT NULL,attempt INTEGER NOT NULL,epoch TEXT NOT NULL,
                state TEXT NOT NULL,request_id TEXT NOT NULL UNIQUE,created_at REAL NOT NULL)""",
        ]
        for statement in statements:
            self._connection.execute(statement)

    def _now(self):
        """The backend owns timestamps used for retention and audit metadata."""
        return time.time()

    def _ensure_open(self):
        if os.getpid() != self._pid:
            raise OwnershipError("Recovery store must not be reused after fork")
        if self._connection is None:
            raise DurableStoreError("Recovery store is closed")

    @contextmanager
    def _transaction(self):
        with self._mutex:
            self._ensure_open()
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                yield
                self._check_files()
                self._connection.execute("COMMIT")
            except sqlite3.Error as exc:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise DurableStoreError("Recovery transaction failed") from exc
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    @staticmethod
    def _blob_digest(reference):
        if not isinstance(reference, str) or not reference.startswith(_BLOB_PREFIX):
            raise IntegrityError("Invalid recovery blob reference")
        digest = reference[len(_BLOB_PREFIX):]
        if not _BLOB_DIGEST.fullmatch(digest):
            raise IntegrityError("Invalid recovery blob identity")
        return digest

    def _file_blob_bytes(self, digest, size):
        path = self.blob_root / (digest + ".json")
        _private_path(path)
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as source:
                if os.fstat(source.fileno()).st_size != size:
                    raise IntegrityError("Recovery blob size mismatch")
                data = source.read(size + 1)
        except FileNotFoundError as exc:
            raise IntegrityError("Recovery blob is missing") from exc
        except OSError as exc:
            raise DurableStoreError("Recovery blob read failed") from exc
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise IntegrityError("Recovery blob integrity check failed")
        return data

    def _publish_blob(self, data, digest):
        """Make verified bytes durable before any SQL reference can commit."""
        if len(data) > _MAX_JSON or hashlib.sha256(data).hexdigest() != digest:
            raise IntegrityError("Invalid recovery blob publication")
        _private_path(self.blob_root, directory=True, create=True)
        path = self.blob_root / (digest + ".json")
        _private_path(path)
        if path.exists():
            self._file_blob_bytes(digest, len(data))
            try:
                with path.open("rb") as existing:
                    os.fsync(existing.fileno())
                self._sync_directory(self.blob_root)
            except OSError as exc:
                raise DurableStoreError("Recovery blob publication failed") from exc
            return
        temporary = None
        try:
            descriptor, name = tempfile.mkstemp(prefix=".pending-", dir=self.blob_root)
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as target:
                target.write(data)
                target.flush()
                os.fsync(target.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                self._file_blob_bytes(digest, len(data))
            temporary.unlink()
            temporary = None
            self._sync_directory(self.blob_root)
        except OSError as exc:
            raise DurableStoreError("Recovery blob publication failed") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _blob_bytes(self, digest):
        row = self._connection.execute("SELECT size FROM blobs WHERE digest=?", (digest,)).fetchone()
        if row is None or type(row["size"]) is not int or not 0 <= row["size"] <= _MAX_JSON:
            raise IntegrityError("Recovery blob catalog is invalid")
        path = self.blob_root / (digest + ".json")
        _private_path(path)
        if not path.exists():
            embedded = self._connection.execute("SELECT data FROM backup_blobs WHERE digest=?", (digest,)).fetchone()
            if embedded is None:
                raise IntegrityError("Recovery blob is missing")
            data = embedded["data"]
            if not isinstance(data, bytes) or len(data) != row["size"] or hashlib.sha256(data).hexdigest() != digest:
                raise IntegrityError("Recovery backup blob integrity check failed")
            self._publish_blob(data, digest)
            # After durable hydration, ordinary missing-file corruption must not
            # silently recover from a second old copy. A rolled-back outer SQL
            # transaction can leave this row, safely alongside identical bytes.
            self._connection.execute("DELETE FROM backup_blobs WHERE digest=?", (digest,))
        return self._file_blob_bytes(digest, row["size"])

    def _encode(self, encoded):
        data = encoded.encode("utf-8")
        if len(data) < _BLOB_THRESHOLD:
            return encoded
        digest = hashlib.sha256(data).hexdigest()
        self._publish_blob(data, digest)
        self._connection.execute("INSERT OR IGNORE INTO blobs(digest,size,created_at) VALUES(?,?,?)", (digest, len(data), self._now()))
        size = self._connection.execute("SELECT size FROM blobs WHERE digest=?", (digest,)).fetchone()["size"]
        if size != len(data):
            raise IntegrityError("Recovery blob catalog size mismatch")
        return _BLOB_PREFIX + digest

    def _read(self, encoded, digest=None, *, required=False):
        # Payload columns are nullable for intents and retained tombstones only.
        # A missing digest on a live value must never disable verification.
        if required and (encoded is None or not isinstance(digest, str) or not _BLOB_DIGEST.fullmatch(digest)):
            raise IntegrityError("Recovery payload is missing its integrity metadata")
        if isinstance(encoded, str) and encoded.startswith(_BLOB_PREFIX):
            try:
                encoded = self._blob_bytes(self._blob_digest(encoded)).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise IntegrityError("Recovery blob is not UTF-8 JSON") from exc
        return _decode(encoded, digest)

    def _referenced_blobs(self):
        # Inspect storage references only; a corrupt payload in one context must
        # not require decoding every unrelated checkpoint to do maintenance.
        rows = self._connection.execute("""
            SELECT input_payload AS value FROM runs WHERE input_payload LIKE '@blob:%'
            UNION ALL SELECT checkpoint FROM runs WHERE checkpoint LIKE '@blob:%'
            UNION ALL SELECT payload FROM calls WHERE payload LIKE '@blob:%'
            UNION ALL SELECT result FROM calls WHERE result LIKE '@blob:%'
            UNION ALL SELECT payload FROM events WHERE payload LIKE '@blob:%'
            UNION ALL SELECT value FROM documents WHERE value LIKE '@blob:%'
            UNION ALL SELECT proposed FROM document_conflicts WHERE proposed LIKE '@blob:%'
        """).fetchall()
        return {self._blob_digest(row["value"]) for row in rows}

    def _event(self, run_id, kind, payload=None):
        encoded = _json(payload)
        return self._connection.execute(
            "INSERT INTO events(run_id,kind,payload,payload_digest,created_at) VALUES(?,?,?,?,?)",
            (run_id, kind, self._encode(encoded), _digest(encoded), self._now()),
        ).lastrowid

    def _run(self, run_id):
        row = self._connection.execute("SELECT * FROM runs WHERE run_id=?", (_identity(run_id, "run id"),)).fetchone()
        if row is None:
            raise KeyError("Unknown durable run")
        result = dict(row)
        result["payloads_pruned"] = bool(result["payloads_pruned"])
        if result["payloads_pruned"]:
            result["input_payload"] = result["checkpoint"] = None
        else:
            result["input_payload"] = self._read(result["input_payload"], result["input_digest"], required=True)
            result["checkpoint"] = self._read(result["checkpoint"], result["checkpoint_digest"], required=True)
        return result

    def _writable(self, run_id, *, allow_cancelled=False):
        run = self._run(run_id)
        context = self._connection.execute("SELECT * FROM contexts WHERE context_id=?", (run["context_id"],)).fetchone()
        if context["deleted"] or context["generation"] != run["generation"]:
            raise StaleRunError("Recovery context generation changed")
        if run["status"] not in _ACTIVE and not (allow_cancelled and run["status"] == "cancelled"):
            raise StaleRunError("Recovery run no longer accepts work")
        return run

    def admit(self, context_id, input_id, input_payload, checkpoint):
        _identity(context_id, "context id")
        _identity(input_id, "input id")
        encoded, genesis = _json(input_payload), _json(checkpoint)
        with self._transaction():
            context = self._connection.execute("SELECT * FROM contexts WHERE context_id=?", (context_id,)).fetchone()
            if context is not None and context["deleted"]:
                raise StaleRunError("Recovery context was deleted")
            existing = self._connection.execute("SELECT run_id,input_digest FROM runs WHERE context_id=? AND input_id=?", (context_id, input_id)).fetchone()
            if existing:
                if existing["input_digest"] != _digest(encoded):
                    raise ConflictError("Input identity already has different content")
                return self._run(existing["run_id"])
            if context is None:
                self._connection.execute("INSERT INTO contexts(context_id,generation) VALUES(?,0)", (context_id,))
                generation = 0
            else:
                generation = context["generation"]
            if self._connection.execute("SELECT 1 FROM runs WHERE context_id=? AND status IN ('running','blocked','attention')", (context_id,)).fetchone():
                raise ConflictError("Context already has an active durable run")
            run_id, now = uuid.uuid4().hex, self._now()
            self._connection.execute(
                """INSERT INTO runs(run_id,context_id,input_id,input_payload,input_digest,generation,
                    phase,status,checkpoint,checkpoint_digest,created_at,updated_at) VALUES(?,?,?,?,?,?,'admitted','running',?,?,?,?)""",
                (run_id, context_id, input_id, self._encode(encoded), _digest(encoded), generation, self._encode(genesis), _digest(genesis), now, now),
            )
            seq = self._event(run_id, "admitted", {"input_id": input_id, "generation": generation})
            self._connection.execute("UPDATE runs SET checkpoint_seq=? WHERE run_id=?", (seq, run_id))
            state = self.get_restore_state()
            if state["required"]:
                self._connection.execute("INSERT INTO restore_selections(run_id,epoch,selected_at) VALUES(?,?,?)", (run_id, state["epoch"], now))
            return self._run(run_id)

    def get_run(self, run_id):
        with self._mutex:
            self._ensure_open()
            return self._run(run_id)

    def matches_input(self, run_id, payload):
        """Compare a retry with its durable digest even after payload retention."""
        _identity(run_id, "run id")
        fingerprint = _digest(_json(payload))
        with self._mutex:
            self._ensure_open()
            row = self._connection.execute("SELECT input_digest FROM runs WHERE run_id=?", (run_id,)).fetchone()
            return row is not None and row["input_digest"] == fingerprint

    def matches_call(self, run_id, call_id, payload):
        """Compare an invocation payload without rehydrating its private data."""
        _identity(run_id, "run id")
        _identity(call_id, "call id")
        _json(payload)
        with self._mutex:
            self._ensure_open()
            row = self._connection.execute("SELECT kind,replay,fingerprint FROM calls WHERE run_id=? AND call_id=?", (run_id, call_id)).fetchone()
            return row is not None and row["fingerprint"] == _digest(_json({"kind": row["kind"], "payload": payload, "replay": row["replay"]}))

    @staticmethod
    def _document_edit(kind, schema_version, expected_revision, value):
        _identity(kind, "document kind")
        if type(schema_version) is not int or schema_version < 1:
            raise ValueError("Document schema version must be a positive integer")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Document revision must be a nonnegative integer")
        encoded = _json(value)
        if len(encoded.encode("utf-8")) > _MAX_DOCUMENT:
            raise ValueError("Document exceeds the 64 KiB limit")
        return {"kind": kind, "schema_version": schema_version,
                "expected_revision": expected_revision, "value": value}

    def _document_edits(self, edits):
        if not isinstance(edits, (tuple, list)) or len(edits) > 100:
            raise ValueError("Document edits must be a bounded list")
        validated, kinds = [], set()
        for edit in edits:
            if type(edit) is not dict or set(edit) != {"kind", "schema_version", "expected_revision", "value"}:
                raise ValueError("Invalid document edit")
            item = self._document_edit(**edit)
            if item["kind"] in kinds:
                raise ValueError("Only one edit per document kind is permitted")
            kinds.add(item["kind"])
            validated.append(item)
        return validated

    def _document_context(self, context_id, expected_generation=None, *, create=False):
        _identity(context_id, "context id")
        if expected_generation is not None and (type(expected_generation) is not int or expected_generation < 0):
            raise ValueError("Context generation must be a nonnegative integer")
        row = self._connection.execute("SELECT * FROM contexts WHERE context_id=?", (context_id,)).fetchone()
        if row is None and create:
            self._connection.execute("INSERT INTO contexts(context_id,generation) VALUES(?,0)", (context_id,))
            row = self._connection.execute("SELECT * FROM contexts WHERE context_id=?", (context_id,)).fetchone()
        if row is None:
            return None
        if row["deleted"] or (expected_generation is not None and row["generation"] != expected_generation):
            raise StaleRunError("Document context was deleted or reset")
        return row

    def _document(self, context_id, kind):
        row = self._connection.execute("SELECT * FROM documents WHERE context_id=? AND kind=?", (context_id, kind)).fetchone()
        if row is None:
            return None
        return dict(row, value=self._read(row["value"], row["digest"], required=True))

    def read_document(self, context_id, kind):
        _identity(context_id, "context id")
        _identity(kind, "document kind")
        with self._mutex:
            self._ensure_open()
            context = self._document_context(context_id)
            if context is None:
                return None
            document = self._document(context_id, kind)
            return dict(document, generation=context["generation"]) if document is not None else None

    def document_generation(self, context_id):
        """App mutations capture a generation even before the first document."""
        with self._mutex:
            self._ensure_open()
            context = self._document_context(context_id)
            return context["generation"] if context is not None else 0

    def _document_problem(self, context_id, edit):
        current = self._connection.execute("SELECT revision,schema_version FROM documents WHERE context_id=? AND kind=?", (context_id, edit["kind"])).fetchone()
        revision = current["revision"] if current else 0
        if revision != edit["expected_revision"]:
            return "revision_conflict", revision
        if current and edit["schema_version"] < current["schema_version"]:
            return "schema_downgrade", revision
        return None, revision

    def _apply_document(self, context, edit, mutation_id, *, run_id=None, call_id=None):
        encoded = _json(edit["value"])
        revision = edit["expected_revision"] + 1
        now = self._now()
        self._connection.execute("""INSERT INTO documents(context_id,kind,schema_version,revision,value,digest,generation,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(context_id,kind) DO UPDATE SET schema_version=excluded.schema_version,
            revision=excluded.revision,value=excluded.value,digest=excluded.digest,generation=excluded.generation,updated_at=excluded.updated_at""",
            (context["context_id"], edit["kind"], edit["schema_version"], revision, self._encode(encoded), _digest(encoded), context["generation"], now))
        self._connection.execute("""INSERT INTO document_events(context_id,kind,revision,schema_version,digest,mutation_id,run_id,call_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", (context["context_id"], edit["kind"], revision, edit["schema_version"], _digest(encoded), mutation_id, run_id, call_id, now))
        return self._document(context["context_id"], edit["kind"])

    def write_document(self, context_id, kind, schema_version, value, expected_revision, mutation_id, expected_generation=None):
        _identity(mutation_id, "document mutation id")
        edit = self._document_edit(kind, schema_version, expected_revision, value)
        fingerprint = _digest(_json({"edit": edit, "expected_generation": expected_generation}))
        with self._transaction():
            context = self._document_context(context_id, expected_generation, create=True)
            old = self._connection.execute("SELECT fingerprint,receipt FROM document_mutations WHERE context_id=? AND mutation_id=?", (context_id, mutation_id)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise ConflictError("Document mutation id already has different content")
                return {**_decode(old["receipt"]), "value": value}
            problem, _ = self._document_problem(context_id, edit)
            if problem:
                raise ConflictError("Document revision or schema changed")
            document = self._apply_document(context, edit, mutation_id)
            receipt = {key: item for key, item in document.items() if key != "value"}
            self._connection.execute("INSERT INTO document_mutations(context_id,mutation_id,fingerprint,receipt) VALUES(?,?,?,?)", (context_id, mutation_id, fingerprint, _json(receipt)))
            return document

    def read_document_events(self, context_id, after=0):
        _identity(context_id, "context id")
        if type(after) is not int or after < 0:
            raise ValueError("Document event sequence must be nonnegative")
        with self._mutex:
            self._ensure_open()
            return [dict(row) for row in self._connection.execute("SELECT * FROM document_events WHERE context_id=? AND seq>? ORDER BY seq", (context_id, after)).fetchall()]

    def _conflicts(self, run_id, call_id=None):
        suffix, parameters = (" AND call_id=?", (run_id, call_id)) if call_id is not None else ("", (run_id,))
        rows = self._connection.execute("SELECT * FROM document_conflicts WHERE run_id=?" + suffix + " ORDER BY created_at,conflict_id", parameters).fetchall()
        run = self._connection.execute("SELECT payloads_pruned FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return [dict(row, proposed=self._read(row["proposed"], row["digest"], required=not (
            run and run["payloads_pruned"] and row["status"] == "resolved"
            and row["proposed"] is None and row["digest"] is None))) for row in rows]

    def list_document_conflicts(self, run_id):
        _identity(run_id, "run id")
        with self._mutex:
            self._ensure_open()
            return self._conflicts(run_id)

    def _stage_documents(self, run, call_id, edits):
        problems = [self._document_problem(run["context_id"], edit) for edit in edits]
        cancelled = run["status"] == "cancelled"
        if cancelled or any(problem for problem, _ in problems):
            for edit, (problem, current) in zip(edits, problems):
                encoded = _json(edit["value"])
                self._connection.execute("""INSERT INTO document_conflicts(conflict_id,run_id,call_id,kind,schema_version,
                    expected_revision,current_revision,proposed,digest,status,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,'pending',?,?)""",
                    (uuid.uuid4().hex, run["run_id"], call_id, edit["kind"], edit["schema_version"], edit["expected_revision"], current,
                     self._encode(encoded), _digest(encoded), "cancelled" if cancelled else problem or "transaction_conflict", self._now()))
            return
        context = self._document_context(run["context_id"], run["generation"])
        for edit in edits:
            self._apply_document(context, edit, f"call:{run['run_id']}:{call_id}:{edit['kind']}", run_id=run["run_id"], call_id=call_id)

    def get_restore_state(self):
        with self._mutex:
            self._ensure_open()
            row = self._connection.execute("SELECT value FROM metadata WHERE key='deployment_epoch'").fetchone()
            if row is None or not isinstance(row["value"], str) or re.fullmatch(r"[a-f0-9]{32}", row["value"]) is None:
                raise IntegrityError("Invalid recovery deployment epoch")
            return {"required": self.requires_restore_review(), "epoch": row["value"]}

    def can_resume(self, run_id):
        _identity(run_id, "run id")
        with self._mutex:
            self._ensure_open()
            row = self._connection.execute("""SELECT r.generation,c.generation AS current_generation,c.deleted
                FROM runs r JOIN contexts c USING(context_id) WHERE r.run_id=?""", (run_id,)).fetchone()
            if row is None or row["deleted"] or row["generation"] != row["current_generation"]:
                return False
            state = self.get_restore_state()
            if not state["required"]:
                return True
            return self._connection.execute("SELECT 1 FROM restore_selections WHERE run_id=? AND epoch=?", (run_id, state["epoch"])).fetchone() is not None

    def _review_run(self, run_id):
        _identity(run_id, "run id")
        row = self._connection.execute("""SELECT r.*,c.generation AS current_generation,c.deleted
            FROM runs r JOIN contexts c USING(context_id) WHERE r.run_id=?""", (run_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown durable run")
        if row["deleted"] or row["generation"] != row["current_generation"]:
            raise StaleRunError("Recovery review belongs to a deleted or reset generation")
        if self._connection.execute("SELECT 1 FROM runs WHERE context_id=? AND run_id!=? AND status IN ('running','blocked','attention')", (row["context_id"], run_id)).fetchone():
            raise StaleRunError("A newer run owns this context")
        return dict(row)

    def get_review(self, run_id):
        _identity(run_id, "run id")
        with self._mutex:
            self._ensure_open()
            row = self._connection.execute("""SELECT r.*,c.generation AS current_generation,c.deleted
                FROM runs r JOIN contexts c USING(context_id) WHERE r.run_id=?""", (run_id,)).fetchone()
            if row is None:
                raise KeyError("Unknown durable run")
            event = self._connection.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE run_id=?", (run_id,)).fetchone()[0]
            context_event = self._connection.execute("SELECT COALESCE(MAX(e.seq),0) FROM events e JOIN runs r ON e.run_id=r.run_id WHERE r.context_id=?", (row["context_id"],)).fetchone()[0]
            document_event = self._connection.execute("SELECT COALESCE(MAX(seq),0) FROM document_events WHERE context_id=?", (row["context_id"],)).fetchone()[0]
            state = self.get_restore_state()
            selected = self.can_resume(run_id)
            version = _digest(_json({"run_id": run_id, "generation": row["current_generation"], "deleted": row["deleted"],
                "status": row["status"], "phase": row["phase"], "event": event, "context_event": context_event, "document_event": document_event,
                "epoch": state["epoch"], "selected": selected, "pruned": row["payloads_pruned"]}))
            conflicts = [item[0] for item in self._connection.execute("SELECT conflict_id FROM document_conflicts WHERE run_id=? AND status='pending' ORDER BY conflict_id", (run_id,)).fetchall()]
            return {"run_id": run_id, "context_id": row["context_id"], "version": version,
                    "generation": row["current_generation"], "run_generation": row["generation"], "deleted": bool(row["deleted"]),
                    "status": row["status"], "phase": row["phase"], "payloads_pruned": bool(row["payloads_pruned"]),
                    "restore_selected": selected, "restore_epoch": state["epoch"], "document_conflicts": conflicts}

    def _check_review(self, run_id, expected_version):
        run = self._review_run(run_id)
        if not isinstance(expected_version, str) or self.get_review(run_id)["version"] != expected_version:
            raise ConflictError("Recovery review is stale")
        return run

    def _request(self, operation, request_id, arguments):
        _identity(request_id, "review request id")
        row = self._connection.execute("SELECT * FROM review_requests WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            return None
        if row["operation"] != operation or row["fingerprint"] != _digest(_json(arguments)):
            raise ConflictError("Review request id already has different content")
        result = _decode(row["result"])
        if result.get("epoch") != self.get_restore_state()["epoch"]:
            raise ConflictError("Review request belongs to another deployment epoch")
        return result

    def _remember_request(self, operation, run_id, request_id, arguments, result):
        self._connection.execute("""INSERT INTO review_requests(request_id,operation,run_id,fingerprint,request,result,created_at)
            VALUES(?,?,?,?,?,?,?)""", (request_id, operation, run_id, _digest(_json(arguments)), _json(arguments), _json(result), self._now()))
        return result

    def get_review_request(self, run_id, request_id):
        _identity(run_id, "run id")
        _identity(request_id, "review request id")
        with self._mutex:
            self._ensure_open()
            row = self._connection.execute("SELECT * FROM review_requests WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                return None
            arguments = _decode(row["request"]) or {}
            if row["run_id"] != run_id and run_id not in arguments.get("run_ids", []):
                return None
            result = _decode(row["result"])
            return {"request_id": request_id, "operation": row["operation"], "fingerprint": row["fingerprint"],
                    "request": arguments, "result": result, "decision": arguments.get("decision", "new_attempt" if row["operation"] == "prepare_retry" else None),
                    "call_id": arguments.get("call_id", arguments.get("logical_call_id")), "note": arguments.get("note"),
                    "note_digest": arguments.get("note_digest", _digest(arguments["note"]) if "note" in arguments else None),
                    "expected_version": arguments.get("expected_version", arguments.get("review_version")),
                    "phase": arguments.get("phase"), "epoch_valid": result.get("epoch") == self.get_restore_state()["epoch"]}

    def list_resolutions(self, run_id):
        _identity(run_id, "run id")
        with self._mutex:
            self._ensure_open()
            return [dict(row) for row in self._connection.execute("SELECT * FROM review_resolutions WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()]

    def record_resolution(self, run_id, expected_version, decision, note, request_id, call_id=None, *, phase=None, context_ids=()):
        _identity(run_id, "run id")
        if decision not in ("stop", "confirmed_completed", "confirmed_not_completed", "resume"):
            raise ValueError("Unknown recovery resolution")
        if not isinstance(note, str) or len(note.encode("utf-8")) > 4096:
            raise ValueError("Recovery evidence note exceeds its limit")
        if call_id is not None:
            _identity(call_id, "call id")
        if phase is not None:
            _identity(phase, "phase")
        if decision == "resume" and phase is None:
            raise ValueError("Resume requires a caller-validated phase")
        if isinstance(context_ids, (str, bytes)):
            raise ValueError("Related contexts must be a collection")
        related = sorted({_identity(item, "context id") for item in context_ids})
        arguments = {"run_id": run_id, "expected_version": expected_version, "decision": decision, "note": note, "call_id": call_id, "phase": phase, "context_ids": related}
        with self._transaction():
            prior = self._request("resolution", request_id, arguments)
            if prior is not None:
                return prior
            run = self._check_review(run_id, expected_version)
            if call_id is not None and self._connection.execute("SELECT 1 FROM calls WHERE run_id=? AND call_id=?", (run_id, call_id)).fetchone() is None:
                raise KeyError("Unknown durable call")
            if decision == "resume":
                if run["status"] not in _ACTIVE or run["payloads_pruned"] or not self.can_resume(run_id):
                    raise StaleRunError("Recovery run is not selected or its payload expired")
            else:
                self._control_rows(list(dict.fromkeys([run["context_id"], *related])), "cancel")
            self._connection.execute("INSERT INTO review_resolutions(run_id,call_id,decision,note,request_id,created_at) VALUES(?,?,?,?,?,?)", (run_id, call_id, decision, note, request_id, self._now()))
            seq = self._event(run_id, "operator_resolution", {"decision": decision, "call_id": call_id, "request_id": request_id, "phase": phase})
            if decision == "resume":
                self._review_phase(run, phase, seq)
            result = {"run_id": run_id, "decision": decision, "call_id": call_id, "version": self.get_review(run_id)["version"],
                      "epoch": self.get_restore_state()["epoch"]}
            return self._remember_request("resolution", run_id, request_id, arguments, result)

    def _review_phase(self, run, phase, sequence):
        checkpoint = self._read(run["checkpoint"], run["checkpoint_digest"], required=True)
        if not isinstance(checkpoint, dict):
            raise IntegrityError("Review continuation requires a checkpoint object")
        checkpoint["paused"] = False
        encoded = _json(checkpoint)
        self._connection.execute("UPDATE runs SET status='running',phase=?,checkpoint=?,checkpoint_digest=?,checkpoint_seq=?,updated_at=? WHERE run_id=?",
                                 (phase, self._encode(encoded), _digest(encoded), sequence, self._now(), run["run_id"]))

    def select_restore(self, run_ids, expected_epoch, versions, request_id):
        if isinstance(run_ids, (str, bytes)):
            raise ValueError("Restore selection requires a run collection")
        selected = sorted({_identity(item, "run id") for item in run_ids})
        if not selected or len(selected) > 1000 or type(versions) is not dict or set(versions) != set(selected):
            raise ValueError("Restore selection requires one review version per run")
        arguments = {"run_ids": selected, "expected_epoch": expected_epoch, "versions": versions}
        with self._transaction():
            state = self.get_restore_state()
            if state["epoch"] != expected_epoch:
                raise ConflictError("Restore deployment epoch changed")
            prior = self._request("restore_selection", request_id, arguments)
            if prior is not None:
                return prior
            for run_id in selected:
                run = self._check_review(run_id, versions[run_id])
                if run["status"] not in _ACTIVE or run["payloads_pruned"]:
                    raise StaleRunError("Only current active runs may be selected")
            for run_id in selected:
                self._connection.execute("INSERT OR REPLACE INTO restore_selections(run_id,epoch,request_id,selected_at) VALUES(?,?,?,?)", (run_id, expected_epoch, request_id, self._now()))
                self._event(run_id, "restore_selected", {"epoch": expected_epoch, "request_id": request_id})
            result = {"epoch": expected_epoch, "run_ids": selected, "versions": {item: self.get_review(item)["version"] for item in selected}}
            return self._remember_request("restore_selection", None, request_id, arguments, result)

    def resolve_document_conflict(self, run_id, conflict_id, decision, expected_revision, review_version=None, mutation_id=None):
        _identity(run_id, "run id")
        _identity(conflict_id, "document conflict id")
        if decision not in ("keep_current", "apply_proposed"):
            raise ValueError("Unknown document conflict resolution")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Document revision must be nonnegative")
        _identity(mutation_id, "document resolution mutation id")
        arguments = {"run_id": run_id, "conflict_id": conflict_id, "decision": decision, "expected_revision": expected_revision, "review_version": review_version}
        with self._transaction():
            prior = self._request("document_resolution", mutation_id, arguments)
            if prior is not None:
                return prior
            run = self._check_review(run_id, review_version) if review_version is not None else self._review_run(run_id)
            conflict = self._connection.execute("SELECT * FROM document_conflicts WHERE run_id=? AND conflict_id=?", (run_id, conflict_id)).fetchone()
            if conflict is None:
                raise KeyError("Unknown document conflict")
            if conflict["status"] != "pending":
                raise ConflictError("Document conflict was already resolved")
            current = self._connection.execute("SELECT revision FROM documents WHERE context_id=? AND kind=?", (run["context_id"], conflict["kind"])).fetchone()
            if (current["revision"] if current else 0) != expected_revision:
                raise ConflictError("Document revision changed during review")
            if decision == "apply_proposed":
                if conflict["reason"] == "cancelled" or run["status"] == "cancelled":
                    raise StaleRunError("Stopped tool edits require a fresh app mutation")
                edit = self._document_edit(conflict["kind"], conflict["schema_version"], expected_revision, self._read(conflict["proposed"], conflict["digest"], required=True))
                problem, _ = self._document_problem(run["context_id"], edit)
                if problem:
                    raise ConflictError("Document schema changed during review")
                context = self._document_context(run["context_id"], run["generation"])
                self._apply_document(context, edit, mutation_id, run_id=run_id, call_id=conflict["call_id"])
            self._connection.execute("UPDATE document_conflicts SET status='resolved',decision=?,resolved_at=? WHERE conflict_id=?", (decision, self._now(), conflict_id))
            self._event(run_id, "document_conflict_resolved", {"conflict_id": conflict_id, "decision": decision})
            result = {"run_id": run_id, "conflict_id": conflict_id, "decision": decision, "version": self.get_review(run_id)["version"],
                      "epoch": self.get_restore_state()["epoch"]}
            return self._remember_request("document_resolution", run_id, mutation_id, arguments, result)

    def get_retry(self, run_id, logical_call_id):
        _identity(run_id, "run id")
        _identity(logical_call_id, "logical call id")
        with self._mutex:
            self._ensure_open()
            row = self._connection.execute("SELECT * FROM retry_grants WHERE run_id=? AND logical_call_id=? ORDER BY seq DESC LIMIT 1", (run_id, logical_call_id)).fetchone()
            if row is None:
                return None
            return dict(row, original_id=row["logical_call_id"], epoch_valid=row["epoch"] == self.get_restore_state()["epoch"])

    def prepare_retry(self, run_id, logical_call_id, expected_version, request_id, phase, *, eligible=False, note=""):
        _identity(run_id, "run id")
        _identity(logical_call_id, "logical call id")
        if eligible is not True:
            raise StaleRunError("Retry requires explicit current eligibility")
        if phase not in ("model_retry", "tools"):
            raise ValueError("Unsupported retry phase")
        if not isinstance(note, str) or len(note.encode("utf-8")) > 4096:
            raise ValueError("Retry evidence note exceeds its limit")
        arguments = {"run_id": run_id, "logical_call_id": logical_call_id, "expected_version": expected_version,
                     "phase": phase, "eligible": eligible, "note": note, "decision": "new_attempt"}
        with self._transaction():
            prior = self._request("prepare_retry", request_id, arguments)
            if prior is not None:
                return prior
            run = self._check_review(run_id, expected_version)
            if run["status"] not in _ACTIVE or run["payloads_pruned"] or not self.can_resume(run_id):
                raise StaleRunError("Retry requires current retained and selected state")
            original = self._call(run_id, logical_call_id)
            if original is None or original["logical_call_id"] is not None or original["kind"] not in ("model", "tool") or original["status"] != "intent":
                raise ConflictError("Only an unresolved logical model or tool call can be retried")
            if original["kind"] == "model" and (not isinstance(original["payload"], dict) or original["payload"].get("retry_eligible") is not True):
                raise StaleRunError("Model call was not recorded as plain inference")
            if phase != ("model_retry" if original["kind"] == "model" else "tools"):
                raise ValueError("Retry phase does not match the invocation kind")
            aliases = self._connection.execute("SELECT status FROM calls WHERE run_id=? AND logical_call_id=?", (run_id, logical_call_id)).fetchall()
            if any(row["status"] != "intent" for row in aliases):
                raise ConflictError("A retry already has a committed outcome")
            if len(aliases) >= 2:
                raise ConflictError("Logical call reached its three-attempt budget")
            pending = self.get_retry(run_id, logical_call_id)
            if pending and pending["state"] == "pending" and pending["epoch_valid"]:
                raise ConflictError("A retry grant is already pending")
            attempt = len(aliases) + 2
            alias = _identity(f"{logical_call_id}:attempt:{attempt}", "retry call id")
            epoch = self.get_restore_state()["epoch"]
            self._connection.execute("INSERT INTO retry_grants(run_id,logical_call_id,call_id,attempt,epoch,state,request_id,created_at) VALUES(?,?,?,?,?,'pending',?,?)", (run_id, logical_call_id, alias, attempt, epoch, request_id, self._now()))
            self._connection.execute("INSERT INTO review_resolutions(run_id,call_id,decision,note,request_id,created_at) VALUES(?,?,'new_attempt',?,?,?)", (run_id, logical_call_id, note, request_id, self._now()))
            seq = self._event(run_id, "retry_granted", {"logical_call_id": logical_call_id, "call_id": alias, "attempt": attempt, "epoch": epoch, "phase": phase})
            self._review_phase(run, phase, seq)
            result = {**self.get_retry(run_id, logical_call_id), "version": self.get_review(run_id)["version"]}
            return self._remember_request("prepare_retry", run_id, request_id, arguments, result)

    def begin_retry(self, run_id, logical_call_id):
        _identity(run_id, "run id")
        _identity(logical_call_id, "logical call id")
        with self._transaction():
            run = self._review_run(run_id)
            grant = self.get_retry(run_id, logical_call_id)
            if grant is None or grant["state"] != "pending" or not grant["epoch_valid"]:
                raise StaleRunError("Retry grant was consumed or belongs to another deployment")
            if run["status"] != "running" or not self.can_resume(run_id):
                raise StaleRunError("Retry run is stopped or not selected")
            original = self._call(run_id, logical_call_id)
            if original is None or original["status"] != "intent" or original["payloads_pruned"]:
                raise ConflictError("Logical invocation is no longer unresolved")
            if self._call(run_id, grant["call_id"]) is not None:
                raise ConflictError("Retry attempt already owns an intent")
            now = self._now()
            self._connection.execute("""INSERT INTO calls(run_id,call_id,kind,payload,fingerprint,replay,status,created_at,updated_at,logical_call_id,attempt)
                VALUES(?,?,?,?,?,?,'intent',?,?,?,?)""", (run_id, grant["call_id"], original["kind"], self._encode(_json(original["payload"])),
                    original["fingerprint"], original["replay"], now, now, logical_call_id, grant["attempt"]))
            self._connection.execute("UPDATE retry_grants SET state='started' WHERE seq=?", (grant["seq"],))
            self._event(run_id, "retry_started", {"logical_call_id": logical_call_id, "call_id": grant["call_id"], "attempt": grant["attempt"]})
            return self._call(run_id, grant["call_id"])

    def list_runs(self, statuses=None):
        with self._mutex:
            self._ensure_open()
            if statuses is None:
                rows = self._connection.execute("SELECT run_id FROM runs ORDER BY created_at,run_id")
            else:
                statuses = tuple(statuses)
                if any(status not in _STATUSES for status in statuses):
                    raise ValueError("Unknown recovery status")
                if not statuses:
                    return []
                placeholders = ",".join("?" for _ in statuses)
                rows = self._connection.execute(f"SELECT run_id FROM runs WHERE status IN ({placeholders}) ORDER BY created_at,run_id", statuses)
            return [self._run(row["run_id"]) for row in rows.fetchall()]

    def list_run_headers(self, statuses=None, context_id=None):
        """Inventory ownership metadata without decoding private recovery payloads."""
        if context_id is not None:
            _identity(context_id, "context id")
        clauses, parameters = [], []
        if statuses is not None:
            statuses = tuple(statuses)
            if any(status not in _STATUSES for status in statuses):
                raise ValueError("Unknown recovery status")
            if not statuses:
                return []
            clauses.append("status IN (" + ",".join("?" for _ in statuses) + ")")
            parameters.extend(statuses)
        if context_id is not None:
            clauses.append("context_id=?")
            parameters.append(context_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._mutex:
            self._ensure_open()
            rows = self._connection.execute(
                "SELECT run_id,context_id,input_id,generation,phase,status,created_at,payloads_pruned FROM runs"
                + where + " ORDER BY created_at,run_id", parameters,
            ).fetchall()
            return [dict(row, payloads_pruned=bool(row["payloads_pruned"])) for row in rows]

    def read_events(self, run_id, after=0):
        _identity(run_id, "run id")
        if type(after) is not int or after < 0:
            raise ValueError("Event sequence must be a nonnegative integer")
        with self._mutex:
            self._ensure_open()
            rows = self._connection.execute("SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after)).fetchall()
            return [dict(row, payload=None if row["payloads_pruned"] else self._read(row["payload"], row["payload_digest"], required=True),
                         payloads_pruned=bool(row["payloads_pruned"])) for row in rows]

    def transition(self, run_id, phase, checkpoint=None, status="running", payload=None):
        _identity(phase, "phase")
        if status not in _STATUSES:
            raise ValueError("Unknown recovery status")
        encoded = None if checkpoint is None else _json(checkpoint)
        _json(payload)
        with self._transaction():
            self._writable(run_id)
            seq = self._event(run_id, "transition", {"phase": phase, "status": status, "detail": payload})
            if encoded is None:
                self._connection.execute("UPDATE runs SET phase=?,status=?,updated_at=? WHERE run_id=?", (phase, status, self._now(), run_id))
            else:
                self._connection.execute("UPDATE runs SET phase=?,status=?,checkpoint=?,checkpoint_digest=?,checkpoint_seq=?,updated_at=? WHERE run_id=?", (phase, status, self._encode(encoded), _digest(encoded), seq, self._now(), run_id))
            return self._run(run_id)

    def _call(self, run_id, call_id):
        row = self._connection.execute("SELECT * FROM calls WHERE run_id=? AND call_id=?", (run_id, call_id)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payloads_pruned"] = bool(result["payloads_pruned"])
        result["document_conflicts"] = self._conflicts(run_id, call_id)
        result["original_id"] = result["logical_call_id"] or result["call_id"]
        if result["payloads_pruned"]:
            result["payload"] = result["result"] = None
            return result
        # Fingerprint includes kind/replay and therefore requires canonical rebuild.
        if row["payload"] is None:
            raise IntegrityError("Recovery call is missing its payload")
        payload = self._read(row["payload"])
        if not isinstance(row["fingerprint"], str) or not _BLOB_DIGEST.fullmatch(row["fingerprint"]) or _digest(_json({"kind": row["kind"], "payload": payload, "replay": row["replay"]})) != row["fingerprint"]:
            raise IntegrityError("Recovery call integrity check failed")
        result["payload"] = payload
        absent_intent = row["status"] == "intent" and row["result"] is None and row["result_digest"] is None
        result["result"] = self._read(row["result"], row["result_digest"], required=not absent_intent)
        return result

    def start_call(self, run_id, call_id, kind, payload, replay="never"):
        _identity(run_id, "run id")
        _identity(call_id, "call id")
        _identity(kind, "call kind")
        if replay not in ("never", "safe"):
            raise ValueError("Unknown replay policy")
        encoded = _json(payload)
        fingerprint = _digest(_json({"kind": kind, "payload": payload, "replay": replay}))
        with self._transaction():
            self._writable(run_id)
            existing = self._call(run_id, call_id)
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise ConflictError("Call identity already has different content")
                return existing
            now = self._now()
            self._connection.execute("INSERT INTO calls(run_id,call_id,kind,payload,fingerprint,replay,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'intent',?,?)", (run_id, call_id, kind, self._encode(encoded), fingerprint, replay, now, now))
            self._event(run_id, "call_intent", {"call_id": call_id, "kind": kind, "replay": replay})
            return self._call(run_id, call_id)

    def finish_call(self, run_id, call_id, result, *, checkpoint=None, phase=None, document_edits=()):
        _identity(run_id, "run id")
        _identity(call_id, "call id")
        encoded = _json(result)
        edits = self._document_edits(document_edits)
        edits_digest = _digest(_json(edits))
        projection = None if checkpoint is None else _json(checkpoint)
        if phase is not None:
            _identity(phase, "phase")
        with self._transaction():
            run = self._writable(run_id, allow_cancelled=True)
            call = self._call(run_id, call_id)
            if call is None:
                raise KeyError("Unknown durable call")
            if run["status"] == "cancelled" and (projection is not None or phase is not None):
                raise StaleRunError("Stopped runs only accept late body outcomes")
            if call["status"] == "completed":
                if call["result_digest"] != _digest(encoded):
                    raise ConflictError("Call outcome already has different content")
                if call["document_edits_digest"] not in (edits_digest, None) or (call["document_edits_digest"] is None and edits):
                    raise ConflictError("Call document edits already have different content")
                return call
            self._stage_documents(run, call_id, edits)
            self._connection.execute("UPDATE calls SET status='completed',result=?,result_digest=?,document_edits_digest=?,updated_at=? WHERE run_id=? AND call_id=?", (self._encode(encoded), _digest(encoded), edits_digest, self._now(), run_id, call_id))
            seq = self._event(run_id, "call_result", {"call_id": call_id, "phase": phase, "checkpoint": projection is not None})
            if projection is not None:
                self._connection.execute("UPDATE runs SET checkpoint=?,checkpoint_digest=?,checkpoint_seq=?,phase=?,updated_at=? WHERE run_id=?", (self._encode(projection), _digest(projection), seq, phase or run["phase"], self._now(), run_id))
            elif phase is not None:
                self._connection.execute("UPDATE runs SET phase=?,updated_at=? WHERE run_id=?", (phase, self._now(), run_id))
            return self._call(run_id, call_id)

    def get_call(self, run_id, call_id):
        _identity(run_id, "run id")
        _identity(call_id, "call id")
        with self._mutex:
            self._ensure_open()
            return self._call(run_id, call_id)

    def calls(self, run_id):
        _identity(run_id, "run id")
        with self._mutex:
            self._ensure_open()
            rows = self._connection.execute("SELECT call_id FROM calls WHERE run_id=? ORDER BY created_at,call_id", (run_id,)).fetchall()
            return [self._call(run_id, row["call_id"]) for row in rows]

    def garbage_collect(self):
        """Remove only unreachable blobs and abandoned unpublished blob files.

        Reference inspection and removal share the writer mutex. A failed SQL
        transaction may leave an unreferenced published file, never a reference
        to bytes which have not been published and fsynced.
        """
        removed, removed_bytes = 0, 0
        with self._transaction():
            reachable = self._referenced_blobs()
            _private_path(self.blob_root, directory=True)
            if self.blob_root.exists():
                for path in self.blob_root.iterdir():
                    digest = path.name[:-5] if path.name.endswith(".json") else ""
                    if _BLOB_DIGEST.fullmatch(digest):
                        if digest in reachable:
                            continue
                    elif not path.name.startswith(".pending-"):
                        continue
                    _private_path(path)
                    size = path.stat().st_size
                    path.unlink()
                    removed += 1
                    removed_bytes += size
                self._sync_directory(self.blob_root)
            rows = self._connection.execute("SELECT digest FROM blobs").fetchall()
            for row in rows:
                if row["digest"] not in reachable:
                    self._connection.execute("DELETE FROM backup_blobs WHERE digest=?", (row["digest"],))
                    self._connection.execute("DELETE FROM blobs WHERE digest=?", (row["digest"],))
        return {"blobs_removed": removed, "bytes_removed": removed_bytes}

    def compact(self, *, retain_terminal=100, max_age_days=30, protected_run_ids=()):
        """Prune old settled payloads, preserving dedupe and unresolved evidence.

        The count and age limits apply only to terminal runs without pending
        calls. Workflow adapters can protect completion/join projection sources
        until their own receipts are committed. No active or unresolved run is
        pruned, regardless of age or these limits. Identity metadata is retained.
        """
        if type(retain_terminal) is not int or retain_terminal < 0:
            raise ValueError("Terminal retention must be a nonnegative integer")
        if max_age_days is not None and (type(max_age_days) not in (int, float)
                                        or not math.isfinite(max_age_days) or max_age_days < 0):
            raise ValueError("Retention age must be nonnegative days or None")
        protected = {_identity(run_id, "protected run id") for run_id in protected_run_ids}
        cutoff = None if max_age_days is None else self._now() - max_age_days * 86400
        counts = {"runs_pruned": 0, "calls_pruned": 0, "events_pruned": 0}
        with self._transaction():
            eligible = self._connection.execute("""
                SELECT run_id,updated_at FROM runs
                WHERE status IN ('completed','cancelled','failed') AND payloads_pruned=0
                AND NOT EXISTS(SELECT 1 FROM calls WHERE calls.run_id=runs.run_id AND calls.status!='completed')
                AND NOT EXISTS(SELECT 1 FROM document_conflicts WHERE document_conflicts.run_id=runs.run_id AND document_conflicts.status='pending')
                ORDER BY updated_at DESC,run_id
            """).fetchall()
            eligible = [row for row in eligible if row["run_id"] not in protected]
            for index, row in enumerate(eligible):
                if index < retain_terminal and (cutoff is None or row["updated_at"] >= cutoff):
                    continue
                run_id = row["run_id"]
                self._connection.execute("UPDATE runs SET input_payload=NULL,checkpoint=NULL,checkpoint_digest=NULL,payloads_pruned=1 WHERE run_id=?", (run_id,))
                calls = self._connection.execute("UPDATE calls SET payload=NULL,result=NULL,payloads_pruned=1 WHERE run_id=? AND payloads_pruned=0", (run_id,)).rowcount
                events = self._connection.execute("UPDATE events SET payload=NULL,payloads_pruned=1 WHERE run_id=? AND payloads_pruned=0", (run_id,)).rowcount
                self._connection.execute("UPDATE document_conflicts SET proposed=NULL,digest=NULL WHERE run_id=? AND status!='pending'", (run_id,))
                self._connection.execute("UPDATE review_resolutions SET note=NULL WHERE run_id=?", (run_id,))
                for request in self._connection.execute("SELECT request_id,request FROM review_requests WHERE run_id=? AND request IS NOT NULL", (run_id,)).fetchall():
                    metadata = _decode(request["request"])
                    if "note" in metadata:
                        metadata["note_digest"] = _digest(metadata.pop("note"))
                        self._connection.execute("UPDATE review_requests SET request=? WHERE request_id=?", (_json(metadata), request["request_id"]))
                counts["runs_pruned"] += 1
                counts["calls_pruned"] += calls
                counts["events_pruned"] += events
        counts.update(self.garbage_collect())
        if counts["runs_pruned"]:
            self._reclaim_pages()
        return counts

    def _reclaim_pages(self):
        with self._mutex:
            try:
                self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._connection.execute("VACUUM")
                self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._check_files()
                self._sync_directory(self.root)
            except sqlite3.Error as exc:
                raise DurableStoreError("Recovery payload cleanup failed") from exc

    def control(self, context_id, action="cancel"):
        return self.control_many([context_id], action)[0]

    def control_many(self, context_ids, action="cancel"):
        """Fence an entire parent/child control decision in one transaction."""
        if action not in ("cancel", "reset", "delete"):
            raise ValueError("Unknown recovery control")
        if isinstance(context_ids, (str, bytes)):
            raise ValueError("Batch control requires a collection of context IDs")
        context_ids = list(dict.fromkeys(_identity(context_id, "context id") for context_id in context_ids))
        with self._transaction():
            updated = self._control_rows(context_ids, action)
        if action == "delete":
            # secure_delete clears live pages; checkpoint and vacuum also remove WAL
            # and freed-page copies. No other process can own this store meanwhile.
            self.garbage_collect()
            self._reclaim_pages()
        return updated

    def _control_rows(self, context_ids, action):
        """Transaction-internal control shared with versioned operator decisions."""
        updated = []
        for context_id in context_ids:
            context = self._connection.execute("SELECT * FROM contexts WHERE context_id=?", (context_id,)).fetchone()
            if context is None:
                self._connection.execute("INSERT INTO contexts(context_id,generation,deleted) VALUES(?,0,?)", (context_id, int(action == "delete")))
            elif not context["deleted"]:
                self._connection.execute("UPDATE contexts SET generation=generation+?,deleted=? WHERE context_id=?", (int(action != "cancel"), int(action == "delete"), context_id))
            runs = self._connection.execute("SELECT run_id,status FROM runs WHERE context_id=?", (context_id,)).fetchall()
            for run in runs:
                if run["status"] in _ACTIVE:
                    self._event(run["run_id"], action)
                    self._connection.execute("UPDATE runs SET status='cancelled',phase=?,updated_at=? WHERE run_id=?", (action, self._now(), run["run_id"]))
                if action == "delete":
                    self._connection.execute("UPDATE runs SET input_payload=NULL,input_digest=NULL,checkpoint=NULL,checkpoint_digest=NULL,payloads_pruned=1 WHERE run_id=?", (run["run_id"],))
                    self._connection.execute("UPDATE events SET payload=NULL,payload_digest=NULL,payloads_pruned=1 WHERE run_id=?", (run["run_id"],))
                    self._connection.execute("UPDATE calls SET payload=NULL,fingerprint=NULL,result=NULL,result_digest=NULL,document_edits_digest=NULL,payloads_pruned=1 WHERE run_id=?", (run["run_id"],))
                    for table in ("document_conflicts", "review_resolutions", "review_requests", "restore_selections", "retry_grants"):
                        self._connection.execute(f"DELETE FROM {table} WHERE run_id=?", (run["run_id"],))
                    # Batch-selection receipts have no single owning run. Drop
                    # a shared receipt when any referenced context is deleted.
                    self._connection.execute("DELETE FROM review_requests WHERE operation='restore_selection' AND (instr(COALESCE(request,''),?)>0 OR instr(result,?)>0)", (run["run_id"], run["run_id"]))
            if action == "delete":
                for table in ("documents", "document_events", "document_mutations"):
                    self._connection.execute(f"DELETE FROM {table} WHERE context_id=?", (context_id,))
            updated.append(dict(self._connection.execute("SELECT * FROM contexts WHERE context_id=?", (context_id,)).fetchone()))
        return updated

    def backup(self, destination: Path):
        destination = Path(os.path.abspath(destination))
        _private_path(destination.parent, directory=True, create=True)
        _private_path(destination)
        with self._mutex:
            self._ensure_open()
            if destination.exists():
                raise FileExistsError(destination)
            descriptor, temporary_name = tempfile.mkstemp(prefix=".durable-backup-", suffix=".sqlite3", dir=destination.parent)
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                target = sqlite3.connect(temporary, isolation_level=None)
                try:
                    self._connection.backup(target)
                    target.execute("PRAGMA journal_mode=DELETE")
                    target.execute("PRAGMA synchronous=FULL")
                    target.execute("BEGIN IMMEDIATE")
                    target.execute("DELETE FROM backup_blobs")
                    for digest in sorted(self._referenced_blobs()):
                        target.execute("INSERT INTO backup_blobs(digest,data) VALUES(?,?)", (digest, self._blob_bytes(digest)))
                    # A restored snapshot must never silently become a driver of
                    # historical active work. No API clears this pilot marker.
                    target.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('restore_requires_review','true')")
                    target.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('deployment_epoch',?)", (uuid.uuid4().hex,))
                    target.execute("DELETE FROM restore_selections")
                    target.execute("COMMIT")
                finally:
                    target.close()
                with temporary.open("rb") as snapshot:
                    os.fsync(snapshot.fileno())
                # Publish only the complete, inert snapshot. A link is atomic and
                # refuses a concurrently-created destination instead of replacing it.
                os.link(temporary, destination)
                temporary.unlink()
                self._sync_directory(destination.parent)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        return destination

    def requires_restore_review(self):
        """Whether this root was restored from an inert, review-required backup."""
        with self._mutex:
            self._ensure_open()
            row = self._connection.execute("SELECT value FROM metadata WHERE key='restore_requires_review'").fetchone()
            if row is None:
                return False
            if row["value"] != "true":
                raise IntegrityError("Invalid recovery backup review marker")
            return True

    @staticmethod
    def _sync_directory(path):
        if os.name != "nt":
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def close(self):
        with self._mutex:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            if self._lock_file is not None:
                self._lock_file.close()
                self._lock_file = None

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, *_):
        self.close()
