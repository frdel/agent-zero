"""Claimed, encrypted document mutations and idempotent provider/chat cleanup.

The inbox stores resource references, never app drafts. Idle maintenance uses
exactly the execution context lock, but never starts an agent message loop.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import inspect
import json
import os
from pathlib import Path

from helpers.durable.store import ConflictError, IntegrityError, OwnershipError, StaleRunError, _identity, _json

KINDS = ("maintenance_document", "maintenance_conflict", "maintenance_delete")


class MaintenanceHeld(RuntimeError):
    pass


def provider_descriptor(agent, *, model=None):
    """Pin configured provider/account without retaining credentials or endpoint."""
    from models import LiteLLMChatWrapper
    from helpers.durable import codec
    from helpers.durable.resources import cipher
    if not os.environ.get("A0_DURABILITY_RESOURCE_KEY"):
        return None
    model = model if model is not None else agent.get_chat_model()
    if type(model) is not LiteLLMChatWrapper or model.provider not in {"openai", "azure"}:
        return None
    kwargs = model.kwargs or {}
    key = kwargs.get("api_key")
    if any(kwargs.get(name) for name in ("azure_ad_token", "azure_ad_token_provider", "extra_headers", "headers")):
        return None
    if not isinstance(key, str) or not key:
        return None  # Environment/global credential fallback has no pinned account.
    cipher()
    secret = base64.urlsafe_b64decode(os.environ["A0_DURABILITY_RESOURCE_KEY"])
    endpoint = str(kwargs.get("api_base", ""))
    return {"provider": model.provider, "model": model.model_name,
            "endpoint_digest": hashlib.sha256(endpoint.encode()).hexdigest(),
            "credential_digest": hmac.new(secret, _json({name: kwargs.get(name) for name in
                ("api_key", "api_base", "api_version", "organization", "project")}).encode(), hashlib.sha256).hexdigest(),
            "implementation": codec.identity(model),
            "contract": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _reference(context_id, request_id, body):
    digest = hashlib.sha256(body).hexdigest()
    name = "request-" + hashlib.sha256(request_id.encode()).hexdigest()
    resource_id = hashlib.sha256(_json([context_id, "maintenance_request", name, digest]).encode()).hexdigest()
    return {"id": resource_id, "kind": "maintenance_request", "name": name, "digest": digest, "size": len(body)}


def metadata(owner, context_id, run_id=None):
    headers = owner.sync("list_run_headers", context_id=context_id)
    if run_id is None:
        if not headers:
            owner.sync("ensure_maintenance_anchor", context_id)
            headers = owner.sync("list_run_headers", context_id=context_id)
        run_id = max(headers, key=lambda row: (row.get("admission_seq", 0), row["run_id"]))["run_id"]
    if not any(row["run_id"] == run_id for row in headers):
        raise KeyError("Run is outside the requested chat")
    return {"run_id": run_id, "generation": owner.sync("document_generation", context_id),
            "epoch": owner.sync("get_restore_state")["epoch"], "version": owner.sync("get_review", run_id)["version"]}


def enqueue(owner, context_id, run_id, kind, value, request_id, *, generation, epoch, version):
    """Encrypt before inbox commit; repeated transport requests retain original identity."""
    from helpers.durable.resources import ResourceManager
    _identity(context_id, "context id"); _identity(run_id, "run id"); _identity(request_id, "request id")
    if kind not in KINDS or type(generation) is not int or generation < 0:
        raise ValueError("Invalid maintenance request")
    if not any(row["run_id"] == run_id for row in owner.sync("list_run_headers", context_id=context_id)):
        raise KeyError("Run is outside the requested chat")
    body = _json(value).encode()
    if len(body) > 96 * 1024:
        raise ValueError("Maintenance request exceeds its bound")
    ref = _reference(context_id, request_id, body)
    payload = {"ref": ref, "generation": generation, "epoch": epoch, "version": version}
    prior = owner.sync("get_command", run_id, request_id)
    if prior is None:
        actual = ResourceManager(owner, context_id).put_bytes(ref["kind"], ref["name"], body, sensitive=True)
        if actual != ref:
            raise IntegrityError("Maintenance resource identity changed")
    receipt = owner.sync("enqueue_maintenance", run_id, kind, payload, request_id)
    wake = getattr(owner, "wake_maintenance", None)
    if callable(wake):
        wake(run_id)
    return public_receipt(receipt, context_id)


def public_receipt(receipt, context_id):
    from helpers.durable.review import command_receipt
    return command_receipt(receipt, context_id)


async def _context(restore_context, run):
    result = restore_context(run)
    return await result if inspect.isawaitable(result) else result


def _request(owner, run, command):
    from helpers.durable.resources import ResourceManager
    payload = command["payload"]
    if (not command["epoch_valid"] or payload["generation"] != run["generation"]
            or payload["epoch"] != owner.sync("get_restore_state")["epoch"]):
        raise ConflictError("Maintenance generation or epoch changed")
    body = ResourceManager(owner, run["context_id"], run["run_id"]).get_bytes(payload["ref"])
    value = json.loads(body)
    if _json(value).encode() != body:
        raise IntegrityError("Maintenance request is not canonical JSON")
    return value


def _response_ids(projection):
    """Read only explicit normalized history/state identities, never raw metadata."""
    found = set()
    for agent in projection.get("agents", []):
        data = agent.get("data", {})
        state = data.get("responses_state") or {}
        if isinstance(state, dict):
            values = [state.get("response_id"), *(state.get("response_ids") or [])]
            found.update(value for value in values if isinstance(value, str) and value)
        history = agent.get("history")
        if isinstance(history, str):
            history = json.loads(history)
        def visit(item):
            if isinstance(item, dict):
                # History message metadata is a normalized framework projection.
                meta = item.get("metadata")
                result = meta.get("responses") if isinstance(meta, dict) else None
                if isinstance(result, dict) and isinstance(result.get("response_id"), str):
                    found.add(result["response_id"])
                for key, child in item.items():
                    if key != "metadata":
                        visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
        visit(history)
    return found


def collect_provider_targets(owner, context):
    return _collect_provider_targets(owner, context)[0]


def _collect_provider_targets(owner, context):
    from helpers import persist_chat
    projections, runs = [], []
    for header in owner.sync("list_run_headers", context_id=context.id):
        if header["payloads_pruned"]:
            continue
        run = owner.sync("get_run", header["run_id"])
        checkpoint = run.get("checkpoint") or {}
        projections.append(checkpoint.get("context") or {})
        runs.append((run, checkpoint))
    # Current public head survives per-run retention.
    head = owner.sync("get_context_head", context.id)
    if head:
        checkpoint = head["checkpoint"]
        projections.append(checkpoint.get("context") or {})
        if not any(run["run_id"] == head["run_id"] for run, _ in runs):
            runs.append(({"run_id": head["run_id"], "payloads_pruned": True}, checkpoint))
    agent = context.agent0
    if context.data.get("responses_delete_on_chat_delete") is False:
        return [], True
    while agent:
        if agent.data.get("responses_delete_on_chat_delete") is False:
            return [], True
        agent = agent.data.get("_subordinate")
    if any(persist_chat._responses_delete_disabled(projection) for projection in projections):
        return [], True
    current = provider_descriptor(context.agent0)
    needed, proven = set(), {}
    for run, checkpoint in runs:
        needed.update(_response_ids(checkpoint.get("context") or {}))
        saved = checkpoint.get("provider_cleanup_targets") or {}
        if not isinstance(saved, dict):
            raise MaintenanceHeld("provider_cleanup_target_unverified")
        needed.update(saved)
        for response_id, descriptor in saved.items():
            if response_id in proven and proven[response_id] != descriptor:
                raise MaintenanceHeld("provider_cleanup_target_conflict")
            proven[response_id] = descriptor
        main_result = checkpoint.get("result")
        results = [(main_result, proven.get(main_result.get("response_id")) if isinstance(main_result, dict) else None)]
        if not run["payloads_pruned"]:
            results += [(call["result"], (call.get("payload") or {}).get("provider_cleanup"))
                        for call in owner.sync("calls", run["run_id"])
                        if call["kind"] == "model" and call["status"] == "completed" and not call["payloads_pruned"]]
        for result, descriptor in results:
            if isinstance(result, dict) and result.get("mode") == "responses" and result.get("response_id"):
                response_id = result["response_id"]
                descriptor = descriptor or proven.get(response_id)
                if (not descriptor or result.get("provider_model_key") not in (None, "", descriptor.get("model"))
                        or response_id in proven and proven[response_id] != descriptor):
                    raise MaintenanceHeld("provider_cleanup_target_unverified")
                proven[response_id] = descriptor
                needed.add(response_id)
    targets = []
    for response_id in sorted(needed):
        if not current or proven.get(response_id) != current:
            raise MaintenanceHeld("provider_cleanup_target_changed")
        targets.append({"response_id": response_id, "target": current})
    return targets, False


def _delete_target(context, target):
    """Audited idempotent DELETE: the identical target's 404 means already absent."""
    model = context.agent0.get_chat_model()
    if provider_descriptor(context.agent0, model=model) != target["target"]:
        raise MaintenanceHeld("provider_cleanup_target_changed")
    import litellm
    kwargs = {key: value for key, value in (model.kwargs or {}).items()
              if key in {"api_key", "api_base", "api_version", "organization", "project"}}
    try:
        litellm.delete_responses(response_id=target["response_id"], model=model.model_name,
                                 custom_llm_provider=model.provider, **kwargs)
    except Exception as exc:
        if getattr(exc, "status_code", None) != 404:
            raise MaintenanceHeld("provider_cleanup_failed") from None


