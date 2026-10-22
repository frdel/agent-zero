"""Shared resource custody exercised through real encrypted PostgreSQL bytes."""
import hashlib
import os
from pathlib import Path
import uuid

import pytest

from helpers.durable.postgres import PostgresStore
from helpers.durable.resources import ResourceHeld, ResourceManager, SCHEME, capture_attachments
from helpers.durable.store import ConflictError, IntegrityError, OwnershipError, StaleRunError

DSN = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")


class Owner:
    distributed, failed = True, False
    def __init__(self, store):
        self.store = store

    def sync(self, name, *args, **kwargs):
        return getattr(self.store, name)(*args, **kwargs)


@pytest.fixture
def shared(monkeypatch):
    if not DSN:
        pytest.skip("Requires explicit disposable PostgreSQL")
    from cryptography.fernet import Fernet
    from psycopg import connect, sql
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    namespace = "resources_" + uuid.uuid4().hex
    first, second = PostgresStore(DSN, namespace=namespace), PostgresStore(DSN, namespace=namespace)
    try:
        yield first, second
    finally:
        first.close(); second.close()
        with connect(DSN, autocommit=True) as cleanup:
            cleanup.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))


def test_private_bytes_cross_workers_without_files_and_reject_wrong_context_or_tampering(shared, tmp_path, monkeypatch):
    first, second = shared
    source = tmp_path / "attachment.pdf"
    content = b"private-file\x00\xff" * 300
    source.write_bytes(content)
    manager = ResourceManager(Owner(first), "chat")
    uri, = capture_attachments(manager, [str(source)])
    ref = manager.reference(uri)
    ciphertext = first.get_resource("chat", ref["id"])["body"]
    assert content not in ciphertext
    source.unlink()
    remote = ResourceManager(Owner(second), "chat")
    assert remote.get_bytes(ref) == content
    import asyncio
    import threading
    from api.durability_resource import DurabilityResource
    from helpers.durable import runtime
    monkeypatch.setattr(runtime, "_service", Owner(second))
    handler = DurabilityResource(None, threading.RLock())
    response = asyncio.run(handler.process({"context": "chat", "resource_id": ref["id"]}, None))
    assert response.data == content and response.headers["Cache-Control"] == "no-store"
    assert asyncio.run(handler.process({"context": "chat", "action": "workspace"}, None)) == {"workspace": None}
    assert remote.materialize(ref, tmp_path / "other-host" / "file.pdf").read_bytes() == content
    with pytest.raises(KeyError):
        ResourceManager(Owner(second), "another-chat").get_bytes(ref)
    with pytest.raises(IntegrityError):
        remote.get_bytes({**ref, "name": "different.pdf"})
    run = first.admit("chat", "adapter-restore", {}, {})
    first.claim(run["run_id"])
    manifest = manager.capture("attachments", [uri])
    claimed = ResourceManager(Owner(first), "chat", run["run_id"])
    assert claimed.restore(manifest, tmp_path / "adapter")[0].read_bytes() == content
    with pytest.raises(ResourceHeld, match="missing_or_changed"):
        claimed.restore({**manifest, "version": 999}, tmp_path / "unsupported")
    second._connection.execute("UPDATE resource_objects SET body=? WHERE context_id='chat'", (b"corrupt",))
    with pytest.raises(IntegrityError):
        remote.get_bytes(ref)
    monkeypatch.delenv("A0_DURABILITY_RESOURCE_KEY")
    with pytest.raises(ResourceHeld, match="RESOURCE_KEY"):
        manager.put_bytes("attachment", "missing-key", b"data")


