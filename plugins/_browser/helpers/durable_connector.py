"""Durable companion browser delivery, reconnect and private profile custody."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid

from plugins._browser.helpers.connector_runtime import ConnectorBrowserRuntime
from plugins._browser.helpers import connector_runtime as transport
from helpers.durable import sessions


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def held(reason):
    sessions._held(reason)


def operation_key(context, run, call, index):
    return digest([context, run, call, index, "host-browser"])


def has_receipt(tool, call):
    turn = sessions._turn(tool)
    if not turn or not call.get("call_id"):
        return False
    manager = sessions._manager(tool)
    return bool(manager.get_manifest("host-browser-op-" + operation_key(manager.context_id, turn.run_id, call["call_id"], 0)))


class DurableConnectorRuntime(ConnectorBrowserRuntime):
    def __init__(self, tool, manager):
        super().__init__(manager.context_id, tool.agent)
        self.tool, self.manager, self.turn = tool, manager, sessions._turn(tool)
        self.index = 0
        self._durable_refs_expired = False

    def envelope(self, payload, operation_id, session, deployment, instance):
        request = dict(payload)
        request["op_id"] = str(uuid.uuid4())
        fingerprint = digest({key: value for key, value in request.items() if key not in {"op_id", "durable"}})
        request["durable"] = {"schema": 1, "deployment": deployment, "session_id": session,
                              "operation_id": operation_id, "fingerprint": fingerprint, "instance_id": instance}
        return request

    async def query(self, sid, action, binding, **extra):
        payload = {"context_id": self.context_id, "action": action,
                   "profile_mode": binding["profile_mode"], "browser_selection": binding["selection"], **extra}
        operation = digest([binding["session"], self.turn.run_id, self.turn.active_call_id, self.index, action, extra])
        request = self.envelope(payload, operation, binding["session"], binding["deployment"], binding["instance"])
        return await self._send_browser_op(sid, request)

    async def _binding(self, sid):
        metadata = transport.host_browser_metadata_for_sid(sid) or {}
        instance = str(metadata.get("durable_instance_id") or "")
        if "durable_session_v1" not in (metadata.get("features") or []) or len(instance) != 64:
            held("host_browser_durable_protocol_required")
        manager = self.manager
        epoch = await asyncio.to_thread(manager.owner.sync, "get_restore_state")
        generation = await asyncio.to_thread(manager.owner.sync, "document_generation", self.context_id)
        deployment = digest(epoch["epoch"])
        config_digest = sessions._digest(transport.get_browser_config(agent=self.agent))
        binding = {"schema": 1, "session": digest([deployment, self.context_id, generation]),
                   "deployment": deployment, "instance": instance, "generation": generation,
                   "config_digest": config_digest, "profile_mode": self._host_browser_profile_mode(),
                   "selection": self._host_browser_selection(sid)}
        prior = await asyncio.to_thread(manager.get_manifest, "host_browser_session")
        previous = prior["value"] if prior else None
        if previous and previous.get("session") == binding["session"]:
            if previous.get("config_digest") != config_digest:
                held("host_browser_session_identity_changed")
            if previous["instance"] != instance:
                if (binding["profile_mode"] != "agent" or not previous.get("snapshot")
                        or previous.get("pending_operation")):
                    held("host_browser_original_instance_required")
                snapshot = await asyncio.to_thread(sessions.get_json, manager, previous["snapshot"])
                await self.query(sid, "durable_import", binding, snapshot=snapshot, restore_documents=True)
                self._durable_refs_expired = True
            else:
                binding.update({key: previous[key] for key in ("snapshot",) if key in previous})
        attached = await self.query(sid, "durable_attach", binding)
        durable = attached.get("durable", {}) if isinstance(attached, dict) else {}
        if durable.get("instance_id") != instance or durable.get("session_id") != binding["session"]:
            held("host_browser_session_identity_changed")
        self._durable_refs_expired = self._durable_refs_expired or bool(durable.get("refs_expired"))
        return binding, prior

    async def _dispatch(self, payload):
        if payload.get("action") == "multi":
            return await transport.run_browser_calls(payload.get("calls"), self._dispatch_call)
        if payload.get("action") == "evaluate":
            script = payload.get("script")
            if not isinstance(script, str) or not script.strip():
                raise ValueError("evaluate requires a non-empty script")
            payload[transport.browser_config.EVALUATE_TIMEOUT_KEY] = transport.browser_config.normalize_evaluate_timeout(
                transport.get_browser_config(self.agent).get(transport.browser_config.EVALUATE_TIMEOUT_KEY,
                    transport.browser_config.DEFAULT_EVALUATE_TIMEOUT_SECONDS))
        self._enforce_privacy(payload)
        manager = self.manager
        index, self.index = self.index, self.index + 1
        job_id = operation_key(self.context_id, self.turn.run_id, self.turn.active_call_id, index)
        kind = "host-browser-op-" + job_id
        from helpers.durable.codec import masked
        from helpers.durable.resources import canonical_value
        semantic = digest(canonical_value(self.agent.context, masked(self.agent,
            {key: value for key, value in payload.items() if key != "op_id"})))
        saved = await asyncio.to_thread(manager.get_manifest, kind)
        if saved and saved["value"].get("semantic") != semantic:
            held("host_browser_operation_identity_changed")
        # Read the original receipt before reconnect/attach: known results require
        # neither another external call nor a surviving connector instance.
        if saved and saved["value"].get("output"):
            return await asyncio.to_thread(sessions.get_json, manager, saved["value"]["output"])
        sid = self._select_sid()
        if not sid:
            held("host_browser_original_instance_required")
        if saved and saved["value"].get("instance") != (transport.host_browser_metadata_for_sid(sid) or {}).get("durable_instance_id"):
            held("host_browser_original_instance_required")
        binding, prior = await self._binding(sid)
        payload["profile_mode"], payload["browser_selection"] = binding["profile_mode"], binding["selection"]
        payload = self._with_browser_helpers(sid, payload)
        request = self.envelope(payload, job_id, binding["session"], binding["deployment"], binding["instance"])
        if saved:
            original = json.loads(await asyncio.to_thread(manager.get_bytes, saved["value"]["request"]))
            if any(original["durable"].get(key) != request["durable"].get(key)
                   for key in ("schema", "deployment", "session_id", "operation_id", "instance_id")):
                held("host_browser_operation_identity_changed")
            request = original
        else:
            if self._durable_refs_expired and any(payload.get(key) is not None for key in ("ref", "target_ref")):
                held("browser_session_requires_fresh_content")
            ref = await asyncio.to_thread(manager.put_bytes, "host_browser_request", job_id, encoded(request), sensitive=True)
            saved = await asyncio.to_thread(manager.publish_manifest, kind,
                {"schema": 1, "request": ref, "instance": binding["instance"], "semantic": semantic}, 0)
        # Mark an external delivery before it can happen. An older exported
        # profile must never be transplanted over a later uncheckpointed effect.
        if not prior or prior["value"].get("pending_operation") != job_id:
            prior = await asyncio.to_thread(manager.publish_manifest, "host_browser_session",
                {**binding, "pending_operation": job_id}, prior["version"] if prior else 0)
            sessions._remember(self.tool, "host_browser_session", prior)
        # The companion's durable journal is the send authority. An authoritative
        # absent result permits delivery; every existing intent is query-only.
        deadline = time.monotonic() + 120
        while True:
            status = await self.query(sid, "durable_status", binding, target_operation_id=job_id)
            status_identity = status.get("durable") or {}
            if (status_identity.get("instance_id") != binding["instance"]
                    or status_identity.get("session_id") != binding["session"]
                    or status_identity.get("operation_id") != job_id):
                held("host_browser_operation_identity_changed")
            state = status_identity.get("state")
            if state == "completed":
                response = status.get("response")
                if not isinstance(response, dict) or not response.get("ok"):
                    held("host_browser_action_outcome_unknown")
                result = response.get("data")
                break
            if state == "absent" and status.get("found") is False:
                result = await self._send_browser_op(sid, request)
                break
            if state == "outcome_unknown" or time.monotonic() > deadline:
                held("host_browser_action_outcome_unknown")
            if state != "running":
                held("host_browser_action_outcome_unknown")
            await asyncio.sleep(.1)
        if not isinstance(result, dict) or (result.get("durable") or {}).get("state") != "completed":
            held("host_browser_action_outcome_unknown")
        if result["durable"].get("instance_id") != binding["instance"] or result["durable"].get("operation_id") != job_id or result["durable"].get("session_id") != binding["session"]:
            held("host_browser_operation_identity_changed")
        # Preserve the true completed output before optional profile export.
        output = await asyncio.to_thread(sessions.put_json, manager, "host_browser_result", job_id, result)
        complete = await asyncio.to_thread(manager.publish_manifest, kind,
                                          {**saved["value"], "output": output}, saved["version"])
        sessions._remember(self.tool, kind, complete)
        if payload.get("action") in {"list", "content"}:
            self._durable_refs_expired = False
        if binding["profile_mode"] == "agent":
            exported = await self.query(sid, "durable_export", binding)
            snapshot = exported.get("snapshot")
            if not isinstance(snapshot, dict):
                held("host_browser_profile_checkpoint_failed")
            binding["snapshot"] = await asyncio.to_thread(sessions.put_json, manager, "host_browser_profile", "snapshot", snapshot)
        manifest = await asyncio.to_thread(manager.publish_manifest, "host_browser_session", binding, prior["version"] if prior else 0)
        sessions._remember(self.tool, "host_browser_session", manifest)
        return result
