"""Private browser/MCP session recovery; session restoration never replays effects."""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from pathlib import Path
from urllib.parse import urlsplit


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _held(reason):
    from helpers.durable.runtime import RecoveryHeld
    raise RecoveryHeld(reason)


def _turn(tool):
    from helpers.durable.runtime import current
    return current(tool.agent)


def _manager(tool):
    from helpers.durable.resources import ResourceManager
    turn = _turn(tool)
    if turn is None:
        _held("session_requires_durable_owner")
    return ResourceManager(turn.owner, tool.agent.context.id, turn.run_id)


def _browser_tool(tool):
    from plugins._browser.tools.browser import Browser
    cls = type(tool)
    execute = cls.__dict__.get("execute")
    return (cls.__name__ == "Browser" and execute is not None
            and getattr(execute, "__code__", None) == Browser.execute.__code__
            and inspect.getsourcefile(execute) == inspect.getsourcefile(Browser.execute))


def supports(tool, args):
    from helpers.mcp_handler import MCPTool
    return type(tool) is MCPTool or _browser_tool(tool)


def can_resume(tool, args, call):
    """Even a read-only hint is not authorization to replay an interrupted body."""
    return False


async def prepare(tool, args):
    if not supports(tool, args):
        _held("session_adapter_required")
    # Check encryption custody before starting a browser or server operation.
    from helpers.durable.resources import ResourceHeld, cipher
    try:
        cipher()
    except ResourceHeld:
        _held("session_encryption_custody_unavailable")
    manager = _manager(tool)
    tool._durable_session_manager = manager
    if _browser_tool(tool):
        from plugins._browser.helpers.config import RUNTIME_BACKEND_KEY, get_browser_config
        config = get_browser_config(agent=tool.agent)
        if config.get(RUNTIME_BACKEND_KEY, "container") != "container":
            _held("durable_host_browser_adapter_required")
        if config.get("extension_paths"):
            _held("durable_browser_extension_adapter_required")
        tool._durable_browser_runtime = await browser_runtime(tool, args)


def safe_url(value):
    """Only HTTP(S) documents can be reopened; scripts, credentials and POSTs cannot."""
    if value == "about:blank":
        return value
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("Browser recovery URL is not an HTTP(S) document")
    return value


def _browser_custody(manager, config_digest):
    def header():
        owner = manager.owner
        return (owner.sync("get_restore_state")["epoch"],
                owner.sync("document_generation", manager.context_id),
                owner.sync("ownership", manager.run_id).get("fence"))
    before = header()
    manifest = manager.get_manifest("browser_session")
    if before != header():
        _held("browser_session_custody_changed")
    return {"epoch": before[0], "generation": before[1], "fence": before[2],
            "run_id": manager.run_id, "manifest_version": manifest["version"] if manifest else 0,
            "config_digest": config_digest}, manifest


async def _invalidate_browser(runtime, context_id):
    runtime._durable_binding = None
    runtime._durable_initialized = False
    from plugins._browser.helpers.runtime import discard_durable_runtime
    try:
        await discard_durable_runtime(context_id, expected=runtime)
    except Exception:
        pass  # The invalid cache is never eligible even if process cleanup fails.


async def cached_browser_current(runtime):
    """Viewer check only: no restoration, URL navigation or claim acquisition."""
    manager = getattr(runtime, "_durable_manager", None)
    tool = getattr(runtime, "_durable_tool", None)
    if manager is None or tool is None:
        return False
    try:
        from plugins._browser.helpers.config import get_browser_config
        config_digest = _digest(get_browser_config(agent=tool.agent))
        binding, manifest = await asyncio.to_thread(_browser_custody, manager, config_digest)
        return (getattr(runtime, "_durable_binding", None) == binding
                and (manifest is None or manifest["value"].get("config_digest") == config_digest))
    except Exception:
        return False
    except BaseException as exc:
        from helpers.durable.runtime import RecoveryHeld
        if isinstance(exc, RecoveryHeld):
            return False
        raise


