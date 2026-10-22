"""Detached MCP delivery with an immutable shared outcome and local credentials.

Only a submitted job may acquire a send grant. A running job is never sent
again, even when its original requester disappears. Server credentials remain
inside an encrypted, owner-only spool on the configured host.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from helpers.durable.resources import ResourceManager, cipher, read_regular

_PROCESSES = {}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def key(context, run, call):
    return digest([context, run, call, "mcp"])


def held(reason):
    from helpers.durable.runtime import RecoveryHeld
    raise RecoveryHeld(reason)


def has_receipt(tool, call):
    from helpers.durable.runtime import current
    turn = current(tool.agent)
    if not turn or not call.get("call_id") or not getattr(turn.owner, "distributed", False):
        return False
    manager = ResourceManager(turn.owner, tool.agent.context.id, turn.run_id)
    return bool(manager.get_manifest("mcp-op-" + key(manager.context_id, turn.run_id, call["call_id"])))


def spool(job_id):
    from helpers import files
    from helpers.durable.resources import private_directory
    directory = private_directory(files.get_abs_path("usr/durability/mcp"))
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        held("mcp_private_configuration_custody_unavailable")
    return directory / (job_id + ".fernet")


def write_spool(path, value):
    body = cipher().encrypt(encoded(value))
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        old = json.loads(cipher().decrypt(read_regular(path)))
        if old != value:
            held("mcp_private_configuration_changed")
        return
    with os.fdopen(descriptor, "wb") as output:
        output.write(body)
        output.flush()
        os.fsync(output.fileno())


def spawn(job_id, namespace):
    process = _PROCESSES.get((job_id, namespace))
    if process and process.poll() is None:
        return
    environment = dict(os.environ, A0_DURABILITY_MCP_NAMESPACE=namespace)
    _PROCESSES[(job_id, namespace)] = subprocess.Popen(
        [sys.executable, "-m", "helpers.durable.mcp_broker", job_id],
        cwd=Path(__file__).resolve().parents[2], env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, start_new_session=True)


async def invoke(tool, config, args):
    from helpers.durable import sessions
    from helpers.durable.runtime import current
    from helpers.durable.codec import masked
    from helpers.durable.resources import canonical_value
    from helpers.mcp_handler import _split_qualified_tool_name
    from mcp.types import CallToolResult
    turn = current(tool.agent)
    manager = tool._durable_session_manager
    if not turn.active_call_id:
        held("mcp_call_identity_missing")
    job_id = key(manager.context_id, turn.run_id, turn.active_call_id)
    kind = "mcp-op-" + job_id
    server_name, name = _split_qualified_tool_name(tool.name)
    server = next((item for item in config.servers if item.name == server_name and not item.disabled), None)
    if server is None or name in server.disabled_tools:
        held("mcp_server_or_tool_disabled")
    config_digest = digest(server.model_dump(mode="json"))
    canonical = canonical_value(tool.agent.context, masked(tool.agent, args))
    fingerprint = digest({"name": tool.name, "args": canonical, "config": config_digest})
    saved = await asyncio.to_thread(manager.get_manifest, kind)
    if saved and saved["value"].get("fingerprint") != fingerprint:
        held("mcp_operation_identity_changed")
    if not saved:
        await config.validate_durable_session(tool)
        descriptor = await asyncio.to_thread(manager.get_manifest, "mcp_" + sessions._digest(tool.name)[:24])
        token = secrets.token_hex(32)
        private = {"schema": 1, "context_id": manager.context_id, "run_id": turn.run_id,
                   "job_id": job_id, "token": token, "name": tool.name, "args": args,
                   "server": server.model_dump(mode="json"), "descriptor": descriptor,
                   "fingerprint": fingerprint}
        shared = {key: value for key, value in private.items() if key != "server"}
        operation = await asyncio.to_thread(sessions.put_json, manager, "mcp_operation", job_id, shared)
        await asyncio.to_thread(write_spool, spool(job_id), private)
        await asyncio.to_thread(turn.owner.sync, "register_resource_job", turn.run_id, job_id,
                                fingerprint, hashlib.sha256(token.encode()).hexdigest())
        saved = await asyncio.to_thread(manager.publish_manifest, kind,
                                        {"schema": 1, "job_id": job_id, "fingerprint": fingerprint, "operation": operation}, 0)
    sessions._remember(tool, kind, saved)
    namespace = getattr(turn.owner.store, "namespace", "agent_zero")
    deadline, last_spawn = time.monotonic() + max(server.tool_timeout or 120, 120) + 30, 0
    while True:
        job = await asyncio.to_thread(turn.owner.sync, "get_resource_job", job_id)
        if job and job["status"] == "completed":
            result = job["result"]
            if result.get("status") != "completed" or result.get("fingerprint") != fingerprint:
                held("mcp_call_outcome_unknown")
            body = await asyncio.to_thread(sessions.get_json, manager, result["output"])
            spool(job_id).unlink(missing_ok=True)
            return CallToolResult.model_validate(body)
        # A different host must not recreate a running call. Original actor can
        # still publish its result; a submitted call needs local configured custody.
        if job and job["status"] == "submitted" and time.monotonic() - last_spawn > 2:
            if not spool(job_id).is_file():
                operation = saved["value"].get("operation")
                if not operation:
                    held("mcp_submitted_call_requires_original_configuration_host")
                shared = await asyncio.to_thread(sessions.get_json, manager, operation)
                if shared.get("fingerprint") != fingerprint or shared.get("job_id") != job_id:
                    held("mcp_operation_identity_changed")
                # Only locally configured server credentials enter this host spool.
                await asyncio.to_thread(write_spool, spool(job_id),
                                        {**shared, "server": server.model_dump(mode="json")})
            await asyncio.to_thread(spawn, job_id, namespace)
            last_spawn = time.monotonic()
        if time.monotonic() > deadline:
            held("mcp_call_outcome_unknown")
        await asyncio.sleep(.1)


async def serve(job_id):
    from helpers.durable.postgres import PostgresStore
    from helpers.mcp_handler import MCPServerLocal, MCPServerRemote, _split_qualified_tool_name
    private = json.loads(cipher().decrypt(read_regular(spool(job_id))))
    if private.get("job_id") != job_id:
        raise ValueError("MCP configuration identity changed")
    store = PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"],
                          namespace=os.environ["A0_DURABILITY_MCP_NAMESPACE"],
                          worker_id="mcp-" + str(os.getpid()))
    role = "mcp-" + job_id
    class Owner:
        lock = threading.RLock()
        def sync(self, method, *args, **kwargs):
            return getattr(store, method)(*args, **kwargs)
    manager = ResourceManager(Owner(), private["context_id"], job_id=job_id, job_token=private["token"])
    granted = False
    try:
        if not store.try_role(role):
            return
        while True:
            try:
                granted = store.begin_resource_job(job_id, private["token"], role)
                break
            except Exception:
                run = store.get_run(private["run_id"])
                if run["status"] == "running" and run["checkpoint"].get("paused"):
                    await asyncio.sleep(.1)
                    continue
                return
        if not granted:
            return
        server_type = MCPServerLocal if private["server"]["type"] == "stdio" else MCPServerRemote
        server = server_type(private["server"])
        tool = SimpleNamespace(name=private["name"], _durable_session_manager=manager,
                               _durable_expected_descriptor=private["descriptor"])
        name = _split_qualified_tool_name(private["name"])[1]
        response = await server.call_tool(name, private["args"], durable_tool=tool)
        from helpers.durable.sessions import put_json
        output = put_json(manager, "mcp_result", job_id,
                          response.model_dump(mode="json", by_alias=True, exclude_none=True))
        store.finish_resource_job(job_id, private["token"],
                                  {"status": "completed", "fingerprint": private["fingerprint"], "output": output})
    except BaseException:
        if granted:
            try:
                import traceback
                diagnostic = manager.put_bytes("mcp_diagnostic", job_id, traceback.format_exc().encode(), sensitive=True)
                store.finish_resource_job(job_id, private["token"],
                    {"status": "outcome_unknown", "fingerprint": private["fingerprint"], "diagnostic": diagnostic})
            except Exception:
                pass
        raise
    finally:
        try:
            store.release_role(role)
        finally:
            store.close()
        # A running intent without result is never replayed, with or without spool.
        if granted:
            spool(job_id).unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 2 or len(sys.argv[1]) != 64 or any(c not in "0123456789abcdef" for c in sys.argv[1]):
        raise SystemExit("Expected operation identity")
    asyncio.run(serve(sys.argv[1]))
