"""Session recovery uses real local MCP transport and isolated browser doubles."""
import asyncio
import copy
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from helpers.durable import sessions
from helpers.durable.resources import ResourceManager
from helpers.durable.runtime import RecoveryHeld
from helpers.mcp_handler import MCPConfig, MCPServerLocal, MCPTool


class MemoryCustody:
    """Encrypted ResourceManager's public storage contract, no user state."""
    def __init__(self):
        self.resources, self.manifests = {}, {}
        self.lock = threading.RLock()
        self.epoch, self.generation, self.fence = "fixture-epoch", 1, 1

    def sync(self, method, *args, **kwargs):
        with self.lock:
            if method == "get_restore_state":
                return {"epoch": self.epoch}
            if method == "document_generation":
                return self.generation
            if method == "ownership":
                return {"fence": self.fence}
            if method == "assert_owner":
                return None
            if method == "put_resource":
                context, ref, body = args
                self.resources[(context, ref["id"])] = {"metadata": ref, "body": body}
                return copy.deepcopy(ref)
            if method == "get_resource":
                return copy.deepcopy(self.resources[args])
            if method == "get_resource_manifest":
                return copy.deepcopy(self.manifests.get(args))
            if method == "publish_resource_manifest":
                context, kind, value, expected, run_id = args
                old = self.manifests.get((context, kind))
                assert (old["version"] if old else 0) == expected
                result = {"version": expected + 1, "value": copy.deepcopy(value)}
                self.manifests[(context, kind)] = result
                return copy.deepcopy(result)
            raise AssertionError(method)


@pytest.fixture
def custody(monkeypatch):
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    return MemoryCustody()


def make_tool(custody, cls=MCPTool, name="fixture.effect"):
    context = SimpleNamespace(id="fixture-chat", log=SimpleNamespace(log=lambda **kw: None))
    agent = SimpleNamespace(context=context, agent_name="fixture")
    context._durable_turn = SimpleNamespace(agent=agent, owner=custody, run_id="fixture-run", active_call_id="tool:0:0")
    return cls(agent=agent, name=name, method=None, args={}, message="", loop_data=None)


@pytest.fixture
def local_mcp(tmp_path, monkeypatch):
    script = tmp_path / "server.py"
    identity, effects = tmp_path / "identity", tmp_path / "effects"
    identity.write_text("fixture-v1")
    script.write_text('''import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP
server = FastMCP(Path(os.environ["FIXTURE_IDENTITY"]).read_text())
@server.tool()
def effect(value: str) -> str:
    with open(os.environ["FIXTURE_EFFECTS"], "a") as out:
        out.write(value + "\\n")
    return value
@server.tool()
def result_for(value: str) -> str:
    path = Path(os.environ["FIXTURE_EFFECTS"])
    return value if path.exists() and value in path.read_text().splitlines() else "unknown"
server.run(transport="stdio")
''')
    def server():
        return MCPServerLocal({"name": "fixture", "command": sys.executable, "args": [str(script)],
                               "env": {"FIXTURE_IDENTITY": str(identity), "FIXTURE_EFFECTS": str(effects)},
                               "init_timeout": 10, "tool_timeout": 10})
    config = MCPConfig(servers_list=[])
    config.servers = [server()]
    monkeypatch.setattr(MCPConfig, "get_for_agent", lambda agent: config)
    return SimpleNamespace(config=config, server=server, identity=identity, effects=effects)


