"""Shared API routing uses committed projections, never requester-side shadows."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest

from agent import AgentContext, UserMessage
from api.durability import Durability
from helpers import persist_chat
from helpers.durable import documents, review, runtime
from helpers.durable.store import ConflictError
from test_durable_runtime import admitted, rig


class SharedView:
    """Public coordinator seam backed by a real isolated ledger for API tests."""
    distributed = True
    enabled = True
    failed = False
    driving = set()

    def __init__(self, local):
        self.local, self.commands, self.projections = local, {}, {}
        self.lock = threading.RLock()

    def sync(self, method, *args, **kwargs):
        if method == "owns":
            return False
        if method == "ownership":
            return {"claimed": True, "worker_id": "other-worker", "fence": 2}
        if method == "get_command":
            return self.commands.get((args[0], args[1]))
        if method == "get_projection":
            return self.projections.get(args[0])
        if method == "put_projection":
            key, value, version = args
            old = self.projections.get(key)
            if (old["version"] if old else 0) != version:
                raise ConflictError("Projection changed")
            self.projections[key] = {"value": value, "version": version + 1}
            return self.projections[key]
        return self.local.sync(method, *args, **kwargs)

    def submit_command(self, run_id, kind, payload, request_id):
        old = self.commands.get((run_id, request_id))
        if old and (old["kind"], old["payload"]) != (kind, payload):
            raise ConflictError("Different command")
        if not old:
            old = {"run_id": run_id, "kind": kind, "payload": payload,
                   "request_id": request_id, "status": "pending", "result": None}
            self.commands[(run_id, request_id)] = old
        return old

    def pause_remote(self, context_id, paused, request_id):
        run = self.sync("list_run_headers", context_id=context_id)[-1]
        return self.submit_command(run["run_id"], "pause", {"paused": paused}, request_id)


@pytest.fixture
def shared(rig, monkeypatch):
    value = SharedView(rig.owner)
    monkeypatch.setattr(runtime, "_service", value)
    return value


def call(payload):
    return asyncio.run(Durability(None, threading.RLock()).process(payload, None))


def test_remote_status_and_document_read_need_no_live_context(rig, shared, monkeypatch):
    run = admitted(rig, "iteration_ready")
    documents.update(rig.owner, rig.context, "todo", {"title": "sentinel-secret", "items": []}, 0, "plan")
    AgentContext._contexts.clear()
    monkeypatch.setattr(AgentContext, "__init__", lambda *args, **kwargs: pytest.fail("Shadow context constructed"))
    result = call({"action": "status"})
    assert result["distributed"] is True
    assert result["runs"][0]["run_id"] == run["run_id"]
    assert result["runs"][0]["ownership"] == {"claimed": True, "worker_id": "other-worker"}
    value = call({"action": "document_read", "context": rig.context.id, "kind": "todo"})
    assert value["document"]["value"]["title"] == "[MASKED]"
    assert AgentContext.all() == []


def test_remote_document_write_holds_without_using_stale_local_masking_context(rig, shared):
    admitted(rig, "iteration_ready")
    response = call({"action": "document_update", "context": rig.context.id, "kind": "todo",
                     "value": {"title": "Private draft", "items": []}, "expected_revision": 0, "request_id": "write"})
    assert response.status_code == 409
    assert "draft was not saved" in response.get_data(as_text=True)
    assert rig.owner.sync("read_document", rig.context.id, "todo") is None


def test_remote_review_receipts_are_scoped_masked_and_repeated_with_exact_identity(rig, shared):
    run = admitted(rig, "iteration_ready")
    payload = {"action": "resolve", "context": rig.context.id, "run_id": run["run_id"],
               "version": rig.owner.sync("get_review", run["run_id"])["version"],
               "decision": "resume", "note": "sentinel-secret evidence", "request_id": "remote-review"}
    result = call(payload)
    assert result["queued"] is True and result["command"] == {"request_id": "remote-review", "state": "pending"}
    command = shared.commands[(run["run_id"], "remote-review")]
    assert command["payload"]["note"] == "[MASKED] evidence"
    rig.owner.sync("transition", run["run_id"], "needs_attention", status="attention")
    assert call(payload) == result, "An accepted request survives a newer review version"
    changed = call({**payload, "note": "Different evidence"})
    assert changed.status_code == 409
    command.update(status="applied", result={"accepted": False, "error": "private-provider-secret"})
    status = call({"action": "command_status", "context": rig.context.id, "run_id": run["run_id"], "request_id": "remote-review"})
    assert status["command"]["state"] == "rejected"
    assert "private-provider-secret" not in json.dumps(status)
    command.update(status="invalidated", epoch_valid=False)
    invalidated = call({"action": "command_status", "context": rig.context.id, "run_id": run["run_id"], "request_id": "remote-review"})
    assert invalidated["command"]["state"] == "rejected"
    assert "restore epoch" in invalidated["command"]["error"]
    wrong_scope = call({"action": "command_status", "context": "another-chat", "run_id": run["run_id"], "request_id": "remote-review"})
    assert wrong_scope.status_code == 404
    assert rig.requests == []


def test_shared_endpoint_still_enforces_authentication_and_csrf(rig, shared, monkeypatch):
    from flask import Flask
    from helpers import api as api_module, login
    admitted(rig, "iteration_ready")
    app = Flask("isolated-shared-api-auth")
    app.secret_key = "synthetic-test-only-session-key"
    app.add_url_rule("/login", "login_handler", lambda: "Authentication required")
    app.add_url_rule("/", "serve_index", lambda: "Synthetic index")
    monkeypatch.setattr(login, "get_credentials_hash", lambda: "synthetic-auth")
    monkeypatch.setattr(api_module.cache, "get", lambda *args: None)
    monkeypatch.setattr(api_module.cache, "add", lambda *args: None)
    api_module.register_api_route(app, threading.RLock())
    client = app.test_client()
    assert client.post("/api/durability", json={"action": "status"}).status_code == 302
    with client.session_transaction() as session:
        session["authentication"] = "synthetic-auth"
        session["csrf_token"] = "synthetic-csrf"
    assert client.post("/api/durability", json={"action": "status"}).status_code == 403
    response = client.post("/api/durability", json={"action": "status"}, headers={"X-CSRF-Token": "synthetic-csrf"})
    assert response.status_code == 200 and response.json["distributed"] is True


def test_remote_stop_works_without_context_or_checkpoint_decode(rig, shared, monkeypatch):
    run = admitted(rig, "iteration_ready")
    version = rig.owner.sync("get_review", run["run_id"])["version"]
    AgentContext._contexts.clear()
    original = shared.sync
    def no_checkpoint(method, *args, **kwargs):
        if method == "get_run":
            raise ValueError("Unreadable checkpoint")
        return original(method, *args, **kwargs)
    monkeypatch.setattr(shared, "sync", no_checkpoint)
    payload = {"action": "resolve", "context": rig.context.id, "run_id": run["run_id"], "version": version,
               "decision": "stop", "note": "Operator note", "request_id": "remote-stop"}
    assert isinstance(call(payload), dict)
    assert isinstance(call(payload), dict)
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "cancelled"
    assert shared.commands == {} and rig.requests == []


def test_generic_api_context_lookup_cannot_mutate_a_remote_shadow(rig, shared, monkeypatch):
    from helpers.api import ApiHandler
    admitted(rig, "iteration_ready")
    handler = Durability(None, threading.RLock())
    with pytest.raises(ValueError, match="execution owner"):
        ApiHandler.use_context(handler, rig.context.id)
    with pytest.raises(ValueError, match="explicit chat"):
        ApiHandler.use_context(handler, "")
    from unittest.mock import AsyncMock
    monkeypatch.setattr(handler, "process", AsyncMock(side_effect=RuntimeError("postgres://user:private-password@private-host/db")))
    request = SimpleNamespace(is_json=True, data=b"{}", get_json=lambda: {})
    response = asyncio.run(handler.handle_request(request))
    assert response.status_code == 503 and "private-password" not in response.get_data(as_text=True)


def test_remote_pause_routes_by_identity_and_never_echoes_command_payload(rig, shared):
    from api.pause import Pause
    admitted(rig, "iteration_ready")
    result = asyncio.run(Pause(None, threading.RLock()).process({"context": rig.context.id, "paused": True}, None))
    assert result["queued"] is True and result["pause"] is True
    assert "payload" not in result
    assert next(iter(shared.commands.values()))["kind"] == "pause"
    assert rig.context.paused is False


def test_shared_reset_requires_stable_identity_before_any_shadow_or_global_fence(rig, shared, monkeypatch):
    from api.chat_reset import Reset
    admitted(rig, "iteration_ready")
    calls = []
    monkeypatch.setattr(runtime, "control", lambda *args, **kwargs: calls.append((args, kwargs)))
    handler = Reset(None, threading.RLock())
    monkeypatch.setattr(handler, "use_context", lambda *args: pytest.fail("Local shadow accessed"))
    missing = asyncio.run(handler.process({"context": rig.context.id}, None))
    assert missing.status_code == 409 and calls == []
    result = asyncio.run(handler.process({"context": rig.context.id, "request_id": "stable-reset"}, None))
    assert result["reset"] is True
    assert calls == [((rig.context.id, "reset"), {"request_id": "stable-reset"})]


def test_shared_delete_holds_before_reset_provider_cleanup_or_local_removal(rig, shared, monkeypatch):
    from api.chat_remove import RemoveChat
    run = admitted(rig, "iteration_ready")
    original_agent = rig.context.agent0
    monkeypatch.setattr(persist_chat, "_delete_provider_responses_for_chat", lambda *args: pytest.fail("Provider cleanup ran"))
    response = asyncio.run(RemoveChat(None, threading.RLock()).process({"context": rig.context.id}, None))
    assert response.status_code == 409
    assert rig.context.agent0 is original_agent and AgentContext.get(rig.context.id) is rig.context
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "running"
    with pytest.raises(persist_chat.SharedDeletionHeld):
        persist_chat.remove_chat(rig.context.id)


def test_shared_persistence_skips_stale_shadows_and_does_not_import_local_chats(rig, shared, monkeypatch):
    admitted(rig, "iteration_ready")
    persist_chat.save_tmp_chat(rig.context)
    assert shared.projections == {} and not persist_chat.chat_file_exists("unknown-chat")
    monkeypatch.setattr(persist_chat, "_convert_v080_chats", lambda: pytest.fail("Local snapshots imported"))
    assert persist_chat.load_tmp_chats() == []


def test_remote_message_routes_before_local_context_hooks_and_logging(rig, shared, monkeypatch):
    from api.message import Message
    persist_chat.save_tmp_chat(rig.context)
    assert shared.sync("list_run_headers", context_id=rig.context.id) == []
    assert shared.sync("get_projection", "genesis:" + rig.context.id)
    handle = object()
    captured = []
    shared.communicate_remote = lambda context_id, message, **kwargs: captured.append((context_id, message, kwargs)) or handle
    handler = Message(None, threading.RLock())
    monkeypatch.setattr(handler, "use_context", lambda *args: pytest.fail("Local shadow accessed"))
    request = SimpleNamespace(content_type="application/json", get_json=lambda: {"context": rig.context.id, "text": "Portable input", "message_id": "stable-input"})
    task, context = asyncio.run(handler.communicate({}, request))
    assert task is handle and context.id == rig.context.id
    assert captured[0][1] == UserMessage("Portable input", id="stable-input")
    assert captured[0][2] == {"ui": True}


def test_initial_shared_message_allocates_chat_identity_before_context_lookup(rig, shared, monkeypatch):
    from api.message import Message
    from helpers import message_queue
    from unittest.mock import AsyncMock
    handler = Message(None, threading.RLock())
    identities = []
    handle = object()
    admitted_inputs = []
    shared.admit_from_context = lambda context, message, **kwargs: admitted_inputs.append((message, kwargs)) or handle
    def context_for(identity):
        assert identity and identity != rig.context.id
        identities.append(identity)
        return rig.context
    monkeypatch.setattr(handler, "use_context", context_for)
    monkeypatch.setattr(rig.context, "communicate", lambda message: handle)
    monkeypatch.setattr(message_queue, "log_user_message", lambda *args: pytest.fail("Requester logged raw UI input"))
    monkeypatch.setattr("helpers.extension.call_extensions_async", AsyncMock(side_effect=AssertionError("Requester ran input hooks")))
    request = SimpleNamespace(content_type="application/json", get_json=lambda: {"context": "", "text": "First message", "message_id": "initial-message"})
    task, _ = asyncio.run(handler.communicate({}, request))
    assert task is handle and len(identities) == 1
    assert admitted_inputs[0][1] == {"ui": True}
    asyncio.run(handler.communicate({}, request))
    assert identities[0] == identities[1], "An initial lost acknowledgment must reuse the same chat admission identity"