def test_manifest_publication_requires_live_owner_cas_and_current_generation(shared):
    first, second = shared
    run = first.admit("chat", "input", {}, {})
    assert first.claim(run["run_id"])
    manager = ResourceManager(Owner(first), "chat", run["run_id"])
    ref = manager.put_bytes("attachment", "a", b"data")
    assert manager.publish_manifest("attachment", {"files": [ref]}, 0)["version"] == 1
    with pytest.raises(OwnershipError):
        ResourceManager(Owner(second), "chat", run["run_id"]).publish_manifest("attachment", {}, 1)
    with pytest.raises(ConflictError):
        manager.publish_manifest("attachment", {}, 0)
    second.control("chat", "reset")
    with pytest.raises((OwnershipError, StaleRunError)):
        manager.publish_manifest("attachment", {}, 1)
    assert manager.get_manifest("attachment") is None


def test_detached_job_can_publish_only_known_immutable_outcome_without_workflow_claim(shared):
    first, second = shared
    run = first.admit("chat", "input", {}, {})
    assert first.claim(run["run_id"])
    token = uuid.uuid4().hex
    first.register_resource_job(run["run_id"], "job", "a" * 64, hashlib.sha256(token.encode()).hexdigest())
    first.release(run["run_id"])
    with pytest.raises(OwnershipError):
        second.begin_resource_job("job", token, "broker:fixture")
    assert second.try_role("broker:fixture")
    assert first.claim(run["run_id"])
    first.transition(run["run_id"], "tools", {"paused": True}, status="blocked")
    with pytest.raises(OwnershipError):
        second.begin_resource_job("job", token, "broker:fixture")
    first.transition(run["run_id"], "tools", {"paused": False}, status="running")
    first.release(run["run_id"])
    assert second.begin_resource_job("job", token, "broker:fixture")
    assert second.get_resource_job("job")["status"] == "running"
    assert not second.begin_resource_job("job", token, "broker:fixture")
    assert not first.try_role("broker:fixture")
    worker = ResourceManager(Owner(second), "chat", job_id="job", job_token=token)
    ref = worker.put_bytes("output", "stdout", b"one known result")
    result = {"output": ref, "exit_code": 0}
    assert second.finish_resource_job("job", token, result)["result"] == result
    assert second.finish_resource_job("job", token, result)["status"] == "completed"
    assert not second.begin_resource_job("job", token, "broker:fixture")
    second.release_role("broker:fixture")
    assert first.try_role("broker:fixture")
    assert not first.begin_resource_job("job", token, "broker:fixture")
    with pytest.raises(ConflictError):
        second.finish_resource_job("job", token, {"exit_code": 1})
    with pytest.raises(OwnershipError):
        second.transition(run["run_id"], "completed", {})
    with pytest.raises(OwnershipError):
        second.finish_resource_job("job", "wrong", result)
    first.control("chat", "reset")
    with pytest.raises(OwnershipError):
        second.finish_resource_job("job", token, result)
    first._connection.execute("UPDATE resource_jobs SET result=NULL WHERE job_id='job'")
    with pytest.raises(IntegrityError):
        second.get_resource_job("job")


def test_retention_keeps_current_resources_collects_orphans_and_delete_scrubs_bytes(shared):
    first, second = shared
    manager = ResourceManager(Owner(first), "chat")
    retained = manager.put_bytes("attachment", "retained", b"keep")
    orphan = manager.put_bytes("attachment", "orphan", b"expire")
    run = first.admit("chat", "input", {"attachments": [SCHEME + retained["id"]]}, {"resources": {"attachments": [retained]}})
    assert first.claim(run["run_id"])
    first.transition(run["run_id"], "completed", status="completed")
    first.compact(retain_terminal=0)
    first.collect_resources(grace_seconds=0)
    assert ResourceManager(Owner(second), "chat").get_bytes(retained) == b"keep"
    with pytest.raises(KeyError):
        manager.get_bytes(orphan)
    with pytest.raises(KeyError):
        first.admit("chat", "dangling-resource", {"attachments": [SCHEME + orphan["id"]]}, {})
    first.control("chat", "delete")
    assert first._connection.execute("SELECT COUNT(*) FROM resource_objects WHERE context_id='chat'").fetchone()[0] == 0
    with pytest.raises(StaleRunError):
        manager.get_bytes(retained)