def test_real_mcp_reconnect_pins_actual_server_and_schema_before_effect(custody, local_mcp, monkeypatch):
    tool = make_tool(custody)
    async def scenario():
        await local_mcp.config.servers[0].initialize()
        await sessions.prepare(tool, {"value": "first"})
        first = await local_mcp.config.call_tool(tool.name, {"value": "first"}, durable_tool=tool)
        assert first.content[0].text == "first"
        # Different client and stdio process, same identity/config/schema.
        local_mcp.config.servers = [local_mcp.server()]
        await local_mcp.config.servers[0].initialize()
        second = await local_mcp.config.call_tool(tool.name, {"value": "second"}, durable_tool=tool)
        assert second.content[0].text == "second"
        local_mcp.identity.write_text("different-server")
        with pytest.raises(RecoveryHeld, match="mcp_session_identity_changed"):
            await local_mcp.config.call_tool(tool.name, {"value": "forbidden"}, durable_tool=tool)
        local_mcp.identity.write_text("fixture-v1")
        original_sync = custody.sync
        def moved_owner(method, *args, **kwargs):
            if method == "assert_owner":
                from helpers.durable.store import OwnershipError
                raise OwnershipError("fixture ownership moved during initialization")
            return original_sync(method, *args, **kwargs)
        monkeypatch.setattr(custody, "sync", moved_owner)
        with pytest.raises(RecoveryHeld, match="mcp_session_owner_changed"):
            await local_mcp.config.call_tool(tool.name, {"value": "stale"}, durable_tool=tool)
    asyncio.run(scenario())
    assert local_mcp.effects.read_text().splitlines() == ["first", "second"]
    assert "sessions" in tool.agent.context._durable_resources
    assert all(b"FIXTURE_EFFECTS" not in row["body"] and b"first" not in row["body"]
               for row in custody.resources.values())


async def recorded_completion(tool, args, call):
    # Query-only fixture reconciler retrieves an already recorded server result.
    assert call["call_id"] == "tool:0:0"
    return await MCPConfig.get_for_agent(tool.agent).call_tool("fixture.result_for", {"value": args["value"]})


def test_mcp_unknown_never_replays_and_trusted_reconciler_only_returns_known_result(custody, local_mcp, monkeypatch):
    monkeypatch.setattr(sessions, "_reconcilers", {})
    tool = make_tool(custody)
    call = {"call_id": "tool:0:0", "status": "intent"}
    assert sessions.can_resume(tool, {"value": "effect"}, call) is False
    assert asyncio.run(sessions.reconcile_unknown(tool, {}, call)) is None
    sessions.register_reconciler("fixture", "effect", recorded_completion)
    async def scenario():
        await local_mcp.config.servers[0].initialize()
        await sessions.prepare(tool, {})
        await local_mcp.config.call_tool(tool.name, {"value": "once"}, durable_tool=tool)
        outcome = await sessions.reconcile_unknown(tool, {"value": "once"}, call)
        assert outcome.message == "once"
        local_mcp.identity.write_text("changed-server")
        with pytest.raises(RecoveryHeld, match="mcp_session_identity_changed"):
            await sessions.reconcile_unknown(tool, {"value": "once"}, call)
    asyncio.run(scenario())
    assert local_mcp.effects.read_text().splitlines() == ["once"]


class Page:
    def __init__(self):
        self.url, self.session, self.events = "about:blank", {}, {}
    def on(self, name, callback):
        self.events[name] = callback
    async def goto(self, url, **kwargs):
        self.url = url
    async def evaluate(self, source, **kwargs):
        return self.session
    async def close(self):
        pass


class CDP:
    def __init__(self):
        self.calls = []
    async def send(self, method, params=None):
        self.calls.append((method, params))
        return {"identifier": "fixture-script"}
    async def detach(self):
        pass


class BrowserContext:
    def __init__(self, storage):
        self.storage, self.pages, self.cdp = copy.deepcopy(storage or {"cookies": [], "origins": []}), [], CDP()
    def on(self, *args):
        pass
    def set_default_timeout(self, *args):
        pass
    set_default_navigation_timeout = set_default_timeout
    async def storage_state(self):
        return copy.deepcopy(self.storage)
    async def new_page(self):
        page = Page()
        self.pages.append(page)
        return page
    async def new_cdp_session(self, page):
        return self.cdp
    async def close(self):
        pass


