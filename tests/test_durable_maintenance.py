"""Encrypted owner routing and crash-safe shared cleanup use a disposable DB."""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from types import SimpleNamespace
import threading
import uuid

import pytest

from helpers.durable import codec, maintenance
from helpers.durable.postgres import PostgresStore
from helpers.durable.store import ConflictError, DurableStoreError


@pytest.fixture
def backend(monkeypatch):
    dsn = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Requires disposable PostgreSQL")
    import psycopg
    from psycopg import sql
    from cryptography.fernet import Fernet
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(codec, "masked", lambda agent, value: value)
    namespace = "maintenance_" + uuid.uuid4().hex
    stores = [PostgresStore(dsn, namespace=namespace, worker_id=name) for name in ("first", "second")]
    owners = [SimpleNamespace(sync=lambda method, *args, _store=store, **kwargs: getattr(_store, method)(*args, **kwargs),
                              store=store, distributed=True) for store in stores]
    try:
        yield SimpleNamespace(first=owners[0], second=owners[1])
    finally:
        for store in stores:
            store.close()
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))


def context(identity="context", model=None, opt_out=False):
    ctx = SimpleNamespace(id=identity, data={})
    ctx.get_data = lambda key: ctx.data.get(key)
    ctx.agent0 = SimpleNamespace(context=ctx, data={}, get_chat_model=lambda: model)
    if opt_out:
        ctx.agent0.data["responses_delete_on_chat_delete"] = False
    return ctx


def admit(owner, ctx, *, result_id=None, origin=None):
    descriptor = maintenance.provider_descriptor(ctx.agent0)
    checkpoint = {"context": {"id": ctx.id, "data": dict(ctx.data), "agents": [{"data": dict(ctx.agent0.data), "history": "[]"}]},
                  "environment": {"provider_cleanup": descriptor}, "origin": origin}
    run = owner.sync("admit", ctx.id, "input", {}, checkpoint)
    owner.sync("claim", run["run_id"])
    if result_id:
        owner.sync("start_call", run["run_id"], "model:0", "model", {"provider_cleanup": descriptor})
        owner.sync("finish_call", run["run_id"], "model:0", {"mode": "responses", "response_id": result_id,
                   "provider_model_key": descriptor["model"] if descriptor else ""})
    owner.sync("transition", run["run_id"], "completed", checkpoint=checkpoint, status="completed")
    owner.sync("release", run["run_id"])
    return owner.sync("get_run", run["run_id"])


def queue(owner, run, kind="maintenance_document", value=None, request_id="request"):
    info = maintenance.metadata(owner, run["context_id"], run["run_id"])
    arguments = {"generation": info["generation"], "epoch": info["epoch"], "version": info["version"]}
    value = value if value is not None else {"kind": "todo", "value": {"title": "private-draft", "items": []}, "expected_revision": 0}
    receipt = maintenance.enqueue(owner, run["context_id"], run["run_id"], kind, value, request_id, **arguments)
    return receipt, arguments, value


def test_idle_document_update_is_encrypted_claimed_and_cas_ack_atomic(backend, monkeypatch):
    ctx = context()
    run = admit(backend.first, ctx)
    receipt, arguments, value = queue(backend.second, run)
    assert receipt["queued"]
    row = backend.first.store._connection.execute("SELECT payload FROM commands").fetchone()["payload"]
    assert "private-draft" not in row
    body = bytes(backend.first.store._connection.execute("SELECT body FROM resource_objects").fetchone()["body"])
    assert b"private-draft" not in body
    assert backend.first.sync("list_command_runs", maintenance.KINDS)[0]["run_id"] == run["run_id"]
    assert backend.first.sync("claim_maintenance", run["run_id"])
    invoked = []
    def restore(row):
        assert backend.second.sync("owns", row["run_id"])
        invoked.append(row["run_id"])
        return ctx
    assert asyncio.run(maintenance.process(backend.second, run["run_id"], restore))["pending"]
    assert invoked == []  # A live owner prevents even policy construction.
    backend.first.sync("release", run["run_id"])
    original = backend.second.store.ack_command
    def cut(*args, **kwargs):
        raise DurableStoreError("process ended after document CAS before ack")
    monkeypatch.setattr(backend.second.store, "ack_command", cut)
    with pytest.raises(DurableStoreError):
        asyncio.run(maintenance.process(backend.second, run["run_id"], restore))
    assert backend.first.sync("read_document", ctx.id, "todo") is None
    monkeypatch.setattr(backend.second.store, "ack_command", original)
    assert asyncio.run(maintenance.process(backend.second, run["run_id"], restore))["processed"] == 1
    assert backend.first.sync("read_document", ctx.id, "todo")["value"]["title"] == "private-draft"
    repeated = maintenance.enqueue(backend.first, ctx.id, run["run_id"], "maintenance_document", value, "request", **arguments)
    assert not repeated["queued"] and repeated["command"]["state"] == "applied"
    assert backend.first.sync("get_run", run["run_id"])["status"] == "completed"
    backend.first.sync("compact", retain_terminal=0, max_age_days=0)
    pruned = backend.second.sync("get_command", run["run_id"], "request")
    assert pruned["payload"] is None and pruned["result"] == {"accepted": True}
    assert maintenance.enqueue(backend.second, ctx.id, run["run_id"], "maintenance_document",
        value, "request", **arguments)["command"]["state"] == "applied"