class DurableBrowserSession:
    def __init__(self, runtime, manager, tool, config_digest):
        self.runtime, self.manager, self.tool = runtime, manager, tool
        self.config_digest = config_digest

    async def call(self, method, *args, **kwargs):
        try:
            binding, _ = await asyncio.to_thread(_browser_custody, self.manager, self.config_digest)
            if getattr(self.runtime, "_durable_binding", None) != binding:
                _held("browser_session_custody_changed")
            await asyncio.to_thread(self.manager.owner.sync, "assert_owner", self.manager.run_id)
            result = await self.runtime.call(method, *args, **kwargs)
        except BaseException as exc:
            await _invalidate_browser(self.runtime, self.manager.context_id)
            if isinstance(exc, Exception):
                _held("browser_action_outcome_unknown")
            raise
        if method == "content" or method == "list" and kwargs.get("include_content"):
            self.runtime._durable_refs_expired = False
        try:
            snapshot = await self.runtime.call("durable_snapshot")
            data = json.dumps(snapshot, sort_keys=True, allow_nan=False).encode()
            ref = await asyncio.to_thread(self.manager.put_bytes, "browser_session", "state", data, sensitive=True)
            manifest = await asyncio.to_thread(self.manager.publish_manifest, "browser_session",
                                              {"schema": 1, "state": ref, "config_digest": self.config_digest},
                                              binding["manifest_version"])
            current, _ = await asyncio.to_thread(_browser_custody, self.manager, self.config_digest)
            if current != {**binding, "manifest_version": manifest["version"]}:
                _held("browser_session_custody_changed")
            self.runtime._durable_binding = current
            _remember(self.tool, "browser_session", manifest)
        except BaseException as exc:
            await _invalidate_browser(self.runtime, self.manager.context_id)
            if isinstance(exc, Exception):
                _held("browser_session_checkpoint_failed")
            raise
        return result


async def browser_runtime(tool, args):
    manager = tool._durable_session_manager
    from plugins._browser.helpers.config import get_browser_config
    config_digest = _digest(get_browser_config(agent=tool.agent))
    from plugins._browser.helpers.runtime import get_durable_runtime
    context_id = str(tool.agent.context.id)
    binding, manifest = await asyncio.to_thread(_browser_custody, manager, config_digest)
    runtime, fresh = await get_durable_runtime(context_id)
    previous = getattr(runtime, "_durable_binding", None)
    if (previous and previous["config_digest"] != config_digest
            or manifest and (manifest["value"].get("schema") != 1
                             or manifest["value"].get("config_digest") != config_digest)):
        await _invalidate_browser(runtime, context_id)
        _held("browser_session_identity_changed")
    if not fresh:
        health = await runtime.call("durable_health")
        if previous != binding or health["started"] and not health["alive"]:
            await _invalidate_browser(runtime, context_id)
            runtime, fresh = await get_durable_runtime(context_id)
    if fresh:
        if manifest:
            data = await asyncio.to_thread(manager.get_bytes, manifest["value"]["state"])
            snapshot = json.loads(data)
            for tab in snapshot.get("tabs", []):
                safe_url(tab["url"])
            try:
                await runtime.call("durable_restore", snapshot)
            except BaseException:
                await _invalidate_browser(runtime, context_id)
                raise
            # Both tab IDs and DOM refs expire; model must inspect restored tabs.
            runtime._durable_refs_expired = True
        current, _ = await asyncio.to_thread(_browser_custody, manager, config_digest)
        if current != binding:
            await _invalidate_browser(runtime, context_id)
            _held("browser_session_custody_changed")
        runtime._durable_binding = binding
        runtime._durable_initialized = True
    runtime._durable_manager, runtime._durable_tool = manager, tool
    if getattr(runtime, "_durable_refs_expired", False):
        action = str(args.get("action") or tool.method or "state").lower()
        if action not in {"state", "list", "content", "open", "navigate", "close", "close_all"}:
            _held("browser_session_requires_fresh_content")
    return DurableBrowserSession(runtime, manager, tool, config_digest)