def test_browser_restore_isolated_from_shared_profiles_and_expires_ids(custody, monkeypatch, tmp_path):
    from plugins._browser import hooks
    from plugins._browser.helpers import runtime
    import patchright.async_api
    contexts, launches = [], []
    class Browser:
        async def new_context(self, storage_state=None, **kwargs):
            context = BrowserContext(storage_state)
            contexts.append(context)
            return context
        async def close(self):
            pass
    class Chromium:
        async def launch(self, **kwargs):
            launches.append(kwargs)
            return Browser()
        async def launch_persistent_context(self, **kwargs):
            pytest.fail("Durable browser touched the shared sign-in profile")
    class Playwright:
        chromium = Chromium()
        async def start(self):
            return self
        async def stop(self):
            pass
    monkeypatch.setattr(patchright.async_api, "async_playwright", Playwright)
    monkeypatch.setattr(hooks, "prepare_playwright_cache", lambda: {"binary": "/fixture/chromium"})
    monkeypatch.setattr(runtime, "get_browser_config", lambda *a, **kw: {})
    monkeypatch.setattr(runtime, "_load_browser_tabs", lambda: pytest.fail("Shared tab state read"))
    monkeypatch.setattr(runtime, "_save_browser_tabs", lambda *a: pytest.fail("Shared tab state overwritten"))
    monkeypatch.setattr(runtime.files, "get_abs_path", lambda *parts: str(tmp_path.joinpath(*parts)))
    monkeypatch.setattr(runtime.BrowserInteractiveView, "ensure_display", lambda self: None)
    async def scenario():
        from helpers.durable import runtime as durable_runtime
        monkeypatch.setattr(durable_runtime, "service", lambda: SimpleNamespace(enabled=True))
        monkeypatch.setattr(runtime, "_durable_runtimes", {})
        monkeypatch.setattr(runtime, "_runtimes", {"chat-a": object()})
        assert await runtime.get_runtime("chat-a", create=False) is None
        with pytest.raises(RuntimeError, match="owning tool"):
            await runtime.get_runtime("chat-a", create=True)
        first = runtime._BrowserRuntimeCore("chat-a", durable=True)
        await first.ensure_started()
        first.context.storage["cookies"] = [{"name": "auth", "value": "private-cookie", "domain": "example.test", "path": "/"}]
        page = await first.context.new_page()
        page.url, page.session = "https://example.test/document", {"draft": "private-draft"}
        await first._register_page(page)
        saved = await first.durable_snapshot()
        manager = ResourceManager(custody, "chat-a", "run-a")
        ref = manager.put_bytes("browser_session", "state", json.dumps(saved).encode(), sensitive=True)
        assert b"private-cookie" not in next(iter(custody.resources.values()))["body"]
        other = runtime._BrowserRuntimeCore("chat-b", durable=True)
        await other.ensure_started()
        assert (await other.durable_snapshot())["storage"]["cookies"] == []
        restored = runtime._BrowserRuntimeCore("chat-a", durable=True)
        await restored.durable_restore(json.loads(manager.get_bytes(ref)))
        assert restored.context.storage == saved["storage"]
        assert min(restored.pages) > max(tab["id"] for tab in saved["tabs"])
        assert next(iter(restored.pages.values())).page.url == "https://example.test/document"
        assert [method for method, _ in restored.context.cdp.calls] == ["Page.addScriptToEvaluateOnNewDocument", "Page.removeScriptToEvaluateOnNewDocument"]
        for core in (first, other, restored):
            await core.close()

        from plugins._browser.helpers import config
        from plugins._browser.tools.browser import Browser as BrowserTool
        browser_config = {}
        monkeypatch.setattr(config, "get_browser_config", lambda **kw: browser_config)
        tool = make_tool(custody, BrowserTool, "browser")
        tool.agent.context.id = "chat-a"
        tool._durable_session_manager = manager
        # A small direct-loop facade keeps the real browser core and cache
        # registry behavior without spawning a worker thread for fake Chromium.
        class Handle:
            def __init__(self):
                self.core = runtime._BrowserRuntimeCore("chat-a", durable=True)
                self._runtime = self
            async def call(self, method, *a, **kw):
                if method == "content":
                    return {"refs": ["new-ref"]}
                return await getattr(self.core, method)(*a, **kw)
            async def close(self):
                await self.core.close()
        cache = {}
        async def get_isolated(context_id):
            if context_id not in cache:
                cache[context_id] = Handle()
                runtime._durable_runtimes[context_id] = cache[context_id]
            handle = cache[context_id]
            return handle, not getattr(handle, "_durable_initialized", False)
        async def discard(context_id, *, expected=None):
            if expected is not None and cache.get(context_id) is not expected:
                return
            handle = cache.pop(context_id, None)
            runtime._durable_runtimes.pop(context_id, None)
            if handle:
                await handle.close()
        monkeypatch.setattr(runtime, "get_durable_runtime", get_isolated)
        monkeypatch.setattr(runtime, "discard_durable_runtime", discard)
        descriptor = {"schema": 1, "state": ref, "config_digest": sessions._digest(browser_config)}
        manager.publish_manifest("browser_session", descriptor, 0)
        prepared = await sessions.browser_runtime(tool, {"action": "content"})
        initial = prepared.runtime
        assert initial.core.context.storage["cookies"][0]["value"] == "private-cookie"
        await prepared.call("content")
        assert initial._durable_binding["manifest_version"] == 2
        assert await runtime.get_runtime("chat-a", create=False) is initial

        # Another worker's committed state cannot be overwritten by an old cache.
        changed = copy.deepcopy(saved)
        changed["storage"]["cookies"][0]["value"] = "other-worker-cookie"
        newer_ref = manager.put_bytes("browser_session", "state", json.dumps(changed).encode(), sensitive=True)
        manager.publish_manifest("browser_session", {**descriptor, "state": newer_ref}, 2)
        prepared = await sessions.browser_runtime(tool, {"action": "content"})
        assert prepared.runtime is not initial
        assert prepared.runtime.core.context.storage["cookies"][0]["value"] == "other-worker-cookie"
        latest = prepared.runtime

        # Restore epochs, claim fences and generations invalidate even an
        # unchanged manifest version. Viewer checks never restore/navigate.
        custody.epoch = "restored-epoch"
        assert await runtime.get_runtime("chat-a", create=False) is None
        assert "chat-a" not in cache
        prepared = await sessions.browser_runtime(tool, {"action": "content"})
        assert prepared.runtime is not latest
        latest = prepared.runtime
        custody.fence += 1
        prepared = await sessions.browser_runtime(tool, {"action": "content"})
        assert prepared.runtime is not latest
        custody.generation += 1
        custody.manifests.pop(("chat-a", "browser_session"))
        prepared = await sessions.browser_runtime(tool, {"action": "content"})
        await prepared.call("content")
        assert prepared.runtime.core.context.storage["cookies"] == []

        browser_config["proxy_server"] = "http://different-proxy.test"
        with pytest.raises(RecoveryHeld, match="browser_session_identity_changed"):
            await sessions.browser_runtime(tool, {"action": "content"})
        assert "chat-a" not in cache
        browser_config.clear()
        await discard("chat-a")
    asyncio.run(scenario())
    assert len(contexts) >= 3 and all("user_data_dir" not in item for item in launches)
    assert not (tmp_path / "tmp/browser/sessions").exists()