def test_reset_invalidates_queued_draft_and_pending_ref_survives_gc(backend):
    ctx = context()
    run = admit(backend.first, ctx)
    queue(backend.second, run)
    assert backend.first.sync("collect_resources", 0)["resources_removed"] == 0
    backend.first.sync("control", ctx.id, "reset")
    command = backend.first.sync("get_command", run["run_id"], "request")
    assert command["status"] == "invalidated" and command["payload"] is None
    assert backend.first.sync("list_command_runs", maintenance.KINDS) == []
    assert backend.first.sync("read_document", ctx.id, "todo") is None


def test_unsent_chat_gets_one_inert_maintenance_anchor_without_execution(backend):
    ctx = context("unsent")
    seed = {"context": {"id": ctx.id, "data": {}, "agents": [{"data": {}, "history": "[]"}]},
            "environment": {"provider_cleanup": None}}
    backend.first.sync("put_projection", "genesis:" + ctx.id, seed, 0)
    first = maintenance.metadata(backend.first, ctx.id)
    assert maintenance.metadata(backend.second, ctx.id) == first
    run = backend.first.sync("get_run", first["run_id"])
    assert run["status"] == "completed" and run["checkpoint"] == seed
    assert backend.first.sync("calls", run["run_id"]) == []
    assert not backend.first.sync("owns", run["run_id"])
    queue(backend.second, run)
    assert asyncio.run(maintenance.process(backend.first, run["run_id"], lambda _: ctx))["processed"] == 1
    assert backend.second.sync("read_document", ctx.id, "todo")["revision"] == 1


@contextmanager
def provider_server():
    seen, removed = [], set()
    class Handler(BaseHTTPRequestHandler):
        def do_DELETE(self):
            seen.append((self.path, self.headers.get("Authorization")))
            status = 404 if self.path in removed else 200
            removed.add(self.path)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"id":"synthetic","object":"response.deleted","deleted":true}' if status == 200 else b'{"error":{"message":"absent","type":"not_found"}}')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", seen
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_known_provider_delete_survives_lost_ack_and_keeps_sanitized_receipt_after_scrub(backend, monkeypatch):
    from models import LiteLLMChatWrapper
    with provider_server() as (url, seen):
        model = LiteLLMChatWrapper("gpt-synthetic", "openai", api_base=url, api_key="synthetic-account-key")
        ctx = context(model=model)
        run = admit(backend.first, ctx, result_id="resp-private")
        receipt, arguments, value = queue(backend.first, run, "maintenance_delete", {})
        original = backend.first.store.finish_maintenance_effect
        def cut(*args, **kwargs):
            raise DurableStoreError("external DELETE completed before receipt")
        monkeypatch.setattr(backend.first.store, "finish_maintenance_effect", cut)
        with pytest.raises(DurableStoreError):
            asyncio.run(maintenance.process(backend.first, run["run_id"], lambda row: ctx))
        assert len(seen) == 1
        assert backend.second.sync("get_call", run["run_id"], "model:0")["result"]["response_id"] == "resp-private"
        monkeypatch.setattr(backend.first.store, "finish_maintenance_effect", original)
        asyncio.run(maintenance.process(backend.second, run["run_id"], lambda row: ctx))
        assert seen == [("/v1/responses/resp-private", "Bearer synthetic-account-key")] * 2
        assert backend.first.sync("get_call", run["run_id"], "model:0")["result"] is None
        result = maintenance.enqueue(backend.first, ctx.id, run["run_id"], "maintenance_delete", value, "request", **arguments)
        assert not result["queued"] and result["command"]["state"] == "applied"
        stored = backend.first.sync("get_command", run["run_id"], "request")
        assert stored["payload"] is None and stored["result"] == {"accepted": True, "deleted": True, "unresolved_provider_calls": 0}
        backend.first.sync("compact", retain_terminal=0, max_age_days=0)
        assert backend.second.sync("get_command", run["run_id"], "request")["result"] == stored["result"]
        assert backend.first.store._connection.execute("SELECT COUNT(*) AS count FROM resource_objects").fetchone()["count"] == 0