async def validate_mcp(tool, server, initialized, tools):
    """Pin the current connection, not a potentially stale list-tools cache."""
    manager = tool._durable_session_manager
    from helpers.mcp_handler import _split_qualified_tool_name
    server_name, name = _split_qualified_tool_name(tool.name)
    if server.disabled or name in server.disabled_tools:
        _held("mcp_server_or_tool_disabled")
    selected = next((item for item in tools if item.get("name") == name), None)
    if selected is None:
        _held("mcp_tool_schema_changed")
    # Never put resolved headers/env/credentials in descriptors. The opaque hash
    # binds locally configured custody without exporting it to another worker.
    descriptor = {"schema": 1, "server": server_name,
                  "config_digest": _digest(server.model_dump(mode="json")),
                  "initialize": initialized, "tool": selected,
                  "tools": sorted(tools, key=lambda item: item["name"]),
                  "reconciler": reconciler_identity(server_name, name)}
    kind = "mcp_" + _digest(tool.name)[:24]
    old = await asyncio.to_thread(manager.get_manifest, kind)
    if old:
        previous = json.loads(await asyncio.to_thread(manager.get_bytes, old["value"]["descriptor"]))
        if descriptor != previous:
            _held("mcp_session_identity_changed")
    else:
        ref = await asyncio.to_thread(manager.put_bytes, "mcp_session", "descriptor",
                                     json.dumps(descriptor, sort_keys=True).encode(), sensitive=True)
        old = await asyncio.to_thread(manager.publish_manifest, kind, {"schema": 1, "descriptor": ref}, 0)
    from helpers.durable.store import OwnershipError
    try:
        await asyncio.to_thread(manager.owner.sync, "assert_owner", manager.run_id)
    except OwnershipError:
        _held("mcp_session_owner_changed")
    _remember(tool, kind, old)


def _remember(tool, kind, manifest):
    turn = _turn(tool)
    with turn.owner.lock:
        state = getattr(tool.agent.context, "_durable_resources", None)
        if state is None:
            state = {"version": 1}
            tool.agent.context._durable_resources = state
        state.setdefault("sessions", {})[kind] = manifest


_reconcilers = {}


def register_reconciler(server, tool, reconcile):
    """Register trusted local query-only code; never infer capability from hints.

    The callable receives (tool, committed_args, call) and returns either None
    (unknown) or an actual completed MCP CallToolResult. It must query a server's
    documented request-status API, never invoke the original operation.
    """
    path = inspect.getsourcefile(reconcile)
    if not path or not inspect.iscoroutinefunction(reconcile) or reconcile.__closure__:
        raise ValueError("MCP reconciler requires inspectable local source")
    identity = {"name": reconcile.__module__ + "." + reconcile.__qualname__,
                "source": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    _reconcilers[(server, tool)] = (identity, reconcile)
    return dict(identity)


def reconciler_identity(server, tool):
    registration = _reconcilers.get((server, tool))
    if registration:
        current = dict(registration[0])
        current["source"] = hashlib.sha256(Path(inspect.getsourcefile(registration[1])).read_bytes()).hexdigest()
        if current != registration[0]:
            _held("mcp_reconciler_identity_changed")
        return current
    return None


async def reconcile(tool, args, call):
    """Return a verified known outcome, or hold. Never rerun the original call."""
    from helpers.mcp_handler import MCPTool, _split_qualified_tool_name
    from mcp.types import CallToolResult
    if type(tool) is not MCPTool:
        return None
    server, name = _split_qualified_tool_name(tool.name)
    registration = _reconcilers.get((server, name))
    if registration is None:
        return None
    manager = getattr(tool, "_durable_session_manager", None) or _manager(tool)
    saved = await asyncio.to_thread(manager.get_manifest, "mcp_" + _digest(tool.name)[:24])
    if not saved:
        return None
    descriptor = json.loads(await asyncio.to_thread(manager.get_bytes, saved["value"]["descriptor"]))
    if descriptor.get("reconciler") != reconciler_identity(server, name):
        _held("mcp_reconciler_identity_changed")
    from helpers.mcp_handler import MCPConfig
    configured = next((item for item in MCPConfig.get_for_agent(tool.agent).servers
                       if item.name == server and not item.disabled and item.has_tool(name)), None)
    if configured is None or _digest(configured.model_dump(mode="json")) != descriptor.get("config_digest"):
        _held("mcp_session_identity_changed")
    tool._durable_session_manager = manager
    await MCPConfig.get_for_agent(tool.agent).validate_durable_session(tool)
    outcome = await registration[1](tool, args, call)
    if outcome is None:
        return None
    if not isinstance(outcome, CallToolResult):
        _held("mcp_reconciliation_result_invalid")
    return outcome


async def reconcile_unknown(tool, args, call):
    outcome = await reconcile(tool, args, call)
    if outcome is None:
        return None
    from helpers.tool import Response
    message, additional = tool._format_tool_result(outcome)
    return Response(message=message, break_loop=False, additional=additional)