def test_browser_lost_capture_holds_instead_of_reporting_retryable_failure(custody):
    from helpers.modules import load_classes_from_file
    from helpers.tool import Tool
    path = Path(__file__).resolve().parents[1] / "plugins/_browser/tools/browser.py"
    Browser, = load_classes_from_file(str(path), Tool)
    tool = make_tool(custody, Browser, "browser")
    assert sessions.supports(tool, {})
    class Custom(Browser):
        pass
    assert not sessions.supports(make_tool(custody, Custom, "browser"), {})
    events = []
    class Runtime:
        async def call(self, method, *args, **kwargs):
            events.append(method)
            if method == "durable_snapshot":
                raise RuntimeError("Lost browser after submit")
            return {"ok": True}
    runtime = Runtime()
    manager = ResourceManager(custody, "fixture-chat", "fixture-run")
    runtime._durable_binding, _ = sessions._browser_custody(manager, "config")
    runtime._durable_initialized = True
    wrapped = sessions.DurableBrowserSession(runtime, manager, tool, "config")
    with pytest.raises(RecoveryHeld, match="browser_session_checkpoint_failed"):
        asyncio.run(wrapped.call("click", 1, 7))
    assert events == ["click", "durable_snapshot"]
    assert runtime._durable_binding is None and runtime._durable_initialized is False
    assert sessions.can_resume(tool, {"action": "evaluate", "script": "submit()"}, {}) is False
    for value in ("javascript:submit()", "file:///etc/passwd", "https://user:secret@example.test/"):
        with pytest.raises(ValueError):
            sessions.safe_url(value)