def test_opt_out_deletes_owned_descendants_without_provider_calls(backend, monkeypatch):
    parent, child = context("parent", opt_out=True), context("child", opt_out=True)
    root = admit(backend.first, parent)
    descendant = admit(backend.first, child, origin={"kind": "child", "mode": "subordinate", "parent_run_id": root["run_id"],
        "parent_context_id": parent.id, "parent_agent_number": 0, "parent_call_id": "tool:0:0", "index": 0})
    queue(backend.second, root, "maintenance_delete", {})
    monkeypatch.setattr(maintenance, "_delete_target", lambda *args: pytest.fail("opted out provider called"))
    contexts = {parent.id: parent, child.id: child}
    backend.first.sync("claim_maintenance", descendant["run_id"])
    assert asyncio.run(maintenance.process(backend.second, root["run_id"], lambda row: contexts[row["context_id"]]))["pending"]
    with pytest.raises(ConflictError):
        backend.first.sync("admit", child.id, "unrelated-new-input", {}, {})
    backend.first.sync("release", descendant["run_id"])
    asyncio.run(maintenance.process(backend.second, root["run_id"], lambda row: contexts[row["context_id"]]))
    for run in (root, descendant):
        assert backend.first.sync("get_run", run["run_id"])["payloads_pruned"]


def test_provider_target_change_and_failure_keep_private_outcomes_and_reject_safely(backend, monkeypatch):
    from models import LiteLLMChatWrapper
    model = LiteLLMChatWrapper("gpt-synthetic", "openai", api_base="https://synthetic.invalid/v1", api_key="original-key")
    ctx = context(model=model)
    run = admit(backend.first, ctx, result_id="resp-private")
    queue(backend.second, run, "maintenance_delete", {})
    model.kwargs["api_key"] = "different-account-key"
    monkeypatch.setattr(maintenance, "_delete_target", lambda *args: pytest.fail("changed account contacted"))
    asyncio.run(maintenance.process(backend.second, run["run_id"], lambda row: ctx))
    receipt = backend.first.sync("get_command", run["run_id"], "request")
    assert receipt["result"] == {"accepted": False, "error": "maintenance_rejected"}
    assert backend.first.sync("get_call", run["run_id"], "model:0")["result"]["response_id"] == "resp-private"
    model.kwargs["api_key"] = "original-key"
    queue(backend.second, backend.first.sync("get_run", run["run_id"]), "maintenance_delete", {}, "retry-request")
    def provider_failure(*args):
        raise maintenance.MaintenanceHeld("private provider error text")
    monkeypatch.setattr(maintenance, "_delete_target", provider_failure)
    asyncio.run(maintenance.process(backend.second, run["run_id"], lambda row: ctx))
    failed = backend.first.sync("get_command", run["run_id"], "retry-request")
    assert failed["result"] == {"accepted": False, "error": "maintenance_rejected"}
    assert backend.first.sync("get_run", run["run_id"])["payloads_pruned"] is False