async def _delete(owner, run, command, restore_context, context):
    from helpers.durable.resources import ResourceManager
    bindings = owner.sync("begin_deletion", run["run_id"], command["request_id"])
    if any(item["run_id"] in getattr(owner, "driving", ()) for item in bindings):
        # Cancellation still permits the old driver to save its known body
        # outcome. Do not freeze provider custody until that writer unwinds.
        return False
    context_ids = {item["context_id"] for item in bindings}
    claimed = []
    contexts = {context.id: context}
    try:
        for binding in bindings:
            context_id = binding["context_id"]
            if context_id == run["context_id"]:
                continue
            child_id = binding["run_id"]
            owned = owner.sync("owns", child_id)
            if not owned and not owner.sync("claim_maintenance", child_id):
                return False
            if not owned:
                claimed.append(child_id)
            child = owner.sync("get_run", child_id)
            if child["payloads_pruned"]:
                head = owner.sync("get_context_head", context_id)
                if not head or head["run_id"] != child_id:
                    raise MaintenanceHeld("maintenance_context_unavailable")
                child["checkpoint"] = head["checkpoint"]
            contexts[context_id] = await _context(restore_context, child)
        manager = ResourceManager(owner, run["context_id"], run["run_id"])
        manifest_kind = "cleanup-" + hashlib.sha256(command["request_id"].encode()).hexdigest()
        saved = manager.get_manifest(manifest_kind)
        snapshot = owner.sync("deletion_provider_snapshot", command["request_id"])
        targets, opted_out = [], set()
        for identity, ctx in contexts.items():
            selected, disabled = _collect_provider_targets(owner, ctx)
            if disabled:
                opted_out.add(identity)
            targets.extend({"context_id": identity, **target} for target in selected)
        plan = json.loads(manager.get_bytes(saved["value"]["ref"])) if saved else {"contexts": sorted(context_ids), "targets": []}
        if plan["contexts"] != sorted(context_ids):
            raise MaintenanceHeld("cleanup_graph_changed")
        merged = {_json(item): item for item in [*plan["targets"], *targets]
                  if item["context_id"] not in opted_out}
        updated = {"contexts": sorted(context_ids), "targets": [merged[key] for key in sorted(merged)]}
        if saved is None or updated != plan:
            body = _json(updated).encode()
            ref = manager.put_bytes("cleanup_plan", manifest_kind, body, sensitive=True)
            manager.publish_manifest(manifest_kind, {"ref": ref}, saved["version"] if saved else 0)
        plan = updated
        for target in plan["targets"]:
            fingerprint = hashlib.sha256(_json(target).encode()).hexdigest()
            effect_id = "delete-" + fingerprint
            receipt = owner.sync("maintenance_effect", run["run_id"], command["request_id"], effect_id, fingerprint)
            if receipt["status"] == "completed":
                continue
            owner.sync("assert_owner", run["run_id"])
            await asyncio.to_thread(_delete_target, contexts[target["context_id"]], target)
            owner.sync("finish_maintenance_effect", run["run_id"], command["request_id"], effect_id, fingerprint)
        unknown = sum(call["kind"] == "model" and call["status"] == "intent"
                      for binding in bindings for header in owner.sync("list_run_headers", context_id=binding["context_id"])
                      if not header["payloads_pruned"] for call in owner.sync("calls", header["run_id"]))
        completed = owner.sync("complete_deletion", run["run_id"], command["request_id"], sorted(context_ids),
                               unresolved_provider_calls=unknown, expected_provider_snapshot=snapshot)
        return completed is not None
    finally:
        for child_id in claimed:
            owner.sync("release", child_id)


