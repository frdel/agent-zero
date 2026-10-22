"""Instance-pinned remote desktop operations and retained screenshot receipts."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import time
import uuid

from helpers.durable import sessions
from helpers.durable.resources import ResourceManager, SCHEME


def supports(tool, args):
    from plugins._a0_connector.tools.computer_use_remote import ComputerUseRemote
    execute = type(tool).__dict__.get("execute")
    return (execute is not None and getattr(execute, "__code__", None) == ComputerUseRemote.execute.__code__
            and inspect.getsourcefile(execute) == inspect.getsourcefile(ComputerUseRemote.execute))


def operation_key(context, run, call, index):
    return sessions._digest([context, run, call, index, "computer-use"])


def can_resume(tool, args, call):
    turn = sessions._turn(tool)
    if not turn or not call.get("call_id"):
        return False
    manager = ResourceManager(turn.owner, tool.agent.context.id, turn.run_id)
    return bool(manager.get_manifest("computer-op-" + operation_key(manager.context_id, turn.run_id, call["call_id"], 0)))


async def prepare(tool, args):
    if not supports(tool, args):
        sessions._held("computer_session_adapter_required")
    from helpers.durable.resources import cipher
    cipher()
    tool._durable_computer_manager = sessions._manager(tool)


def _envelope(payload, operation, session, deployment, instance):
    from plugins._browser.helpers.durable_connector import digest
    request = dict(payload, op_id=str(uuid.uuid4()))
    request["durable"] = {"schema": 1, "deployment": deployment, "session_id": session,
                          "operation_id": operation, "instance_id": instance,
                          "fingerprint": digest({key: value for key, value in request.items() if key not in {"op_id", "durable"}})}
    return request


def _data(response):
    return response.get("result", response.get("data")) if isinstance(response, dict) else None


def _normalize(response):
    response = dict(response)
    if "data" in response:
        response["result"] = response.pop("data")
    return response


async def _materialize(tool, manager, response):
    import copy
    response = copy.deepcopy(response)
    data = _data(response)
    if not isinstance(data, dict):
        return response
    ref = data.get("_durable_capture_ref")
    if ref:
        path = str(await asyncio.to_thread(manager.materialize, ref))
        with manager.owner.lock:
            context = tool.agent.context
            state = getattr(context, "_durable_resources", {"version": 1})
            attachments = state.setdefault("attachments", [])
            if ref not in attachments:
                attachments.append(ref)
            context._durable_resources = state
            paths = getattr(context, "_durable_resource_paths", {})
            paths[path] = SCHEME + ref["id"]
            context._durable_resource_paths = paths
        data["path"] = path
    return response


async def dispatch(tool, sid, payload, exchange):
    from plugins._a0_connector.helpers.ws_runtime import computer_use_metadata_for_sid
    from helpers.durable.codec import masked
    from helpers.durable.resources import canonical_value
    turn = sessions._turn(tool)
    if not hasattr(tool, "_durable_computer_manager"):
        await prepare(tool, {})
    manager = tool._durable_computer_manager
    index = getattr(tool, "_durable_dispatch_index", 0)
    tool._durable_dispatch_index = index + 1
    if not turn.active_call_id:
        sessions._held("computer_call_identity_missing")
    operation = operation_key(manager.context_id, turn.run_id, turn.active_call_id, index)
    kind = "computer-op-" + operation
    semantic = sessions._digest(canonical_value(tool.agent.context, masked(tool.agent,
        {key: value for key, value in payload.items() if key not in {"op_id", "durable"}})))
    saved = await asyncio.to_thread(manager.get_manifest, kind)
    if saved:
        if saved["value"].get("semantic") != semantic:
            sessions._held("computer_operation_identity_changed")
        if saved["value"].get("output"):
            response = await asyncio.to_thread(sessions.get_json, manager, saved["value"]["output"])
            return await _materialize(tool, manager, response)
    metadata = computer_use_metadata_for_sid(sid) or {}
    instance = str(metadata.get("durable_instance_id") or "")
    if (not sid or "computer_use_durable_v1" not in (metadata.get("features") or [])
            or len(instance) != 64 or not metadata.get("enabled") or not metadata.get("supported")
            or str(metadata.get("status", "")).lower() == "rearm required"):
        sessions._held("computer_durable_approved_host_required")
    if saved and saved["value"].get("instance") != instance:
        sessions._held("computer_original_instance_required")
    epoch = await asyncio.to_thread(manager.owner.sync, "get_restore_state")
    generation = await asyncio.to_thread(manager.owner.sync, "document_generation", manager.context_id)
    deployment = sessions._digest(epoch["epoch"])
    session = sessions._digest([deployment, manager.context_id, generation, "computer"])
    request = _envelope(payload, operation, session, deployment, instance)
    if saved:
        request = await asyncio.to_thread(sessions.get_json, manager, saved["value"]["request"])
        if request["durable"]["session_id"] != session or request["durable"]["deployment"] != deployment:
            sessions._held("computer_session_identity_changed")
    else:
        await asyncio.to_thread(manager.owner.sync, "assert_owner", turn.run_id)
        ref = await asyncio.to_thread(sessions.put_json, manager, "computer_request", operation, request)
        saved = await asyncio.to_thread(manager.publish_manifest, kind,
            {"schema": 1, "instance": instance, "semantic": semantic, "request": ref}, 0)
        sessions._remember(tool, kind, saved)
    query = _envelope({"context_id": manager.context_id, "action": "durable_status", "target_operation_id": operation},
                      sessions._digest([operation, "status"]), session, deployment, instance)
    deadline = time.monotonic() + 180
    try:
        while True:
            await asyncio.to_thread(manager.owner.sync, "assert_owner", turn.run_id)
            status = await exchange(sid=sid, payload=query)
            data = _data(status)
            if not status.get("ok") or not isinstance(data, dict):
                sessions._held("computer_action_outcome_unknown")
            durable = data.get("durable") or data
            if (durable.get("instance_id") != instance or durable.get("session_id") != session
                    or durable.get("operation_id") != operation):
                sessions._held("computer_original_instance_required")
            state = durable.get("state")
            if state == "completed":
                response = data.get("response")
                if not isinstance(response, dict):
                    sessions._held("computer_action_outcome_unknown")
                response = _normalize(response)
                break
            if state == "absent" and data.get("found") is False:
                await asyncio.to_thread(manager.owner.sync, "assert_owner", turn.run_id)
                response = _normalize(await exchange(sid=sid, payload=request))
                break
            if state != "running" or time.monotonic() > deadline:
                sessions._held("computer_action_outcome_unknown")
            await asyncio.sleep(.1)
        data = _data(response)
        durable = data.get("durable", {}) if isinstance(data, dict) else {}
        if (durable.get("state") != "completed" or durable.get("instance_id") != instance
                or durable.get("operation_id") != operation or durable.get("session_id") != session):
            sessions._held("computer_action_outcome_unknown")
        # Retain exact bytes before optional image materialization. Server-provided
        # filesystem paths are never treated as a path on another worker.
        if isinstance(data, dict):
            data.pop("_durable_capture_ref", None)
            if payload.get("action") == "capture" or isinstance(data.get("artifact"), dict):
                for key in ("path", "capture_path", "container_path", "host_path"):
                    data.pop(key, None)
        output = await asyncio.to_thread(sessions.put_json, manager, "computer_result", operation, response)
        committed = await asyncio.to_thread(manager.publish_manifest, kind,
                                           {**saved["value"], "output": output}, saved["version"])
        sessions._remember(tool, kind, committed)
        if isinstance(data, dict):
            artifact = data.get("artifact")
            if isinstance(artifact, dict) and artifact.get("encoding") == "base64":
                body = base64.b64decode(artifact.get("data", ""), validate=True)
                from helpers.durable.resource_store import MAX_RESOURCE
                if len(body) <= MAX_RESOURCE:
                    data["_durable_capture_ref"] = await asyncio.to_thread(manager.put_bytes, "computer_capture",
                        str(artifact.get("filename") or "capture.png"), body, sensitive=True)
        if isinstance(data, dict) and data.get("_durable_capture_ref"):
            data.pop("artifact", None)
            output = await asyncio.to_thread(sessions.put_json, manager, "computer_result", operation, response)
            committed = await asyncio.to_thread(manager.publish_manifest, kind,
                                               {**committed["value"], "output": output}, committed["version"])
            sessions._remember(tool, kind, committed)
        return await _materialize(tool, manager, response)
    except Exception:
        sessions._held("computer_action_outcome_unknown")


async def reconcile_unknown(tool, args, call):
    # Receipt delivery is resumed through the exact source-pinned tool path;
    # it recreates the same indexed start/action/capture sequence from results.
    return None