@pytest.mark.parametrize("obstacle", ["none", "claim", "role", "job"])
def test_protocol2_upgrade_requires_quiescent_owners_and_jobs(backend, obstacle):
    from helpers.durable.store import OwnershipError
    ctx = context()
    run = admit(backend.first, ctx)
    if obstacle in ("claim", "job"):
        backend.first.sync("claim_maintenance", run["run_id"])
    if obstacle == "role":
        backend.first.sync("try_role", "scheduler")
    if obstacle == "job":
        backend.first.sync("register_resource_job", run["run_id"], "submitted-job", "f" * 64, "a" * 64)
        backend.first.sync("release", run["run_id"])
    backend.second.store._connection.execute("UPDATE backend_metadata SET value='2' WHERE key='protocol'")
    try:
        if obstacle == "none":
            upgraded = PostgresStore(os.environ["A0_TEST_DURABILITY_POSTGRES_DSN"], namespace=backend.first.store.namespace)
            assert upgraded._connection.execute("SELECT value FROM backend_metadata WHERE key='protocol'").fetchone()["value"] == "3"
            upgraded.close()
        else:
            with pytest.raises(OwnershipError, match="Stop all recovery workers and settle"):
                PostgresStore(os.environ["A0_TEST_DURABILITY_POSTGRES_DSN"], namespace=backend.first.store.namespace)
            assert backend.second.store._connection.execute("SELECT value FROM backend_metadata WHERE key='protocol'").fetchone()["value"] == "2"
    finally:
        backend.second.store._connection.execute("UPDATE backend_metadata SET value='3' WHERE key='protocol'")


def test_conflict_reconciliation_is_owner_routed_and_never_replays_known_body(backend):
    ctx = context()
    checkpoint = {"context": {"id": ctx.id, "data": {}, "agents": [{"data": {}, "history": "[]"}]}}
    run = backend.first.sync("admit", ctx.id, "conflict-input", {}, checkpoint)
    backend.first.sync("claim", run["run_id"])
    backend.first.sync("start_call", run["run_id"], "tool:0:0", "tool", {})
    backend.first.sync("write_document", ctx.id, "todo", 1, {"title": "concurrent app", "items": []}, 0, "app-mutation")
    body = backend.first.sync("finish_call", run["run_id"], "tool:0:0", {"external": "already completed"},
        document_edits=({"kind": "todo", "schema_version": 1, "expected_revision": 0,
                         "value": {"title": "proposed tool edit", "items": []}},))
    conflict = backend.first.sync("list_document_conflicts", run["run_id"])[0]
    backend.first.sync("release", run["run_id"])
    queue(backend.second, run, "maintenance_conflict", {"conflict_id": conflict["conflict_id"],
          "decision": "apply_proposed", "expected_revision": 1})
    asyncio.run(maintenance.process(backend.second, run["run_id"], lambda row: ctx))
    document = backend.first.sync("read_document", ctx.id, "todo")
    assert document["revision"] == 2 and document["value"]["title"] == "proposed tool edit"
    assert backend.first.sync("get_call", run["run_id"], "tool:0:0")["result"] == body["result"]
    assert len(backend.first.sync("calls", run["run_id"])) == 1
    assert backend.first.sync("get_command", run["run_id"], "request")["result"] == {"accepted": True}


def test_shared_memory_patch_is_encrypted_atomic_and_idempotent_across_workers(backend, monkeypatch):
    from plugins._memory.helpers import durable_memory as memory
    from helpers.durable.store import OwnershipError
    scope = 'projects/synthetic'
    identity = {'provider': 'synthetic', 'model': 'fixed', 'dimension': 2}
    original = {'id': 'one', 'text': 'private remembered fact', 'metadata': {'id': 'one', 'area': 'main'}, 'vector': [1.0, 0.0]}
    patch = {'upsert': [original], 'delete': []}
    with pytest.raises(OwnershipError):
        memory.apply_patch(backend.first, scope, 0, 'insert', patch, identity=identity)
    receipt = memory.apply_patch(backend.first, scope, 0, 'insert', patch, identity=identity, control=True)
    assert memory.apply_patch(backend.second, scope, 0, 'insert', patch, identity=identity, control=True) == receipt
    assert memory.get_snapshot(backend.second, scope)['documents'] == [original]
    rows = backend.first.store._connection.execute('SELECT value FROM projections').fetchall()
    assert 'private remembered fact' not in str(rows)
    updated = {**original, 'id': 'two', 'metadata': {'id': 'two'}, 'vector': [0.0, 1.0]}
    replacement = {'upsert': [updated], 'delete': ['one']}
    save = backend.first.store.put_projection
    def crash(key, value, version):
        if key.startswith('memory-op:'):
            raise RuntimeError('Cut after index replacement before receipt')
        return save(key, value, version)
    monkeypatch.setattr(backend.first.store, 'put_projection', crash)
    with pytest.raises(RuntimeError):
        memory.apply_patch(backend.first, scope, 1, 'replace', replacement, control=True)
    assert memory.get_snapshot(backend.second, scope)['documents'] == [original]
    monkeypatch.setattr(backend.first.store, 'put_projection', save)
    memory.apply_patch(backend.second, scope, 1, 'replace', replacement, control=True)
    assert memory.get_snapshot(backend.first, scope)['documents'] == [updated]
    with pytest.raises(ConflictError):
        memory.apply_patch(backend.first, scope, 1, 'stale', {'upsert': [], 'delete': ['two']}, control=True)