async def process(owner, run_id, restore_context):
    """Drain claimed maintenance at a worker boundary or in a dedicated idle task.

    Root coordinator supplies its audited, claim-before-constructor restore
    callback. This function never starts/restarts inference or an agent loop.
    Caller releases a claim it already held; newly acquired idle claims release.
    """
    owned = owner.sync("owns", run_id)
    if not owned and not owner.sync("claim_maintenance", run_id):
        return {"processed": 0, "pending": True}
    processed = 0
    try:
        pending = [item for item in owner.sync("pending_commands", run_id) if item["kind"] in KINDS]
        if not pending:
            return {"processed": 0, "pending": False}
        run = owner.sync("get_run", run_id)
        if run["payloads_pruned"]:
            head = owner.sync("get_context_head", run["context_id"])
            if head is None or head["run_id"] != run_id:
                raise MaintenanceHeld("maintenance_context_unavailable")
            run["checkpoint"] = head["checkpoint"]
        context = await _context(restore_context, run)
        from helpers.durable import codec, documents
        for command in pending:
            try:
                value = _request(owner, run, command)
                if command["kind"] == "maintenance_delete":
                    if not await _delete(owner, run, command, restore_context, context):
                        return {"processed": processed, "pending": True}
                    return {"processed": processed + 1, "pending": False, "deleted": True,
                            "context_ids": [item["context_id"] for item in owner.sync("deletion_contexts", command["request_id"])]}
                elif command["kind"] == "maintenance_document":
                    declared = documents.definition(value["kind"])
                    declared.decode(owner.sync("read_document", run["context_id"], value["kind"]))
                    draft = declared.validate(codec.masked(context.agent0, declared.validate(value["value"])))
                    owner.sync("apply_document_command", run_id, command["request_id"], kind=value["kind"],
                               schema_version=declared.schema_version, value=draft, expected_revision=value["expected_revision"])
                else:
                    conflict = next((item for item in owner.sync("list_document_conflicts", run_id)
                                     if item["conflict_id"] == value["conflict_id"]), None)
                    if conflict is None:
                        raise KeyError("Unknown document conflict")
                    declared = documents.definition(conflict["kind"])
                    declared.decode(owner.sync("read_document", run["context_id"], conflict["kind"]))
                    if conflict["schema_version"] != declared.schema_version:
                        raise ValueError("Conflict schema changed")
                    declared.validate(conflict["proposed"])
                    owner.sync("apply_document_command", run_id, command["request_id"],
                               conflict_id=value["conflict_id"], decision=value["decision"], expected_revision=value["expected_revision"])
                processed += 1
            except (ConflictError, StaleRunError, KeyError, ValueError, MaintenanceHeld):
                owner.sync("ack_command", run_id, command["request_id"], result={"accepted": False, "error": "maintenance_rejected"})
                processed += 1
        return {"processed": processed, "pending": False}
    finally:
        if not owned:
            owner.sync("release", run_id)