def test_corrupt_retained_root_prevents_resource_collection(shared):
    first, _ = shared
    manager = ResourceManager(Owner(first), "chat")
    ref = manager.put_bytes("attachment", "retained", b"evidence")
    first.admit("chat", "input", {}, {"resources": {"attachments": [ref]}})
    first._connection.execute("UPDATE runs SET checkpoint='{}'")
    with pytest.raises(IntegrityError):
        first.collect_resources(grace_seconds=0)
    assert manager.get_bytes(ref) == b"evidence"


def test_resource_path_translation_does_not_rebind_sibling_paths_or_invalid_reference_suffixes():
    from types import SimpleNamespace
    from helpers.durable.resources import canonical_value, local_value
    context = SimpleNamespace(_durable_workspace_path=Path("/tmp/work"), _durable_workspace_origin={"project_name": "project"},
                              _durable_resource_paths={"/tmp/upload.pdf": SCHEME + "a" * 64})
    source = {'command': 'cat "/tmp/work/file" /tmp/work-other/file /tmp/upload.pdf-suffix',
              'attachment': '/tmp/upload.pdf', 'bad_ref': SCHEME + "a" * 64 + '-suffix'}
    canonical = canonical_value(context, source)
    context._durable_workspace_path = Path('/tmp/second-work')
    context._durable_resource_paths = {'/tmp/second-upload.pdf': SCHEME + "a" * 64}
    restored = local_value(context, canonical)
    assert restored['command'] == 'cat "/tmp/second-work/file" /tmp/work-other/file /tmp/upload.pdf-suffix'
    assert restored['attachment'] == '/tmp/second-upload.pdf'
    assert restored['bad_ref'] == source['bad_ref']


def test_background_outbox_publication_and_retention_are_atomic(shared, monkeypatch):
    first, second = shared
    run = first.admit('outbox-context', 'input', {}, {})
    assert first.claim(run['run_id'])
    identifier = 'c' * 64
    token = 'outbox-private-token'
    manager = ResourceManager(Owner(first), 'outbox-context', run['run_id'])
    request = manager.put_bytes('background-request', identifier, b'private frozen input', sensitive=True)
    jobs = [{'id': identifier + ':final:result', 'fingerprint': 'a' * 64,
             'token_digest': hashlib.sha256(token.encode()).hexdigest(), 'allow_completed': True}]
    value = {'id': identifier, 'run_id': run['run_id'], 'request': request, 'roots': []}
    publish = first.publish_resource_manifest
    def crash(*args, **kwargs):
        raise RuntimeError('cut before manifest publication')
    monkeypatch.setattr(first, 'publish_resource_manifest', crash)
    with pytest.raises(RuntimeError):
        first.publish_resource_outbox('outbox-context', 'background-' + identifier, value, 0, run['run_id'], jobs)
    assert second.get_resource_job(jobs[0]['id']) is None
    monkeypatch.setattr(first, 'publish_resource_manifest', publish)
    first.publish_resource_outbox('outbox-context', 'background-' + identifier, value, 0, run['run_id'], jobs)
    first.transition(run['run_id'], 'completed', status='completed')
    first.release(run['run_id'])
    first.compact(retain_terminal=0)
    assert second.collect_resources(0)['resources_removed'] == 0
    assert second.list_resource_manifests('background-')[0]['value'] == value
    assert second.try_role('outbox:fixture')
    assert second.begin_resource_job(jobs[0]['id'], token, 'outbox:fixture')
    actor = ResourceManager(Owner(second), 'outbox-context', job_id=jobs[0]['id'], job_token=token)
    result = actor.put_bytes('background-result', identifier, b'known result', sensitive=True)
    second.finish_resource_job(jobs[0]['id'], token, {'value': result})
    assert second.collect_resources(0)['resources_removed'] == 2
    assert second.list_resource_manifests('background-') == []
    assert second.get_resource_job(jobs[0]['id']) is None