def test_shared_memory_framework_bridge_rebuilds_real_faiss_without_reembedding(backend, monkeypatch, tmp_path):
    from plugins._memory.helpers import durable_memory
    from plugins._memory.helpers.memory import Memory
    from helpers.durable import runtime
    from langchain_core.embeddings import Embeddings
    class Embedder(Embeddings):
        def __init__(self):
            self.documents = []
        def embed_documents(self, texts):
            self.documents.extend(texts)
            return [[1., 0.] for _ in texts]
        def embed_query(self, text):
            return [1., 0.]
    embedding = Embedder()
    monkeypatch.setattr('models.get_embedding_model', lambda *args, **kwargs: embedding)
    monkeypatch.setattr(Memory, '_get_embedding_config', lambda agent=None: SimpleNamespace(provider='synthetic', name='fixed', build_kwargs=lambda: {}))
    monkeypatch.setattr('plugins._memory.helpers.memory.abs_db_dir', lambda scope: str(tmp_path / scope))
    monkeypatch.setattr(Memory, 'index', {})
    monkeypatch.setattr(runtime, '_service', backend.first)
    first = asyncio.run(Memory.get_by_subdir('shared', preload_knowledge=False))
    identifier = asyncio.run(first.insert_text('cross host memory'))
    assert embedding.documents == ['cross host memory']
    monkeypatch.setattr(runtime, '_service', backend.second)
    second = asyncio.run(Memory.get_by_subdir('shared', preload_knowledge=False))
    assert second.get_document_by_id(identifier).page_content == 'cross host memory'
    docs = asyncio.run(second.search_similarity_threshold('anything', 5, 0., embedding=[1., 0.]))
    assert [doc.metadata['id'] for doc in docs] == [identifier]
    assert embedding.documents == ['cross host memory']
    asyncio.run(second.delete_documents_by_ids([identifier]))
    assert durable_memory.get_snapshot(backend.first, 'shared')['documents'] == []
    with pytest.raises(ConflictError):
        asyncio.run(first.insert_text('stale writer'))
    assert durable_memory.get_snapshot(backend.second, 'shared')['documents'] == []


