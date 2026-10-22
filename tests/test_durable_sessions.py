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
        assert [method for method, _ in restored.context.cdp.calls] == ["Page.enable", "Page.addScriptToEvaluateOnNewDocument", "Page.removeScriptToEvaluateOnNewDocument"]
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


def test_real_chromium_profile_restores_database_cache_workers_downloads_and_extensions(custody, monkeypatch, tmp_path):
    """Explicit opt-in uses installed Chromium; never downloads a test dependency."""
    import os
    binary = os.environ.get("A0_TEST_DURABLE_CHROMIUM")
    if not binary:
        pytest.skip("Set A0_TEST_DURABLE_CHROMIUM to an existing disposable-test Chromium")
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from plugins._browser import hooks
    from plugins._browser.helpers import runtime, profile_checkpoint
    extension = tmp_path / "extension"
    extension.mkdir()
    (extension / "manifest.json").write_text(json.dumps({"manifest_version": 3, "name": "Durability fixture", "version": "1.0", "permissions": ["storage"], "background": {"service_worker": "worker.js"}}))
    (extension / "worker.js").write_text("chrome.storage.local.set({fixture:'extension-value'});")
    config = {"extension_paths": [str(extension)]}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path == "/worker.js":
                body = b"self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(clients.claim()));"
                content_type = "application/javascript"
            elif self.path == "/download":
                body, content_type = b"retained-download", "application/octet-stream"
            else:
                body, content_type = b"<html><title>Durable fixture</title><p>Local fixture</p></html>", "text/html"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if self.path == "/download":
                self.send_header("Content-Disposition", 'attachment; filename="fixture.txt"')
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(hooks, "prepare_playwright_cache", lambda: {"binary": binary})
    monkeypatch.setattr(runtime, "get_browser_config", lambda **kw: config)
    monkeypatch.setattr(runtime.BrowserInteractiveView, "ensure_display", lambda self: "")
    monkeypatch.setattr(runtime.files, "get_abs_path", lambda *parts: str(tmp_path.joinpath(*parts)))
    monkeypatch.setattr("plugins._browser.helpers.playwright.get_playwright_binary", lambda: Path(binary))
    async def scenario():
        first = runtime._BrowserRuntimeCore("profile-chat", durable=True, profile=True)
        first._durable_config = config
        second = None
        try:
            opened = await first.open(url)
            page = first.pages[opened["id"]].page
            await page.evaluate('''async () => {
                document.cookie='auth=private-profile-cookie;path=/';
                localStorage.setItem('fixture','local-value');sessionStorage.setItem('fixture','session-value');
                const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('durable',1);r.onupgradeneeded=()=>r.result.createObjectStore('values');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
                await new Promise((resolve,reject)=>{const t=db.transaction('values','readwrite');t.objectStore('values').put('indexed-value','key');t.oncomplete=resolve;t.onerror=reject});db.close();
                const cache=await caches.open('durable');await cache.put('/cached',new Response('cache-value'));
                await navigator.serviceWorker.register('/worker.js');await navigator.serviceWorker.ready;
            }''', isolated_context=False)
            async with page.expect_download() as pending:
                await page.evaluate("() => {const a=document.createElement('a');a.href='/download';a.click()}")
            await pending.value
            if first._durable_downloads:
                await asyncio.gather(*first._durable_downloads)
            workers = first.context.service_workers
            extension_worker = next((worker for worker in workers if worker.url.startswith("chrome-extension:")), None)
            if extension_worker is None:
                extension_worker = await first.context.wait_for_event("serviceworker", predicate=lambda worker: worker.url.startswith("chrome-extension:"), timeout=10000)
            extension_id = extension_worker.url.split("/")[2]
            assert await extension_worker.evaluate("async()=> (await chrome.storage.local.get('fixture')).fixture") == "extension-value"
            closed = await first.durable_profile_checkpoint()
            assert closed["snapshot"]["tabs"][0]["session_storage"] == {"fixture": "session-value"}
            manager = ResourceManager(custody, "profile-chat", "profile-run")
            checkpoint = profile_checkpoint.capture(manager, closed["root"])
            assert all(len(row["body"]) > 0 and b"private-profile-cookie" not in row["body"] for row in custody.resources.values())
            second = runtime._BrowserRuntimeCore("profile-chat", durable=True, profile=True)
            second._durable_config = config
            profile_checkpoint.restore(manager, checkpoint, second.durable_root)
            await second.durable_restore(closed["snapshot"])
            restored = next(iter(second.pages.values())).page
            result = await restored.evaluate('''async () => {
                const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('durable',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
                const value=await new Promise((resolve,reject)=>{const r=db.transaction('values').objectStore('values').get('key');r.onsuccess=()=>resolve(r.result);r.onerror=reject});db.close();
                const cached=await (await caches.open('durable')).match('/cached');
                return {cookie:document.cookie,local:localStorage.getItem('fixture'),session:sessionStorage.getItem('fixture'),indexed:value,cache:cached&&await cached.text(),worker:Boolean(await navigator.serviceWorker.getRegistration())};
            }''', isolated_context=False)
            assert result == {"cookie": "auth=private-profile-cookie", "local": "local-value", "session": "session-value", "indexed": "indexed-value", "cache": "cache-value", "worker": True}
            assert (second.downloads_dir / "fixture.txt").read_bytes() == b"retained-download"
            import sqlite3
            with sqlite3.connect(second.profile_dir / "Default" / "History") as history:
                recorded_paths = history.execute("SELECT target_path FROM downloads").fetchall()
            assert recorded_paths and all(Path(row[0]).is_file() and str(second.downloads_dir) in row[0] for row in recorded_paths)
            worker = next((item for item in second.context.service_workers if item.url.startswith("chrome-extension:")), None)
            if worker is None:
                worker = await second.context.wait_for_event("serviceworker", predicate=lambda item: item.url.startswith("chrome-extension:"), timeout=10000)
            assert worker.url.split("/")[2] == extension_id
            assert await worker.evaluate("async()=> (await chrome.storage.local.get('fixture')).fixture") == "extension-value"
            original = profile_checkpoint.identity(config)
            (extension / "worker.js").write_text("chrome.storage.local.set({fixture:'changed'});")
            assert profile_checkpoint.identity(config) != original
        finally:
            for core in (first, second):
                if core:
                    await core.close()
                    if core._durable_root:
                        import shutil
                        shutil.rmtree(core._durable_root)
    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_real_browser_actor_survives_requester_death_without_repeating_post(monkeypatch, tmp_path):
    import os
    import signal
    import subprocess
    import time
    import uuid
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    dsn = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")
    binary = os.environ.get("A0_TEST_DURABLE_CHROMIUM")
    if not dsn or not binary:
        pytest.skip("Requires explicit disposable PostgreSQL and installed test Chromium")
    from helpers.durable.postgres import PostgresStore
    from psycopg import connect, sql
    namespace = "browser_actor_" + uuid.uuid4().hex
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", key)
    context_id = "browser-actor-chat"
    store = PostgresStore(dsn, namespace=namespace)
    run = store.admit(context_id, "fixture-input", {"message": "fixture"}, {"paused": False})
    received, release = threading.Event(), threading.Event()
    posts = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            body = b"<html><title>Actor fixture</title></html>"
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            posts.append(self.path)
            received.set()
            release.wait(15)
            body = b"one-actual-effect"
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    driver = tmp_path / "requester.py"
    driver.write_text('''import asyncio,json,os,sys,threading
from pathlib import Path
from types import SimpleNamespace
from helpers.durable.postgres import PostgresStore
from helpers.durable.resources import ResourceManager
from plugins._browser.helpers import profile_checkpoint,session_broker
from plugins._browser.tools.browser import Browser
import helpers.secrets
helpers.secrets.get_secrets_manager=lambda ctx:SimpleNamespace(mask_values=lambda value:value)
store=PostgresStore(os.environ['A0_DURABILITY_POSTGRES_DSN'],namespace=os.environ['FIXTURE_NAMESPACE'])
class Owner:
 distributed=True
 lock=threading.RLock()
 def __init__(self):self.store=store
 def sync(self,name,*args,**kwargs):return getattr(store,name)(*args,**kwargs)
owner=Owner();run_id=os.environ['FIXTURE_RUN'];store.claim(run_id)
ctx=SimpleNamespace(id='browser-actor-chat');agent=SimpleNamespace(context=ctx)
turn=SimpleNamespace(agent=agent,owner=owner,run_id=run_id,active_call_id='tool:0:0');ctx._durable_turn=turn
manager=ResourceManager(owner,ctx.id,run_id)
config={'extension_paths':[]};identity=profile_checkpoint.identity(config)
tool=Browser(agent=agent,name='browser',method=None,args={},message='',loop_data=None)
async def main():
 if sys.argv[1]=='start':
  browser=session_broker.BrokerRuntime(tool,manager,config,identity)
  opened=await browser.call('open',os.environ['FIXTURE_URL'])
  Path(os.environ['FIXTURE_TAB']).write_text(str(opened['id']))
  stale=await browser.call('click',opened['id'],'expired-ref')
  assert stale['refs_expired'] and 'fresh content' in stale['error']
  fresh=await browser.call('content',opened['id'])
  assert not fresh['refs_expired']
 turn.active_call_id='tool:0:1'
 browser=session_broker.BrokerRuntime(tool,manager,config,identity)
 result=await browser.call('evaluate',int(Path(os.environ['FIXTURE_TAB']).read_text()),"async () => await (await fetch('/effect',{method:'POST',body:'fixture'})).text()")
 Path(os.environ['FIXTURE_RESULT']).write_text(json.dumps(result))
asyncio.run(main());store.close()
''')
    environment = dict(os.environ, A0_DURABILITY_POSTGRES_DSN=dsn, A0_DURABILITY_RESOURCE_KEY=key,
                       A0_BROWSER_PLAYWRIGHT_CACHE_DIR=str(Path(binary).parents[2]),
                       FIXTURE_NAMESPACE=namespace, FIXTURE_RUN=run["run_id"], FIXTURE_URL=url,
                       FIXTURE_TAB=str(tmp_path / "tab"), FIXTURE_RESULT=str(tmp_path / "result"),
                       PYTHONPATH=str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    requester = successor = None
    broker_pid = None
    try:
        requester = subprocess.Popen([sys.executable, str(driver), "start"], env=environment,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 30
        while not received.wait(.1) and requester.poll() is None and time.monotonic() < deadline:
            pass
        assert received.is_set(), requester.stderr.read().decode() if requester.poll() is not None else "Actor never dispatched its original request"
        requester.kill(); requester.wait(timeout=5)
        release.set()
        from plugins._browser.helpers.session_broker import _key
        job_id = _key(context_id, run["run_id"], "tool:0:1", 0)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            job = store.get_resource_job(job_id)
            if job and job["status"] == "completed":
                break
            time.sleep(.05)
        manager = ResourceManager(SimpleNamespace(sync=lambda name,*a,**kw:getattr(store,name)(*a,**kw)), context_id)
        assert job["status"] == "completed" and job["result"]["status"] == "completed", manager.get_bytes(job["result"]["diagnostic"]).decode() if job.get("result", {}).get("diagnostic") else job
        manager = ResourceManager(SimpleNamespace(sync=lambda name,*a,**kw:getattr(store,name)(*a,**kw)), context_id)
        recorded = json.loads(manager.get_bytes(job["result"]["output"]))
        broker_pid = recorded["broker"]["pid"]
        successor = subprocess.Popen([sys.executable, str(driver), "recover"], env=environment,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert successor.wait(timeout=30) == 0, successor.stderr.read().decode()
        assert "one-actual-effect" in (tmp_path / "result").read_text()
        assert posts == ["/effect"]
    finally:
        release.set()
        for process in (requester, successor):
            if process and process.poll() is None:
                process.kill(); process.wait(timeout=5)
        if broker_pid is None:
            row = store._connection.execute("SELECT worker_id FROM coordinator_roles WHERE name=?", ("browser-" + __import__("hashlib").sha256(context_id.encode()).hexdigest(),)).fetchone()
            if row and row["worker_id"].startswith("browser-"):
                broker_pid = int(row["worker_id"].split("-", 1)[1])
        if broker_pid:
            try:
                os.kill(broker_pid, signal.SIGTERM)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    try: os.kill(broker_pid, 0)
                    except ProcessLookupError: break
                    time.sleep(.05)
            except ProcessLookupError:
                pass
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        store.close()
        with connect(dsn, autocommit=True) as cleanup:
            cleanup.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))


def test_real_mcp_actor_survives_requester_death_and_keeps_credentials_local(monkeypatch, tmp_path):
    import os
    import subprocess
    import time
    import uuid
    from helpers.durable.postgres import PostgresStore
    from psycopg import connect, sql
    dsn = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Requires explicit disposable PostgreSQL")
    namespace = "mcp_actor_" + uuid.uuid4().hex
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", key)
    server = tmp_path / "mcp_server.py"
    server.write_text('''import os,time
from pathlib import Path
from mcp.server.fastmcp import FastMCP
server=FastMCP('durable-fixture')
@server.tool()
def effect(value:str)->str:
 assert not any(k.startswith('A0_DURABILITY_') for k in os.environ)
 assert os.environ['FIXTURE_CREDENTIAL']=='private-fixture-token'
 root=Path(os.environ['FIXTURE_ROOT'])
 with (root/'effects').open('a') as out:out.write(value+'\\n')
 (root/'received').touch()
 deadline=time.monotonic()+20
 while not (root/'release').exists() and time.monotonic()<deadline:time.sleep(.02)
 return 'completed:'+value
server.run(transport='stdio')
''')
    driver = tmp_path / "requester.py"
    driver.write_text('''import asyncio,json,os,sys,threading
from pathlib import Path
from types import SimpleNamespace
from helpers.durable.postgres import PostgresStore
from helpers.durable.resources import ResourceManager
from helpers.durable.mcp_broker import invoke
from helpers.mcp_handler import MCPServerLocal,MCPTool
import helpers.secrets
helpers.secrets.get_secrets_manager=lambda ctx:SimpleNamespace(mask_values=lambda value:value)
store=PostgresStore(os.environ['A0_DURABILITY_POSTGRES_DSN'],namespace=os.environ['FIXTURE_NAMESPACE'])
class Owner:
 distributed=True
 lock=threading.RLock()
 def __init__(self):self.store=store
 def sync(self,name,*args,**kwargs):return getattr(store,name)(*args,**kwargs)
owner=Owner();run_id=os.environ['FIXTURE_RUN'];store.claim(run_id)
ctx=SimpleNamespace(id='mcp-actor-chat');agent=SimpleNamespace(context=ctx)
ctx._durable_turn=SimpleNamespace(agent=agent,owner=owner,run_id=run_id,active_call_id='tool:0:0')
tool=MCPTool(agent=agent,name='fixture.effect',method=None,args={},message='',loop_data=None)
tool._durable_session_manager=ResourceManager(owner,ctx.id,run_id)
server=MCPServerLocal({'name':'fixture','command':sys.executable,'args':[os.environ['FIXTURE_SERVER']],
 'env':{'FIXTURE_ROOT':os.environ['FIXTURE_ROOT'],'FIXTURE_CREDENTIAL':'private-fixture-token','A0_DURABILITY_RESOURCE_KEY':'must-not-forward'},'tool_timeout':30})
async def validate(tool):await server.validate_durable_session('effect',tool)
config=SimpleNamespace(servers=[server],validate_durable_session=validate)
if len(sys.argv)>1 and sys.argv[1]=='preflight':
 import helpers.durable.mcp_broker as broker
 def lose_host(job_id,namespace):
  broker.spool(job_id).unlink()
  raise RuntimeError('Simulated original configuration host loss before send')
 broker.spawn=lose_host
async def main():
 result=await invoke(tool,config,{'value':'one-effect'})
 Path(os.environ['FIXTURE_ROOT'],'result').write_text(result.model_dump_json())
asyncio.run(main());store.close()
''')
    store = PostgresStore(dsn, namespace=namespace)
    run = store.admit("mcp-actor-chat", "fixture-input", {"message": "fixture"}, {"paused": False})
    env = dict(os.environ, A0_DURABILITY_POSTGRES_DSN=dsn, A0_DURABILITY_RESOURCE_KEY=key,
               FIXTURE_NAMESPACE=namespace, FIXTURE_RUN=run["run_id"], FIXTURE_SERVER=str(server),
               FIXTURE_ROOT=str(tmp_path), PYTHONPATH=str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    requester = successor = None
    try:
        preflight = subprocess.run([sys.executable, str(driver), "preflight"], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
        assert preflight.returncode != 0 and b"configuration host loss" in preflight.stderr
        assert not (tmp_path / "effects").exists()
        # A new worker reconstructs only the unsent operation using its matching
        # local server configuration; no headers/env were placed in the ledger.
        requester = subprocess.Popen([sys.executable, str(driver)], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 30
        while not (tmp_path / "received").exists() and requester.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        assert (tmp_path / "received").exists(), requester.stderr.read().decode() if requester.poll() is not None else "Actor did not deliver MCP call"
        requester.kill(); requester.wait(timeout=5)
        (tmp_path / "release").touch()
        from helpers.durable.mcp_broker import key as operation_key
        job_id = operation_key("mcp-actor-chat", run["run_id"], "tool:0:0")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            job = store.get_resource_job(job_id)
            if job and job["status"] == "completed":
                break
            time.sleep(.05)
        manager = ResourceManager(SimpleNamespace(sync=lambda name,*a,**kw:getattr(store,name)(*a,**kw)), "mcp-actor-chat")
        assert job["status"] == "completed" and job["result"]["status"] == "completed", manager.get_bytes(job["result"]["diagnostic"]).decode() if job.get("result", {}).get("diagnostic") else job
        successor = subprocess.Popen([sys.executable, str(driver)], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert successor.wait(timeout=30) == 0, successor.stderr.read().decode()
        assert "completed:one-effect" in (tmp_path / "result").read_text()
        assert (tmp_path / "effects").read_text().splitlines() == ["one-effect"]
        receipt = manager.get_manifest("mcp-op-" + job_id)
        assert "private-fixture-token" not in json.dumps(receipt)
        from helpers.durable.mcp_broker import spool
        assert not spool(job_id).exists()
    finally:
        (tmp_path / "release").touch()
        for process in (requester, successor):
            if process and process.poll() is None:
                process.kill(); process.wait(timeout=5)
        store.close()
        with connect(dsn, autocommit=True) as cleanup:
            cleanup.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))


def test_host_durable_receipts_recover_lost_ack_and_hold_unknown_intents(custody, monkeypatch, tmp_path):
    """Real companion manager/journal across the kernel transport seam."""
    import os
    source = os.environ.get("A0_TEST_CONNECTOR_SOURCE")
    if not source:
        pytest.skip("Requires explicit isolated companion source")
    monkeypatch.syspath_prepend(str(Path(source) / "src"))
    from agent_zero_cli.config import CLIConfig
    from agent_zero_cli.host_browser_common import BrowserProfile
    from agent_zero_cli.host_browser_manager import HostBrowserManager
    from agent_zero_cli.host_browser_durable import BrowserJournal, fingerprint, profile_identity
    from plugins._browser.helpers import durable_connector, connector_runtime
    from plugins._browser.tools.browser import Browser
    import helpers.secrets
    monkeypatch.setattr(helpers.secrets, "get_secrets_manager", lambda ctx: SimpleNamespace(mask_values=lambda value: value))
    journal = BrowserJournal(tmp_path / "journal", key=Fernet.generate_key().decode())
    host = HostBrowserManager(CLIConfig(host_browser_enabled=True), persist_enabled=False, durable_journal=journal)
    profile = BrowserProfile("chrome-a0", "Synthetic Agent", sys.executable, tmp_path / "source", "Default", "Agent")
    monkeypatch.setattr(host, "selected_profile", lambda **kwargs: profile)
    config = {"host_browser_profile_mode": "existing", "host_browser_selection": "fixture-id"}
    metadata = {"features": ["durable_session_v1"], "durable_instance_id": journal.instance_id}
    monkeypatch.setattr(connector_runtime, "get_browser_config", lambda *a, **kw: config)
    monkeypatch.setattr(connector_runtime, "host_browser_metadata_for_sid", lambda sid: metadata)
    monkeypatch.setattr(connector_runtime, "host_browser_metadata_for_context", lambda ctx: [metadata])
    tool = make_tool(custody, Browser, "browser")
    manager = ResourceManager(custody, "fixture-chat", "fixture-run")
    tool._durable_session_manager = manager
    deliveries, lose_ack = [], [True]
    async def effect(payload):
        deliveries.append(payload['text'])
        folder=journal.root/'profiles'/payload['durable']['session_id']
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'state').write_text(payload['text'])
        return {'text': payload['text']}
    async def listing():return {'browsers': []}
    async def nothing(*args):pass
    async def session(*args):return SimpleNamespace(dispatch=effect,list=listing,close=nothing,browser=SimpleNamespace(command=nothing))
    monkeypatch.setattr(host._durable_controller(), '_session', session)
    class Transport(durable_connector.DurableConnectorRuntime):
        def _select_sid(self):return "fixture-sid"
        def _with_browser_helpers(self, sid, payload):return payload
        async def _send_browser_op(self, sid, payload):
            assert payload['durable']['fingerprint'] == fingerprint(payload)
            value = await host.handle_op(payload)
            assert value.get('ok'), value
            if payload['action'] == 'keyboard' and lose_ack[0]:
                lose_ack[0] = False
                raise ConnectionError('Request completed but acknowledgment was lost')
            return value['data']
    async def scenario():
        with pytest.raises(ConnectionError):await Transport(tool,manager).call('keyboard',1,text='café')
        assert (await Transport(tool,manager).call('keyboard',1,text='café'))['text'] == 'café'
        assert deliveries == ['café']
        known=Transport(tool,manager);known._select_sid=lambda:None
        assert (await known.call('keyboard',1,text='café'))['text'] == 'café'
        tool.agent.context._durable_turn.active_call_id='tool:0:1'
        unknown=Transport(tool,manager);original=unknown._send_browser_op
        async def lost(sid,payload):
            if payload['action']=='keyboard':
                durable=journal.validate(payload,profile_identity(profile,'existing'))
                with journal.transaction():
                    journal.db.execute("INSERT INTO operations VALUES(?,?,?,'intent',NULL)",(durable['session_id'],durable['operation_id'],durable['fingerprint']))
                raise ConnectionError('Companion died after send intent')
            return await original(sid,payload)
        unknown._send_browser_op=lost
        with pytest.raises(ConnectionError):await unknown.call('keyboard',1,text='uncertain')
        with pytest.raises(RecoveryHeld,match='host_browser_action_outcome_unknown'):
            await Transport(tool,manager).call('keyboard',1,text='uncertain')
        assert deliveries == ['café']
        # Actual companion exports must advance after each new operation, rather
        # than replay the first export's receipt for this entire browser session.
        config['host_browser_profile_mode']='agent'
        profile_tool=make_tool(custody,Browser,'browser')
        profile_tool.agent.context.id='profile-chat'
        profile_manager=ResourceManager(custody,'profile-chat','fixture-run')
        profile_tool._durable_session_manager=profile_manager
        def saved_profile():
            import base64,io,zipfile
            manifest=profile_manager.get_manifest('host_browser_session')
            snapshot=sessions.get_json(profile_manager,manifest['value']['snapshot'])
            return zipfile.ZipFile(io.BytesIO(base64.b64decode(snapshot['archive']))).read('state')
        assert (await Transport(profile_tool,profile_manager).call('keyboard',1,text='first-profile'))['text']=='first-profile'
        assert saved_profile()==b'first-profile'
        profile_tool.agent.context._durable_turn.active_call_id='tool:0:2'
        assert (await Transport(profile_tool,profile_manager).call('keyboard',1,text='second-profile'))['text']=='second-profile'
        assert saved_profile()==b'second-profile'
        # A known external response survives failed export, but the older profile
        # cannot silently replace its later uncheckpointed state on another host.
        profile_tool.agent.context._durable_turn.active_call_id='tool:0:3'
        broken=Transport(profile_tool,profile_manager);send=broken._send_browser_op
        async def fail_export(sid,payload):
            if payload['action']=='durable_export':raise ConnectionError('Profile export unavailable')
            return await send(sid,payload)
        broken._send_browser_op=fail_export
        with pytest.raises(ConnectionError):await broken.call('keyboard',1,text='known-unexported')
        assert (await Transport(profile_tool,profile_manager).call('keyboard',1,text='known-unexported'))['text']=='known-unexported'
        metadata['durable_instance_id']='f'*64
        profile_tool.agent.context._durable_turn.active_call_id='tool:0:4'
        with pytest.raises(RecoveryHeld,match='host_browser_original_instance_required'):
            await Transport(profile_tool,profile_manager).call('keyboard',1,text='must-not-run')
        assert deliveries==['café','first-profile','second-profile','known-unexported']
        await host.close()
    try:asyncio.run(scenario())
    finally:journal.close()


def test_computer_receipts_recover_exact_action_and_capture_after_lost_ack(custody, monkeypatch, tmp_path):
    import os
    import base64
    source = os.environ.get("A0_TEST_CONNECTOR_SOURCE")
    if not source:
        pytest.skip("Requires explicit isolated companion source")
    monkeypatch.syspath_prepend(str(Path(source) / "src"))
    from agent_zero_cli.host_browser_durable import BrowserJournal
    from agent_zero_cli.computer_use_durable import DurableComputerUse
    from plugins._a0_connector.tools import computer_use_remote as plugin
    from plugins._a0_connector.helpers import ws_runtime
    import helpers.secrets
    monkeypatch.setattr(helpers.secrets, "get_secrets_manager", lambda ctx: SimpleNamespace(mask_values=lambda value: value))
    journal = BrowserJournal(tmp_path / "computer-journal", key=Fernet.generate_key().decode())
    controller = DurableComputerUse(journal)
    helper = tmp_path / "desktop-helper.py"
    helper.write_text("# Synthetic approved desktop boundary; never dispatches OS input.\n")
    manager = SimpleNamespace(enabled=True, supported=True, trust_mode="trusted",
        _backend_spec=SimpleNamespace(helper_target=str(helper)), _backend_metadata={"backend_id":"fixture"})
    effects = []
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
    async def perform(payload):
        action = payload['action']
        if action == 'start_session':return {'op_id':payload['op_id'],'ok':True,'result':{'session_id':'approved-session','width':1,'height':1}}
        if not payload.get('session_id'):return {'op_id':payload['op_id'],'ok':False,'code':'COMPUTER_USE_SESSION_REQUIRED','error':'Session required before dispatch'}
        if action == 'type':
            effects.append(payload['text'])
            return {'op_id':payload['op_id'],'ok':True,'result':{'session_id':'approved-session','text':payload['text']}}
        if action == 'capture':return {'op_id':payload['op_id'],'ok':True,'result':{'session_id':'approved-session','width':1,'height':1,'host_path':'/private/host/capture.png','artifact':{'encoding':'base64','filename':'capture.png','mime':'image/png','data':base64.b64encode(png).decode()}}}
        raise AssertionError(action)
    manager._handle_legacy_op = perform
    metadata={'supported':True,'enabled':True,'features':['computer_use_durable_v1'],'durable_instance_id':journal.instance_id}
    monkeypatch.setattr(plugin,'select_computer_use_target_sid',lambda ctx:'fixture-sid')
    monkeypatch.setattr(plugin,'computer_use_metadata_for_sid',lambda sid:metadata)
    monkeypatch.setattr(ws_runtime,'computer_use_metadata_for_sid',lambda sid:metadata)
    lose_ack=[True]
    async def exchange(*,sid,payload):
        response=await controller.handle(manager,payload)
        if payload['action']=='type' and payload.get('session_id') and lose_ack[0]:
            lose_ack[0]=False
            raise ConnectionError('Delivered action, lost acknowledgement')
        return response
    def tool():
        current=make_tool(custody,plugin.ComputerUseRemote,'computer_use_remote')
        current.args={'action':'type','text':'one actual input'}
        current._dispatch_payload_once=exchange
        return current
    async def scenario():
        with pytest.raises(RecoveryHeld,match='computer_action_outcome_unknown'):
            await tool().execute()
        recovered=tool()
        result=await recovered.execute()
        assert effects == ['one actual input']
        assert 'Latest screen attached' in result.message
        content=result.additional['raw_content']
        image=Path(next(item['image_url']['url'] for item in content if item.get('type')=='image_url'))
        assert image.read_bytes() == png
        assert recovered.agent.context._durable_resources['attachments']
        assert image.as_posix() in recovered.agent.context._durable_resource_paths
        # A completed receipt remains readable with host input disabled.
        metadata['enabled']=False
        assert 'Latest screen attached' in (await tool().execute()).message
        assert effects == ['one actual input']
        fresh=tool();fresh.agent.context._durable_turn.active_call_id='tool:0:1'
        with pytest.raises(RecoveryHeld,match='computer_durable_approved_host_required'):
            await fresh.execute()
        assert effects == ['one actual input']
    try:asyncio.run(scenario())
    finally:journal.close()
