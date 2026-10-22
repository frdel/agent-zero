"""Detached, fenced browser actor with immutable per-operation shared receipts.

A running send intent is never delivered a second time. The independent actor
can finish the original operation/profile while its requesting framework dies.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import socket
import tempfile
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time

from helpers.durable.resources import ResourceManager
from plugins._browser.helpers import profile_checkpoint

_READS = {"list", "state", "content", "detail", "screenshot", "screenshot_file", "interactive_session", "annotation_target"}
_REF_METHODS = {"click", "type", "submit", "type_submit", "hover", "double_click", "right_click", "drag", "detail", "select_option", "set_checked", "upload_file"}
_METHODS = _READS | {"open", "navigate", "back", "forward", "reload", "set_active", "click", "type", "submit", "type_submit", "scroll", "evaluate", "key_chord", "hover", "double_click", "right_click", "drag", "wheel", "keyboard", "clipboard", "set_viewport", "select_option", "set_checked", "upload_file", "mouse", "multi", "close_browser", "close_all_browsers"}
_PROCESSES = {}


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _held(reason):
    from helpers.durable.runtime import RecoveryHeld
    raise RecoveryHeld(reason)


def _requires_refs(method, args):
    if method in _REF_METHODS:
        return True
    if method == "multi":
        def visit(calls):
            return any(call.get("action") in _REF_METHODS or visit(call.get("calls", [])) for call in calls)
        return visit(args[0])
    return False


def _key(context, run, call, index):
    return hashlib.sha256(f"{context}:{run}:{call}:{index}".encode()).hexdigest()


def has_receipt(tool, call):
    from helpers.durable.runtime import current
    turn = current(tool.agent)
    if not turn or not getattr(turn.owner, "distributed", False):
        return False
    manager = ResourceManager(turn.owner, tool.agent.context.id, turn.run_id)
    return bool(manager.get_manifest("browser-op-" + _key(manager.context_id, turn.run_id, call["call_id"], 0)))


def _spawn(context, namespace):
    process = _PROCESSES.get((context, namespace))
    if process is not None and process.poll() is None:
        return
    if not os.environ.get("A0_DURABILITY_POSTGRES_DSN"):
        _held("browser_broker_database_configuration_missing")
    environment = dict(os.environ, A0_DURABILITY_BROWSER_NAMESPACE=namespace)
    _PROCESSES[(context, namespace)] = subprocess.Popen(
        [sys.executable, "-m", "plugins._browser.helpers.session_broker", "--serve", context],
        cwd=Path(__file__).resolve().parents[3], env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True)


class BrokerRuntime:
    def __init__(self, tool, manager, config, identity):
        from helpers.durable.runtime import current
        self.tool, self.manager, self.config, self.identity = tool, manager, config, identity
        self.turn = current(tool.agent)
        self.index = 0
        self._durable_refs_expired = False

    async def call(self, method, *args, **kwargs):
        if method not in _METHODS:
            _held("browser_broker_method_unsupported")
        manager, turn = self.manager, self.turn
        index, self.index = self.index, self.index + 1
        call_id = turn.active_call_id
        if not call_id:
            _held("browser_broker_call_identity_missing")
        job_id = _key(manager.context_id, turn.run_id, call_id, index)
        kind = "browser-op-" + job_id
        from helpers.durable.codec import masked
        from helpers.durable.resources import canonical_value
        canonical = canonical_value(self.tool.agent.context, masked(self.tool.agent, {"method": method, "args": list(args), "kwargs": kwargs}))
        fingerprint = _digest({"schema": 1, "operation": canonical, "identity": self.identity})
        saved = await asyncio.to_thread(manager.get_manifest, kind)
        if saved:
            if saved["value"].get("fingerprint") != fingerprint:
                _held("browser_operation_identity_changed")
        else:
            previous_queue = await asyncio.to_thread(manager.get_manifest, "browser_queue")
            generation = await asyncio.to_thread(turn.owner.sync, "document_generation", manager.context_id)
            if previous_queue and previous_queue["value"].get("generation") == generation:
                for previous_op in previous_queue["value"].get("operations", []):
                    previous_job = await asyncio.to_thread(turn.owner.sync, "get_resource_job", previous_op["job_id"])
                    if previous_job and (previous_job.get("result") or {}).get("session_unavailable"):
                        _held("browser_session_checkpoint_failed")
            token = secrets.token_hex(32)
            descriptor = {"schema": 1, "job_id": job_id, "token": token, "fingerprint": fingerprint,
                          "context_id": manager.context_id, "run_id": turn.run_id, "call_id": call_id,
                          "method": method, "args": copy.deepcopy(list(args)), "kwargs": copy.deepcopy(kwargs), "config": self.config,
                          "identity": self.identity}
            _capture_uploads(manager, descriptor)
            ref = await asyncio.to_thread(manager.put_bytes, "browser_operation", job_id, _encoded(descriptor), sensitive=True)
            await asyncio.to_thread(turn.owner.sync, "register_resource_job", turn.run_id, job_id, fingerprint, hashlib.sha256(token.encode()).hexdigest())
            saved = await asyncio.to_thread(manager.publish_manifest, kind, {"schema": 1, "job_id": job_id, "descriptor": ref, "fingerprint": fingerprint}, 0)
        await self._enqueue(saved["value"])
        namespace = getattr(turn.owner.store, "namespace", "agent_zero")
        deadline, last_spawn = time.monotonic() + 120, 0
        while True:
            job = await asyncio.to_thread(turn.owner.sync, "get_resource_job", job_id)
            if job and job["status"] == "completed":
                result = job["result"]
                if result.get("fingerprint") != fingerprint or result.get("status") != "completed":
                    _held("browser_broker_operation_unknown")
                output = json.loads(await asyncio.to_thread(manager.get_bytes, result["output"]))
                body = output["value"]
                if result.get("session"):
                    prior = await asyncio.to_thread(manager.get_manifest, "browser_session")
                    incoming = result["session"]
                    old_order = (prior["value"].get("admission_seq", -1), prior["value"].get("order", -1)) if prior else (-1, -1)
                    new_order = (incoming.get("admission_seq", -1), incoming.get("order", -1))
                    if new_order > old_order:
                        manifest = await asyncio.to_thread(manager.publish_manifest, "browser_session", incoming, prior["version"] if prior else 0)
                    else:
                        manifest = prior
                    from helpers.durable.sessions import _remember
                    _remember(self.tool, "browser_session", manifest)
                body = await _materialize_output(self.tool, manager, body, output.get("artifacts", {}))
                await _install_view(self.tool, manager, output.get("broker"), _digest(self.config))
                return body
            if time.monotonic() > deadline:
                _held("browser_broker_operation_unknown")
            if time.monotonic() - last_spawn > 2:
                await asyncio.to_thread(_spawn, manager.context_id, namespace)
                last_spawn = time.monotonic()
            await asyncio.sleep(.1)

    async def _enqueue(self, operation):
        manager = self.manager
        queue = await asyncio.to_thread(manager.get_manifest, "browser_queue")
        epoch = await asyncio.to_thread(manager.owner.sync, "get_restore_state")
        generation = await asyncio.to_thread(manager.owner.sync, "document_generation", manager.context_id)
        session = _digest([manager.context_id, self.turn.run_id, epoch["epoch"], generation])
        old = queue["value"] if queue else {}
        if old.get("session") == session:
            value = dict(old, operations=list(old["operations"]))
        else:
            base = await asyncio.to_thread(manager.get_manifest, "browser_session")
            value = {"schema": 1, "session": session, "run_id": self.turn.run_id,
                     "epoch": epoch["epoch"], "generation": generation,
                     "base": base["value"] if base else None,
                     "base_job": old.get("operations", [{}])[-1].get("job_id") if old.get("operations") else None,
                     "operations": [], "next_order": 0}
        if not any(item["job_id"] == operation["job_id"] for item in value["operations"]):
            if len(value["operations"]) >= 100:
                # Completed receipts retain immutable per-operation manifests.
                value["operations"] = [item for item in value["operations"]
                    if manager.owner.sync("get_resource_job", item["job_id"])["status"] != "completed"]
            value["operations"].append(dict(operation, order=value.get("next_order", 0)))
            value["next_order"] = value.get("next_order", 0) + 1
            queue = await asyncio.to_thread(manager.publish_manifest, "browser_queue", value, queue["version"] if queue else 0)
        from helpers.durable.sessions import _remember
        _remember(self.tool, "browser_queue", queue)


def _capture_uploads(manager, descriptor):
    from helpers import files
    from helpers.durable.resources import read_regular
    def capture(values):
        paths = values.pop("paths", None) or ([values.pop("path")] if values.get("path") else [])
        return [manager.put_bytes("browser_upload", Path(path).name,
                                 read_regular(files.get_abs_path(path)), sensitive=True) for path in paths]
    def visit(calls):
        for call in calls:
            if call.get("action") == "upload_file":
                call["_durable_uploads"] = capture(call)
            if isinstance(call.get("calls"), list):
                visit(call["calls"])
    if descriptor["method"] == "upload_file":
        descriptor["uploads"] = capture(descriptor["kwargs"])
    elif descriptor["method"] == "multi":
        visit(descriptor["args"][0])


def _restore_uploads(manager, descriptor):
    if descriptor.get("uploads"):
        descriptor["kwargs"]["paths"] = [str(manager.materialize(ref)) for ref in descriptor["uploads"]]
    def visit(calls):
        for call in calls:
            if "_durable_uploads" in call:
                call["paths"] = [str(manager.materialize(ref)) for ref in call.pop("_durable_uploads")]
            if isinstance(call.get("calls"), list):
                visit(call["calls"])
    if descriptor["method"] == "multi":
        visit(descriptor["args"][0])


async def _materialize_output(tool, manager, value, artifacts):
    replacements = {}
    context = tool.agent.context
    from helpers.durable.resources import SCHEME
    for original, ref in artifacts.items():
        local = str(await asyncio.to_thread(manager.materialize, ref))
        replacements[original] = local
        with manager.owner.lock:
            state = getattr(context, "_durable_resources", {"version": 1})
            existing = {item["id"]: item for item in state.get("attachments", [])}
            existing[ref["id"]] = ref
            state["attachments"] = list(existing.values())
            context._durable_resources = state
            mappings = getattr(context, "_durable_resource_paths", {})
            mappings[local] = SCHEME + ref["id"]
            context._durable_resource_paths = mappings
    def visit(item):
        if isinstance(item, str):
            return replacements.get(item, item)
        if isinstance(item, list):
            return [visit(child) for child in item]
        if isinstance(item, dict):
            return {key: visit(child) for key, child in item.items()}
        return item
    return visit(value)


def _artifacts(manager, result):
    found = {}
    def visit(item):
        if isinstance(item, dict):
            path = item.get("path")
            if isinstance(path, str) and Path(path).is_file():
                from helpers.durable.resources import read_regular
                ref = manager.put_bytes("browser_artifact", Path(path).name, read_regular(path), sensitive=True)
                found[path] = ref
                if isinstance(item.get("a0_path"), str):
                    found[item["a0_path"]] = ref
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(result)
    return found


async def serve(context_id):
    from helpers.durable.postgres import PostgresStore
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore
    namespace = os.environ.get("A0_DURABILITY_BROWSER_NAMESPACE", "agent_zero")
    store = PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"], namespace=namespace, worker_id="browser-" + str(os.getpid()))
    class Owner:
        def sync(self, method, *args, **kwargs):
            return getattr(store, method)(*args, **kwargs)
    owner = Owner()
    manager = ResourceManager(owner, context_id)
    role = "browser-" + hashlib.sha256(context_id.encode()).hexdigest()
    core, session, last_session, idle = None, None, None, time.monotonic()
    actor_lock = asyncio.Lock()
    ipc_root = Path(tempfile.mkdtemp(prefix="a0-browser-"))
    ipc = {"path": str(ipc_root / "control.sock"), "token": secrets.token_hex(32),
           "host": hashlib.sha256(os.uname().nodename.encode()).hexdigest(), "pid": os.getpid()}
    async def local_request(reader, writer):
        try:
            payload = json.loads(await asyncio.wait_for(reader.readline(), timeout=10))
            if not hmac.compare_digest(str(payload.get("token", "")), ipc["token"]):
                raise ValueError("Browser actor authentication failed")
            current = manager.get_manifest("browser_queue")
            if not current or current["value"]["session"] != session:
                raise ValueError("Browser actor custody changed")
            method = payload.get("method")
            allowed = _METHODS | {"interactive_viewer", "zoom", "annotation_target", "close_context"}
            if method not in allowed or core is None:
                raise ValueError("Browser actor method is unavailable")
            async with actor_lock:
                result = await getattr(core, method)(*payload.get("args", []), **payload.get("kwargs", {}))
            response = {"ok": True, "value": result}
            if method == "interactive_viewer" and isinstance(result, dict) and result.get("available"):
                response["display"] = {"token": core.interactive_view.token, "port": core.interactive_view.port}
        except Exception:
            response = {"ok": False, "error": "Browser actor request failed"}
        writer.write(_encoded(response) + b"\n")
        try:
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    ipc_server = None
    try:
        if not store.try_role(role):
            return
        ipc_server = await asyncio.start_unix_server(local_request, path=ipc["path"], limit=12 * 1024 * 1024)
        Path(ipc["path"]).chmod(0o600)
        while time.monotonic() - idle < 1800:
            queue = manager.get_manifest("browser_queue")
            if not queue:
                return
            value = queue["value"]
            if session is not None and value["session"] != session:
                return  # Release the old actor before another run can act.
            if value["epoch"] != store.get_restore_state()["epoch"] or value["generation"] != store.document_generation(context_id):
                return
            session = value["session"]
            progressed = False
            for operation in value["operations"]:
                job = store.get_resource_job(operation["job_id"])
                if job["status"] == "completed":
                    continue
                descriptor = json.loads(manager.get_bytes(operation["descriptor"]))
                if descriptor["fingerprint"] != operation["fingerprint"] or descriptor["method"] not in _METHODS:
                    return
                token, job_id = descriptor["token"], descriptor["job_id"]
                try:
                    granted = store.begin_resource_job(job_id, token, role)
                except Exception:
                    run = store.get_run(descriptor["run_id"])
                    if run["status"] == "running" and run["checkpoint"].get("paused"):
                        await asyncio.sleep(.1)
                        break
                    return
                if not granted:
                    return  # A prior actor's unresolved send can never be repeated.
                job_manager = ResourceManager(owner, context_id, job_id=job_id, job_token=token)
                actual_output = None
                artifacts = {}
                try:
                    await actor_lock.acquire()
                    if core is None:
                        core = _BrowserRuntimeCore(context_id, durable=True, profile=True)
                        core._durable_config = descriptor["config"]
                        base = value.get("base")
                        if value.get("base_job"):
                            previous = store.get_resource_job(value["base_job"])
                            if previous and previous["status"] == "completed" and previous["result"].get("session"):
                                base = previous["result"]["session"]
                        if profile_checkpoint.identity(descriptor["config"], descriptor["identity"]) != descriptor["identity"]:
                            raise ValueError("Browser runtime identity changed")
                        if base:
                            if base.get("schema") == 2:
                                if base["identity"] != descriptor["identity"]:
                                    raise ValueError("Browser profile identity changed")
                                profile_checkpoint.restore(manager, base["profile"], core.durable_root)
                            snapshot = json.loads(manager.get_bytes(base["state"]))
                            await core.durable_restore(snapshot)
                            core._durable_refs_expired = True
                    if store.get_run(descriptor["run_id"])["status"] == "cancelled":
                        raise ValueError("Browser operation was cancelled before dispatch")
                    kwargs = descriptor["kwargs"]
                    _restore_uploads(job_manager, descriptor)
                    method = descriptor["method"]
                    # Reads refresh persistent state before generating new DOM refs.
                    # Effects checkpoint after their original delivery, never replay.
                    if method in _READS and method != "detail" and core.context is not None:
                        closed = await core.durable_profile_checkpoint()
                        profile = profile_checkpoint.capture(job_manager, closed["root"])
                        await core.durable_profile_resume(closed["snapshot"])
                        core._durable_refs_expired = True
                        last_session = {"schema": 2, "state": job_manager.put_bytes("browser_session", "state", _encoded(closed["snapshot"]), sensitive=True),
                                        "profile": profile, "identity": descriptor["identity"], "config_digest": _digest(descriptor["config"])}
                    async def deliver():
                        if _requires_refs(method, descriptor["args"]) and getattr(core, "_durable_refs_expired", False):
                            return {"error": "Browser references expired after profile recovery; request fresh content first", "refs_expired": True}
                        outcome = await getattr(core, method)(*descriptor["args"], **kwargs)
                        if method == "content" or method == "list" and kwargs.get("include_content"):
                            core._durable_refs_expired = False
                        return outcome
                    action = asyncio.create_task(deliver())
                    while not action.done():
                        done, _ = await asyncio.wait({action}, timeout=.1)
                        if not done:
                            run = store.get_run(descriptor["run_id"])
                            if run["status"] == "cancelled" or store.document_generation(context_id) != value["generation"]:
                                action.cancel()
                                await asyncio.gather(action, return_exceptions=True)
                                raise ValueError("Browser action cancellation outcome is unknown")
                    result = action.result()
                    # Preserve the true response before any subsequent file/profile
                    # capture can fail. A broken checkpoint never erases a known effect.
                    actual_output = job_manager.put_bytes("browser_result", job_id + "-body",
                        _encoded({"value": result, "broker": ipc, "artifacts": {}}), sensitive=True)
                    artifacts = _artifacts(job_manager, result)
                    if method not in _READS or last_session is None:
                        closed = await core.durable_profile_checkpoint()
                        profile = profile_checkpoint.capture(job_manager, closed["root"])
                        last_session = {"schema": 2, "state": job_manager.put_bytes("browser_session", "state", _encoded(closed["snapshot"]), sensitive=True),
                                        "profile": profile, "identity": descriptor["identity"], "config_digest": _digest(descriptor["config"])}
                        await core.durable_profile_resume(closed["snapshot"])
                        core._durable_refs_expired = True
                    if isinstance(result, dict):
                        result["refs_expired"] = bool(getattr(core, "_durable_refs_expired", False))
                    last_session = dict(last_session, source_run=descriptor["run_id"],
                                        admission_seq=store.get_run(descriptor["run_id"]).get("admission_seq", 0),
                                        order=operation["order"])
                    output = job_manager.put_bytes("browser_result", job_id, _encoded({"value": result, "broker": ipc, "artifacts": artifacts}), sensitive=True)
                    store.finish_resource_job(job_id, token, {"schema": 1, "status": "completed", "fingerprint": descriptor["fingerprint"],
                                                             "output": output, "session": last_session, "artifact_refs": list(artifacts.values())})
                    progressed, idle = True, time.monotonic()
                except Exception:
                    # Private diagnostics are encrypted; public receipts retain a
                    # fixed outcome classification, never a fabricated tool result.
                    import traceback
                    try:
                        diagnostic = {"diagnostic": job_manager.put_bytes("browser_diagnostic", job_id, traceback.format_exc()[-16384:].encode(), sensitive=True)}
                    except Exception:
                        diagnostic = {}  # A full resource quota must not erase a retained body.
                    if actual_output is not None:
                        store.finish_resource_job(job_id, token, {"schema": 1, "status": "completed",
                            "fingerprint": descriptor["fingerprint"], "output": actual_output,
                            "session_unavailable": True, **diagnostic,
                            "artifact_refs": list(artifacts.values())})
                    else:
                        store.finish_resource_job(job_id, token, {"schema": 1, "status": "unknown", "fingerprint": descriptor["fingerprint"], **diagnostic})
                    return
                finally:
                    if actor_lock.locked():
                        actor_lock.release()
            if not progressed:
                await asyncio.sleep(.1)
    finally:
        if ipc_server:
            ipc_server.close()
            await ipc_server.wait_closed()
        shutil.rmtree(ipc_root, ignore_errors=True)
        if core:
            try:
                await core.close()
            finally:
                if core._durable_root:
                    shutil.rmtree(core._durable_root, ignore_errors=True)
        store.release_role(role)
        store.close()


class BrokerView:
    def __init__(self, tool, manager, ipc, binding):
        self._durable_tool, self._durable_manager, self._durable_binding = tool, manager, binding
        self._durable_initialized = True
        self.ipc, self._runtime = ipc, self

    async def call(self, method, *args, **kwargs):
        from helpers.durable.sessions import cached_browser_current
        if not await cached_browser_current(self):
            raise RuntimeError("Browser actor custody changed; prepare its owner first")
        result = await asyncio.to_thread(_ipc_call, self.ipc, method, args, kwargs)
        if result.get("display"):
            from helpers import virtual_desktop
            display = result["display"]
            virtual_desktop.register_session(token=display["token"], host="127.0.0.1", port=display["port"],
                                            owner="browser", title="Browser")
        return result["value"]

    async def close(self, **kwargs):
        # Framework shutdown detaches its view; the actor survives the requester.
        self._durable_initialized = False


def _ipc_call(ipc, method, args, kwargs):
    if ipc["host"] != hashlib.sha256(os.uname().nodename.encode()).hexdigest():
        raise RuntimeError("The live browser viewer belongs to another framework host")
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(30)
        connection.connect(ipc["path"])
        connection.sendall(_encoded({"token": ipc["token"], "method": method, "args": list(args), "kwargs": kwargs}) + b"\n")
        with connection.makefile("rb") as stream:
            data = stream.readline(12 * 1024 * 1024)
        result = json.loads(data)
    if not result.get("ok"):
        raise RuntimeError("The browser actor request did not complete")
    return result


async def _install_view(tool, manager, ipc, config_digest):
    if not ipc:
        return
    from helpers.durable.sessions import _browser_custody
    from plugins._browser.helpers import runtime
    binding, _ = await asyncio.to_thread(_browser_custody, manager, config_digest)
    view = BrokerView(tool, manager, ipc, binding)
    with runtime._runtime_lock:
        runtime._durable_runtimes[manager.context_id] = view
        runtime._runtimes[manager.context_id] = view


async def _main(context):
    import signal
    task = asyncio.create_task(serve(context))
    loop = asyncio.get_running_loop()
    for event in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(event, task.cancel)
    try:
        await task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve":
        asyncio.run(_main(sys.argv[2]))