def test_shared_knowledge_preload_is_atomic_and_survives_a_joining_host_without_files(backend, monkeypatch, tmp_path):
    from plugins._memory.helpers import durable_memory, memory as memory_module
    from plugins._memory.helpers.memory import Memory
    from helpers.durable import runtime
    from langchain_core.embeddings import Embeddings
    import initialize
    class Embedder(Embeddings):
        def __init__(self):
            self.documents = []
        def embed_documents(self, texts):
            self.documents.extend(texts)
            return [[1., 0.] for _ in texts]
        def embed_query(self, text):
            return [1., 0.]
    embedding = Embedder()
    knowledge = tmp_path / 'knowledge'
    knowledge.mkdir()
    source = knowledge / 'fixture.md'
    source.write_text('First shared configured knowledge.', encoding='utf-8')
    monkeypatch.setattr('models.get_embedding_model', lambda *args, **kwargs: embedding)
    monkeypatch.setattr(Memory, '_get_embedding_config', lambda agent=None: SimpleNamespace(provider='synthetic', name='fixed', build_kwargs=lambda: {}))
    monkeypatch.setattr(Memory, 'index', {})
    monkeypatch.setattr(memory_module, 'abs_db_dir', lambda scope: str(tmp_path / 'absent-index'))
    monkeypatch.setattr(memory_module, 'abs_knowledge_dir', lambda directory, *parts: str(knowledge.joinpath(*parts)))
    monkeypatch.setattr(initialize, 'initialize_agent', lambda: SimpleNamespace(knowledge_subdirs=['fixture']))
    monkeypatch.setattr(runtime, '_service', backend.first)
    run = backend.first.sync('admit', 'knowledge-context', 'knowledge-input', {}, {})
    assert backend.first.sync('claim', run['run_id'])
    monkeypatch.setattr(memory_module, 'get_agent_memory_subdir', lambda agent: 'knowledge-fixture')
    with monkeypatch.context() as claimed:
        claimed.setattr(runtime, 'current', lambda agent=None: SimpleNamespace(run_id=run['run_id']))
        agent = SimpleNamespace(config=SimpleNamespace(knowledge_subdirs=['fixture']))
        first = asyncio.run(Memory.get(agent))
    backend.first.sync('release', run['run_id'])
    initial = durable_memory.get_snapshot(backend.first, 'knowledge-fixture')
    identifiers = [doc['id'] for doc in initial['documents']]
    assert len(identifiers) == 1 and embedding.documents == ['First shared configured knowledge.']
    assert first.get_document_by_id(identifiers[0]).page_content == 'First shared configured knowledge.'
    assert initial['documents'][0]['metadata']['source_path'] == 'fixture/fixture.md'
    monkeypatch.setattr(runtime, '_service', backend.second)
    absent = tmp_path / 'other-host-missing'
    monkeypatch.setattr(memory_module, 'abs_knowledge_dir', lambda *args: str(absent))
    second = asyncio.run(Memory.get_by_subdir('knowledge-fixture'))
    assert second.get_document_by_id(identifiers[0]).page_content == 'First shared configured knowledge.'
    assert durable_memory.get_snapshot(backend.second, 'knowledge-fixture') == initial
    assert not absent.exists() and len(embedding.documents) == 1
    monkeypatch.setattr(memory_module, 'abs_knowledge_dir', lambda directory, *parts: str(knowledge.joinpath(*parts)))
    source.write_text('Replacement shared configured knowledge.', encoding='utf-8')
    asyncio.run(Memory.get_by_subdir('knowledge-fixture'))
    assert durable_memory.get_snapshot(backend.first, 'knowledge-fixture') == initial
    assert len(embedding.documents) == 1  # Changed host files require explicit reindex.
    original = backend.second.store.put_projection
    def crash(key, value, version):
        if key.startswith('memory-op:'):
            raise RuntimeError('Cut before atomic knowledge receipt')
        return original(key, value, version)
    monkeypatch.setattr(backend.second.store, 'put_projection', crash)
    with pytest.raises(RuntimeError):
        asyncio.run(Memory.reload(agent))
    assert durable_memory.get_snapshot(backend.first, 'knowledge-fixture') == initial
    monkeypatch.setattr(backend.second.store, 'put_projection', original)
    replacement = asyncio.run(Memory.reload(agent))
    current = durable_memory.get_snapshot(backend.first, 'knowledge-fixture')
    assert len(current['documents']) == 1 and current['documents'][0]['id'] != identifiers[0]
    assert current['documents'][0]['text'] == 'Replacement shared configured knowledge.'
    before = len(embedding.documents)
    asyncio.run(Memory.get_by_subdir('knowledge-fixture'))
    assert len(embedding.documents) == before
    asyncio.run(replacement.delete_documents_by_ids([current['documents'][0]['id']]))
    deleted = durable_memory.get_snapshot(backend.first, 'knowledge-fixture')
    asyncio.run(Memory.get_by_subdir('knowledge-fixture'))
    assert durable_memory.get_snapshot(backend.first, 'knowledge-fixture') == deleted
    source.write_text('', encoding='utf-8')
    asyncio.run(Memory.reload(agent))
    empty = durable_memory.get_snapshot(backend.first, 'knowledge-fixture')
    asyncio.run(Memory.get_by_subdir('knowledge-fixture'))
    assert empty['documents'] == [] and durable_memory.get_snapshot(backend.first, 'knowledge-fixture') == empty


def test_shared_memory_delete_receipt_retains_only_ids_and_historical_reads_never_authorize_mutation(backend):
    from plugins._memory.helpers import durable_memory
    identity = {'provider': 'synthetic', 'model': 'fixed', 'dimension': 2}
    document = {'id': 'private-id', 'text': 'private deleted knowledge',
                'metadata': {'id': 'private-id', 'private': 'private deleted metadata'}, 'vector': [1., 0.]}
    durable_memory.apply_patch(backend.first, 'receipt-scope', 0, 'save',
        {'upsert': [document], 'delete': []}, identity=identity, control=True)
    patch = {'upsert': [], 'delete': ['private-id']}
    receipt = durable_memory.apply_patch(backend.first, 'receipt-scope', 1, 'delete', patch, control=True)
    assert receipt['removed'] == ['private-id'] and receipt['removed_count'] == 1
    assert 'private deleted' not in str(receipt)
    _, saved = durable_memory.operation(backend.second, 'receipt-scope', 'delete')
    assert saved == receipt
    backend.first.sync('begin_restore_review')
    with pytest.raises(ConflictError):
        durable_memory.operation(backend.second, 'receipt-scope', 'delete')
    assert durable_memory.operation(backend.second, 'receipt-scope', 'delete', allow_historical=True)[1] == receipt
    with pytest.raises(ConflictError):
        durable_memory.apply_patch(backend.second, 'receipt-scope', 1, 'delete', patch, control=True)
    assert durable_memory.get_snapshot(backend.first, 'receipt-scope')['documents'] == []


def test_shared_memory_ciphertexts_cannot_move_between_receipts_or_snapshot_revisions(backend):
    import copy
    from plugins._memory.helpers import durable_memory
    from helpers.durable.store import IntegrityError
    identity = {'provider': 'synthetic', 'model': 'fixed', 'dimension': 2}
    document = {'id': 'one', 'text': 'synthetic', 'metadata': {'id': 'one'}, 'vector': [1., 0.]}
    durable_memory.apply_patch(backend.first, 'binding-scope', 0, 'save',
        {'upsert': [document], 'delete': []}, identity=identity, control=True)
    original_snapshot = backend.first.sync('get_projection', durable_memory.key('binding-scope'))
    original_key, _ = durable_memory.operation(backend.first, 'binding-scope', 'save')
    original_receipt = backend.first.sync('get_projection', original_key)
    durable_memory.apply_patch(backend.first, 'binding-scope', 1, 'delete',
        {'upsert': [], 'delete': ['one']}, control=True)
    delete_key, _ = durable_memory.operation(backend.first, 'binding-scope', 'delete')
    target = backend.first.sync('get_projection', delete_key)
    swapped = copy.deepcopy(target['value'])
    swapped['receipt']['body'] = original_receipt['value']['receipt']['body']
    backend.first.sync('put_projection', delete_key, swapped, target['version'])
    with pytest.raises(IntegrityError):
        durable_memory.operation(backend.second, 'binding-scope', 'delete')
    swapped = {**original_snapshot['value'], 'domain': 'snapshot:3'}
    backend.first.sync('put_projection', durable_memory.key('binding-scope'), swapped, 2)
    with pytest.raises(IntegrityError):
        durable_memory.get_snapshot(backend.second, 'binding-scope')
    scope = 'epoch-race'
    projection = durable_memory.key(scope)
    operation_key = 'memory-op:' + projection[7:] + ':prepared'
    value = durable_memory.seal(backend.first, scope, {'identity': identity, 'documents': []}, domain='snapshot:1')
    receipt = durable_memory.seal(backend.first, scope, {'revision': 1, 'ids': [], 'removed': []},
                                  domain='operation:' + operation_key + ':' + 'a' * 64)
    backend.first.sync('begin_restore_review')
    role = 'memory:' + projection[7:]
    assert backend.first.sync('try_role', role)
    try:
        with pytest.raises(ConflictError):
            backend.first.sync('commit_memory_patch', projection, 0, operation_key, 'a' * 64,
                               value, receipt, control_role=role)
    finally:
        backend.first.sync('release_role', role)
    assert backend.second.sync('get_projection', projection) is None


@pytest.mark.parametrize('cut', ['driver', 'final_snapshot', 'unknown'])
def test_delete_waits_for_late_model_outcomes_and_rechecks_its_atomic_final_snapshot(backend, monkeypatch, cut):
    from models import LiteLLMChatWrapper
    model = LiteLLMChatWrapper('gpt-synthetic', 'openai', api_base='https://synthetic.invalid/v1', api_key='synthetic-key')
    ctx = context(model=model)
    descriptor = maintenance.provider_descriptor(ctx.agent0)
    checkpoint = {'context': {'id': ctx.id, 'data': {}, 'agents': [{'data': {}, 'history': '[]'}]},
                  'environment': {'provider_cleanup': descriptor}}
    run = backend.first.sync('admit', ctx.id, 'live-input', {}, checkpoint)
    run_id = run['run_id']
    assert backend.first.sync('claim', run_id)
    backend.first.sync('start_call', run_id, 'model:0', 'model', {'provider_cleanup': descriptor})
    queue(backend.first, run, 'maintenance_delete', {})
    deleted = []
    monkeypatch.setattr(maintenance, '_delete_target', lambda context, target: deleted.append(target['response_id']))
    outcome = {'mode': 'responses', 'response_id': 'late-known-response', 'provider_model_key': descriptor['model']}
    original = backend.first.store.complete_deletion
    if cut == 'driver':
        backend.first.driving = {run_id}
    elif cut == 'final_snapshot':
        def commit_after_snapshot(*args, **kwargs):
            backend.first.sync('finish_call', run_id, 'model:0', outcome)
            return original(*args, **kwargs)
        monkeypatch.setattr(backend.first.store, 'complete_deletion', commit_after_snapshot)
    first = asyncio.run(maintenance.process(backend.first, run_id, lambda row: ctx))
    if cut == 'unknown':
        assert first['deleted'] and deleted == []
    else:
        assert first['pending'] and not first.get('deleted') and deleted == []
        assert not backend.first.sync('get_run', run_id)['payloads_pruned']
        assert backend.first.sync('get_command', run_id, 'request')['status'] == 'pending'
        if cut == 'driver':
            backend.first.sync('finish_call', run_id, 'model:0', outcome)
            backend.first.driving.clear()
        monkeypatch.setattr(backend.first.store, 'complete_deletion', original)
        second = asyncio.run(maintenance.process(backend.first, run_id, lambda row: ctx))
        assert second['deleted'] and deleted == ['late-known-response']
    receipt = backend.first.sync('get_command', run_id, 'request')['result']
    assert receipt['accepted'] and receipt['unresolved_provider_calls'] == (1 if cut == 'unknown' else 0)


def test_retained_provider_target_map_is_cleaned_and_new_opt_out_prevents_plan_retries(backend, monkeypatch):
    from models import LiteLLMChatWrapper
    model = LiteLLMChatWrapper('gpt-synthetic', 'openai', api_base='https://synthetic.invalid/v1', api_key='synthetic-key')
    ctx = context(model=model)
    descriptor = maintenance.provider_descriptor(ctx.agent0)
    checkpoint = {'context': {'id': ctx.id, 'data': {}, 'agents': [{'data': {}, 'history': '[]'}]},
                  'environment': {'provider_cleanup': descriptor},
                  'provider_cleanup_targets': {'retained-only-response': descriptor}}
    run = backend.first.sync('admit', ctx.id, 'retained-input', {}, checkpoint)
    assert backend.first.sync('claim', run['run_id'])
    backend.first.sync('transition', run['run_id'], 'completed', checkpoint=checkpoint, status='completed')
    backend.first.sync('release', run['run_id'])
    queue(backend.first, run, 'maintenance_delete', {})
    deleted = []
    monkeypatch.setattr(maintenance, '_delete_target', lambda context, target: deleted.append(target['response_id']))
    original = backend.first.store.finish_maintenance_effect
    def lose_ack(*args):
        raise DurableStoreError('Lost provider receipt acknowledgment')
    monkeypatch.setattr(backend.first.store, 'finish_maintenance_effect', lose_ack)
    with pytest.raises(DurableStoreError):
        asyncio.run(maintenance.process(backend.first, run['run_id'], lambda row: ctx))
    assert deleted == ['retained-only-response']
    ctx.agent0.data['responses_delete_on_chat_delete'] = False
    monkeypatch.setattr(backend.first.store, 'finish_maintenance_effect', original)
    assert asyncio.run(maintenance.process(backend.first, run['run_id'], lambda row: ctx))['deleted']
    assert deleted == ['retained-only-response']
