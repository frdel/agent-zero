import asyncio
import concurrent.futures
import json
import re
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import real modules first so setdefault stubs below never shadow them for later collectors.
import agent
import helpers.tool
import helpers.ws
import helpers.ws_manager
import plugins._model_config.helpers.model_config


class _TestAgentContext:
    @staticmethod
    def get(context_id):
        return None


class _TestAgent:
    pass


class _TestAgentConfig:
    pass


class _TestAgentContextType:
    BACKGROUND = "background"
    USER = SimpleNamespace(value="user")


class _TestResponse(SimpleNamespace):
    def __init__(self, message="", break_loop=False, additional=None, **kwargs):
        super().__init__(
            message=message,
            break_loop=break_loop,
            additional=additional,
            **kwargs,
        )


class _TestTool:
    def __init__(
        self,
        agent=None,
        name="",
        method=None,
        args=None,
        message="",
        loop_data=None,
        **kwargs,
    ):
        self.agent = agent
        self.name = name
        self.method = method
        self.args = args or {}
        self.message = message
        self.loop_data = loop_data

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(
            self.name,
            response.message.strip(),
            id=self.log.id,
            **(response.additional or {}),
        )
        self.log.update(content=response.message.strip())


class _TestWsHandler:
    def __init__(self, *args, **kwargs):
        self.emitted = []

    async def emit_to(self, sid, event, data, correlation_id=None):
        self.emitted.append((sid, event, data, correlation_id))


class _TestWsManager:
    async def emit_to(self, *args, **kwargs):
        pass


class _TestWsResult(dict):
    @staticmethod
    def error(code="", message="", correlation_id=None):
        return _TestWsResult(
            {
                "ok": False,
                "code": code,
                "error": message,
                "correlation_id": correlation_id,
            }
        )


sys.modules.setdefault(
    "agent",
    SimpleNamespace(
        Agent=_TestAgent,
        AgentConfig=_TestAgentConfig,
        AgentContext=_TestAgentContext,
        AgentContextType=_TestAgentContextType,
    ),
)
sys.modules.setdefault("helpers.tool", SimpleNamespace(Response=_TestResponse, Tool=_TestTool))
sys.modules.setdefault("helpers.ws", SimpleNamespace(WsHandler=_TestWsHandler))
sys.modules.setdefault("helpers.ws_manager", SimpleNamespace(
    WsResult=_TestWsResult,
    WsPayloadTooLargeError=ValueError,
    get_shared_ws_manager=lambda: _TestWsManager(),
))
_model_config_stub = ModuleType("plugins._model_config.helpers.model_config")
_model_config_stub.get_presets = lambda: []
_model_config_stub.get_preset_by_name = lambda name: None
_model_config_stub.get_chat_model_config = lambda agent=None: {}
_model_config_stub.get_vision_model_config = lambda agent=None: {}
_model_config_stub.build_vision_model = lambda agent=None: None
sys.modules.setdefault("plugins._model_config.helpers.model_config", _model_config_stub)


@pytest.fixture
def anyio_backend():
    return "asyncio"

from helpers import ephemeral_images, virtual_desktop
from helpers.errors import RepairableException
from plugins._browser.helpers.config import (
    build_browser_launch_config,
    get_browser_main_model_summary,
    get_browser_model_preset_options,
    normalize_browser_config,
    resolve_browser_model_selection,
)
from plugins._browser.helpers.extension_manager import (
    _build_web_store_download_url,
    _crx_zip_payload,
    _detect_chrome_prodversion,
    _normalize_chrome_prodversion,
    get_extensions_root,
    parse_chrome_web_store_extension_id,
    uninstall_browser_extension,
)
import plugins._browser.helpers.extension_manager as browser_extension_manager_module
from plugins._browser.helpers.runtime import (
    BrowserPage,
    _BrowserRuntimeCore,
    _BrowserScreencast,
    list_runtime_sessions,
    normalize_url,
)
import plugins._browser.helpers.runtime as browser_runtime_module
from plugins._browser.helpers.interactive_view import BrowserInteractiveView
import plugins._browser.helpers.interactive_view as browser_interactive_view_module
from plugins._browser.helpers.playwright import (
    ensure_playwright_binary,
    get_playwright_binary,
    get_playwright_cache_dir,
)
import plugins._browser.helpers.playwright as browser_playwright_module
import plugins._browser.hooks as browser_hooks_module
import plugins._browser.tools.browser as browser_tool_module
import plugins._browser.api.ws_browser as ws_browser_module


SMALL_JPEG_10X10 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL"
    "DBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/"
    "2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAKAAoDASIAAhEBAxEB/8QAFQAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhADE"
    "AAAAKf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAA"
    "AAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECA"
    "QE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAA"
    "AAAAAAAAAAAAAA/9oACAEBAAE/ISf/2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAA"
    "AAAAAAAAAAP/aAAgBAwEBPxAk/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEB"
    "PxAk/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxAn/9k="
)


def test_browser_url_normalization_matches_address_bar_hosts():
    assert normalize_url("localhost:3000") == "http://localhost:3000/"
    assert normalize_url("127.0.0.1:8000/path") == "http://127.0.0.1:8000/path"
    assert normalize_url("novinky.cz") == "https://novinky.cz/"
    assert normalize_url("https://example.com") == "https://example.com/"
    assert normalize_url("about:blank") == "about:blank"
    with pytest.raises(RepairableException, match="relative"):
        normalize_url("/docs")


def test_browser_config_normalizes_extension_paths(tmp_path):
    extension_dir = tmp_path / "extension"
    extension_dir.mkdir()

    config = normalize_browser_config(
        {
            "extension_paths": [str(extension_dir), "", "  ", str(extension_dir)],
        }
    )

    assert config == {
        "extension_paths": [str(extension_dir)],
        "default_homepage": "about:blank",
        "autofocus_active_page": True,
        "annotation_screenshots": False,
        "browser_tab_scope": "per_context",
        "max_open_tabs": 32,
        "evaluate_timeout_seconds": 30.0,
        "runtime_backend": "container",
        "host_browser_privacy_policy": "allow",
        "host_browser_profile_mode": "existing",
        "host_browser_selection": "",
        "proxy_server": "",
        "proxy_bypass": "",
        "proxy_username": "",
        "proxy_password": "",
        "keyboard_layout": "",
        "keyboard_variant": "",
        "model_preset": "",
    }


def test_browser_config_normalizes_keyboard_layout():
    config = normalize_browser_config(
        {
            "keyboard_layout": "  DE  ",
            "keyboard_variant": "  Mac  ",
        }
    )

    assert config["keyboard_layout"] == "de"
    assert config["keyboard_variant"] == "mac"

    cleared = normalize_browser_config(
        {
            "keyboard_layout": "",
            "keyboard_variant": "mac",
        }
    )

    assert cleared["keyboard_layout"] == ""
    assert cleared["keyboard_variant"] == ""

    unsafe = normalize_browser_config(
        {
            "keyboard_layout": "de; rm -rf /",
            "keyboard_variant": "mac & echo pwned",
        }
    )

    for token in (unsafe["keyboard_layout"], unsafe["keyboard_variant"]):
        assert token == token.lower()
        for forbidden in (" ", ";", "&", "|", "$", "`", "'", '"'):
            assert forbidden not in token


def test_browser_keyboard_layout_restarts_runtime():
    from plugins._browser.helpers.config import browser_runtime_config

    base = browser_runtime_config({"keyboard_layout": "de", "keyboard_variant": "mac"})

    assert base["keyboard_layout"] == "de"
    assert base["keyboard_variant"] == "mac"

    changed = browser_runtime_config({"keyboard_layout": "us", "keyboard_variant": "mac"})
    assert changed != base


def test_browser_config_normalizes_model_preset():
    assert normalize_browser_config({"model_preset": "  Research  "})["model_preset"] == "Research"
    assert "model" not in normalize_browser_config({"model": "main"})


def test_browser_config_normalizes_host_backend_and_privacy_policy():
    config = normalize_browser_config(
        {
            "runtime_backend": "host-required",
            "host_browser_privacy_policy": "warn",
            "host_browser_profile_mode": "agent",
        }
    )

    assert config["runtime_backend"] == "host_required"
    assert config["host_browser_privacy_policy"] == "warn"
    assert config["host_browser_profile_mode"] == "agent"


def test_browser_config_builds_authenticated_internal_proxy():
    config = normalize_browser_config(
        {
            "proxy_server": "  socks5://proxy.example:1080  ",
            "proxy_bypass": "  localhost, .example.com  ",
            "proxy_username": "researcher",
            "proxy_password": "secret",
        }
    )

    assert build_browser_launch_config(config)["proxy"] == {
        "server": "socks5://proxy.example:1080",
        "bypass": "localhost, .example.com",
        "username": "researcher",
        "password": "secret",
    }


def test_browser_config_normalizes_host_browser_selection():
    assert normalize_browser_config({})["host_browser_selection"] == ""
    assert (
        normalize_browser_config({"host_browser_selection": "  Edge Dev  "})["host_browser_selection"]
        == "edge_dev"
    )
    assert (
        normalize_browser_config({"host_browser_choice": "chrome"})["host_browser_selection"]
        == "chrome"
    )
    assert normalize_browser_config({"host_browser_selection": " Safari:Default "})[
        "host_browser_selection"
    ] == "safari:default"
    assert (
        normalize_browser_config({"host_browser_selection": "ws://127.0.0.1:9222/devtools/Browser/AbC?token=XyZ"})[
            "host_browser_selection"
        ]
        == "ws://127.0.0.1:9222/devtools/Browser/AbC?token=XyZ"
    )
    assert normalize_browser_config({"host_browser_selection": "localhost:9222"})[
        "host_browser_selection"
    ] == "localhost:9222"
    assert normalize_browser_config({"host_browser_selection": "bad\x00value"})[
        "host_browser_selection"
    ] == "badvalue"
    assert (
        normalize_browser_config({"runtime_backend": "host_when_available"})["runtime_backend"]
        == "host_required"
    )


def test_browser_config_store_lists_supported_host_targets_and_migrates_endpoint():
    path = PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-config-store.js"
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"^import .*;\n", "", source, flags=re.M)
    source = source.replace("export const store = createStore", "const store = createStore")
    endpoint = "ws://localhost:9222/devtools/browser/old-guid"
    browser_status = {
        "connectors": [
            {
                "browser_id": "chrome-cdp",
                "cdp_endpoint": endpoint,
                "features": ["open_remote_debugging"],
                "available_browsers": [
                    {
                        "id": "chrome-cdp",
                        "family": "chrome-cdp",
                        "label": "Chrome (allowed)",
                        "cdp_endpoint": endpoint,
                    },
                    {
                        "id": "chrome:default",
                        "family": "chrome",
                        "label": "Chrome profile",
                        "cdp_endpoint": "",
                    },
                    {
                        "id": "safari:default",
                        "family": "safari",
                        "label": "Safari - Automation window",
                        "cdp_endpoint": "",
                        "status": "ready",
                    },
                ],
            }
        ]
    }
    script = (
        "const browserStatus = "
        + json.dumps(browser_status)
        + ";\n"
        + "const createStore = (_name, value) => value;\n"
        + "const callJsonApi = async () => ({ host_browser: browserStatus });\n"
        + "const showConfirmDialog = async () => false;\n"
        + source
        + f"\nstore.config = ensureConfig({{ host_browser_selection: {json.dumps(endpoint)} }});\n"
        + "await store.loadHostBrowserStatus();\n"
        + "if (store.config.host_browser_selection !== 'chrome-cdp') throw new Error('legacy endpoint was not migrated');\n"
        + "const values = store.hostBrowserOptions().map((option) => option.value);\n"
        + "if (!values.includes('chrome-cdp')) throw new Error('stable browser id is missing');\n"
        + "if (!values.includes('safari:default')) throw new Error('Safari WebDriver id is missing');\n"
        + f"if (values.includes({json.dumps(endpoint)})) throw new Error('volatile endpoint was advertised');\n"
        + "if (values.includes('chrome:default')) throw new Error('local profiles leaked into the dropdown');\n"
        + "if (!store.hostBrowserSetupAvailable('chrome')) throw new Error('installed Chrome setup is hidden');\n"
        + "if (store.hostBrowserSetupAvailable('opera')) throw new Error('missing Opera setup is visible');\n"
        + "if (store.hostBrowserSetupAvailable('edge')) throw new Error('missing Edge setup is visible');\n"
        + "browserStatus.connectors[0].available_browsers.push({ family: 'edge-dev-a0' });\n"
        + "if (!store.hostBrowserSetupAvailable('edge')) throw new Error('installed Edge Dev setup is hidden');\n"
        + "const custom = 'ws://localhost:9333/devtools/browser/custom';\n"
        + "if (stableHostBrowserSelection(custom, browserStatus) !== custom) throw new Error('custom endpoint changed');\n"
        + "store.config.extension_paths = ['/scoped/extension'];\n"
        + "store.applyExtensionPayload({ extension_paths: ['/global/extension'], extensions: [] });\n"
        + "if (store.config.extension_paths[0] !== '/scoped/extension') throw new Error('refresh replaced scoped or unsaved extensions');\n"

    )

    subprocess.run(["node", "--input-type=module", "-e", script], check=True, text=True)


def test_browser_config_normalizes_max_open_tabs():
    assert normalize_browser_config({"max_open_tabs": "12"})["max_open_tabs"] == 12
    assert normalize_browser_config({"max_open_tabs": "0"})["max_open_tabs"] == 1
    assert normalize_browser_config({"max_open_tabs": "200"})["max_open_tabs"] == 50
    assert normalize_browser_config({"max_open_tabs": "oops"})["max_open_tabs"] == 32


def test_browser_config_normalizes_tab_scope():
    assert normalize_browser_config({})["browser_tab_scope"] == "per_context"
    assert normalize_browser_config({"browser_tab_scope": "shared"})["browser_tab_scope"] == "shared"
    assert normalize_browser_config({"browser_tab_scope": "per-context"})["browser_tab_scope"] == "per_context"
    assert normalize_browser_config({"browser_tab_scope": "everything"})["browser_tab_scope"] == "per_context"


def test_browser_model_selection_uses_presets(monkeypatch):
    import plugins._browser.helpers.config as browser_config_module
    from plugins._model_config.helpers import model_config

    monkeypatch.setattr(
        browser_config_module,
        "get_browser_config",
        lambda agent=None: {"model_preset": "Research", "extension_paths": []},
    )
    monkeypatch.setattr(
        model_config,
        "get_preset_by_name",
        lambda name: {
            "name": "Research",
            "chat": {"provider": "openrouter", "name": "example/model"},
        } if name == "Research" else None,
    )

    selection = resolve_browser_model_selection(SimpleNamespace())

    assert selection["source_kind"] == "preset"
    assert selection["config"] == {"provider": "openrouter", "name": "example/model"}


def test_browser_model_selection_falls_back_to_main_for_missing_preset(monkeypatch):
    from plugins._model_config.helpers import model_config

    monkeypatch.setattr(model_config, "get_preset_by_name", lambda name: None)
    monkeypatch.setattr(
        model_config,
        "get_chat_model_config",
        lambda agent=None: {"provider": "openrouter", "name": "main/model"},
    )

    selection = resolve_browser_model_selection(SimpleNamespace(), {"model_preset": "Missing"})

    assert selection["source_kind"] == "main"
    assert selection["preset_status"] == "missing"
    assert selection["config"] == {"provider": "openrouter", "name": "main/model"}


def test_browser_model_preset_controls_followup_turn_and_clears(monkeypatch):
    import importlib
    import plugins._browser.helpers.config as browser_config_module

    state = {}
    agent = SimpleNamespace(
        set_data=lambda key, value: state.__setitem__(key, value),
        get_data=lambda key: state.get(key),
    )
    monkeypatch.setattr(
        browser_config_module,
        "resolve_browser_model_selection",
        lambda agent=None, settings=None: {
            "source_kind": "preset",
            "selected_preset_name": "Browser",
        },
    )

    browser_config_module.activate_browser_model(agent)
    assert browser_config_module.browser_model_is_active(agent)

    provider_module = importlib.import_module(
        "plugins._browser.extensions.python._functions.agent.Agent.get_chat_model.start._20_browser_model"
    )
    cleanup_module = importlib.import_module(
        "plugins._browser.extensions.python.monologue_end._20_browser_model"
    )
    selected_model = object()
    monkeypatch.setattr(
        provider_module,
        "resolve_browser_model",
        lambda agent, fallback=None: selected_model,
    )
    model_data = {"result": object()}
    provider_module.BrowserModelProvider(agent).execute(data=model_data)
    assert model_data["result"] is selected_model

    cleanup_module.BrowserModelCleanup(agent).execute()
    assert not browser_config_module.browser_model_is_active(agent)


def test_browser_model_preset_options_include_missing_selected(monkeypatch):
    from plugins._model_config.helpers import model_config

    monkeypatch.setattr(
        model_config,
        "get_presets",
        lambda: [{"name": "Balance", "chat": {"provider": "openrouter", "name": "model"}}],
    )

    options = get_browser_model_preset_options(settings={"model_preset": "Deleted"})

    assert options[-1]["name"] == "Deleted"
    assert options[-1]["missing"] is True


def test_browser_main_model_summary_shows_current_model(monkeypatch):
    from plugins._model_config.helpers import model_config

    monkeypatch.setattr(
        model_config,
        "get_chat_model_config",
        lambda agent=None: {"provider": "openrouter", "name": "example/main"},
    )

    assert get_browser_main_model_summary() == "openrouter / example/main"


def test_browser_launch_config_uses_full_chromium_for_all_sessions(tmp_path):
    default_launch = build_browser_launch_config(
        {
            "extension_paths": [],
        }
    )

    assert default_launch["browser_mode"] == "chromium"
    assert default_launch["channel"] is None
    assert default_launch["requires_full_browser"] is True
    assert default_launch["proxy"] is None
    assert "--hide-crash-restore-bubble" in default_launch["args"]
    assert not any(arg.startswith("--load-extension=") for arg in default_launch["args"])
    assert "--no-sandbox" not in default_launch["args"]
    assert "--disable-dev-shm-usage" not in default_launch["args"]
    assert "--disable-gpu" not in default_launch["args"]
    assert "--headless=new" not in default_launch["args"]

    extension_dir = tmp_path / "extension"
    extension_dir.mkdir()

    launch = build_browser_launch_config(
        {
            "extension_paths": [str(extension_dir)],
        }
    )

    assert launch["browser_mode"] == "chromium"
    assert launch["channel"] is None
    assert launch["requires_full_browser"] is True
    assert launch["extensions"]["active"] is True
    assert any(arg.startswith("--load-extension=") for arg in launch["args"])
    assert "--headless=new" not in launch["args"]


def _patch_playwright_cache_root(monkeypatch, tmp_path):
    monkeypatch.delenv("A0_BROWSER_PLAYWRIGHT_CACHE_DIR", raising=False)
    monkeypatch.setattr(
        browser_playwright_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    monkeypatch.setattr(
        browser_playwright_module,
        "get_playwright_chromium_revision",
        lambda: "1169",
    )


def test_browser_uses_patchright_revision_when_newer_playwright_cache_exists(
    monkeypatch, tmp_path
):
    _patch_playwright_cache_root(monkeypatch, tmp_path)
    monkeypatch.setattr(
        browser_playwright_module,
        "get_playwright_chromium_revision",
        lambda: "1228",
    )
    cache_dir = Path(get_playwright_cache_dir())
    expected = cache_dir / "chromium-1228" / "chrome-linux64" / "chrome"
    other = cache_dir / "chromium-1234" / "chrome-linux64" / "chrome"
    expected.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    expected.touch()
    other.touch()

    assert get_playwright_binary() == expected


@pytest.mark.parametrize("platform_dir", ["chrome-linux", "chrome-linux64"])
def test_browser_installs_current_patchright_chromium_for_host_architecture(
    monkeypatch, tmp_path, platform_dir
):
    _patch_playwright_cache_root(monkeypatch, tmp_path)
    monkeypatch.setattr(
        browser_playwright_module,
        "get_playwright_chromium_revision",
        lambda: "1234",
    )
    old_binary = (
        tmp_path / "tmp" / "playwright" / "chromium-1169" / "chrome-linux" / "chrome"
    )
    old_binary.parent.mkdir(parents=True)
    old_binary.touch()
    expected = (
        tmp_path / "tmp" / "playwright" / "chromium-1234" / platform_dir / "chrome"
    )

    def install(command, *, env):
        assert command == [
            sys.executable,
            "-m",
            "patchright",
            "install",
            "chromium",
            "--no-shell",
        ]
        assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "tmp" / "playwright")
        expected.parent.mkdir(parents=True)
        expected.touch()

    monkeypatch.setattr(browser_playwright_module.subprocess, "check_call", install)

    assert ensure_playwright_binary() == expected


def test_browser_hook_installs_patchright_for_existing_self_updated_runtime(monkeypatch):
    current = False

    def is_current(requirement):
        assert requirement == "patchright==1.61.2"
        return current

    def install(command, *, cwd):
        nonlocal current
        assert command == [
            "/usr/local/bin/uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "patchright==1.61.2",
        ]
        assert cwd == str(PROJECT_ROOT / "plugins" / "_browser")
        current = True

    monkeypatch.setattr(
        browser_hooks_module,
        "_patchright_requirement",
        lambda: "patchright==1.61.2",
    )
    monkeypatch.setattr(browser_hooks_module, "_patchright_is_current", is_current)
    monkeypatch.setattr(browser_hooks_module.shutil, "which", lambda name: "/usr/local/bin/uv")
    monkeypatch.setattr(browser_hooks_module.subprocess, "check_call", install)

    browser_hooks_module._ensure_patchright_dependency()

    assert current is True


@pytest.mark.parametrize("socks_installed", [False, True])
def test_browser_install_ensures_httpx_socks_support(monkeypatch, socks_installed):
    installed = socks_installed
    calls = []

    def find_spec(name):
        assert name == "socksio"
        return object() if installed else None

    def install(command, *, cwd):
        nonlocal installed
        assert command == [
            "/usr/local/bin/uv", "pip", "install", "--python", sys.executable,
            "httpx[socks]",
        ]
        assert cwd == str(PROJECT_ROOT / "plugins" / "_browser")
        calls.append(command)
        installed = True

    def prepare():
        assert installed
        return {"binary": "chromium"}

    monkeypatch.setattr(browser_hooks_module.importlib.util, "find_spec", find_spec)
    monkeypatch.setattr(browser_hooks_module.shutil, "which", lambda name: "/usr/local/bin/uv")
    monkeypatch.setattr(browser_hooks_module.subprocess, "check_call", install)
    monkeypatch.setattr(browser_hooks_module, "prepare_playwright_cache", prepare)

    assert browser_hooks_module.install() == {"binary": "chromium"}
    assert len(calls) == (0 if socks_installed else 1)
    assert browser_hooks_module.install() == {"binary": "chromium"}
    assert len(calls) == (0 if socks_installed else 1)


def _write_playwright_binary(cache_dir: Path) -> Path:
    browser_binary = cache_dir / "chromium-1169" / "chrome-linux" / "chrome"
    browser_binary.parent.mkdir(parents=True)
    browser_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    return browser_binary


def test_browser_playwright_cache_uses_tmp_path(monkeypatch, tmp_path):
    _patch_playwright_cache_root(monkeypatch, tmp_path)
    primary_cache = tmp_path / "tmp" / "playwright"
    browser_binary = _write_playwright_binary(primary_cache)

    assert get_playwright_cache_dir() == str(
        tmp_path / "tmp" / "playwright"
    )
    assert browser_playwright_module.get_playwright_cache_dirs() == [
        tmp_path / "tmp" / "playwright",
        tmp_path / "usr" / "plugins" / "_browser" / "playwright",
        tmp_path / "usr" / "browser" / "playwright",
    ]
    assert get_playwright_binary() == browser_binary


def test_browser_playwright_binary_ignores_retired_usr_cache(monkeypatch, tmp_path):
    _patch_playwright_cache_root(monkeypatch, tmp_path)
    _write_playwright_binary(
        tmp_path / "usr" / "plugins" / "_browser" / "playwright"
    )

    assert get_playwright_binary() is None


def test_browser_playwright_cache_migrates_valid_retired_usr_cache(monkeypatch, tmp_path):
    _patch_playwright_cache_root(monkeypatch, tmp_path)
    retired_cache = tmp_path / "usr" / "plugins" / "_browser" / "playwright"
    _write_playwright_binary(retired_cache)

    result = browser_hooks_module.cleanup_playwright_cache()

    assert result["errors"] == []
    assert result["migrated"] == str(retired_cache)
    assert get_playwright_binary() == (
        tmp_path / "tmp" / "playwright" / "chromium-1169" / "chrome-linux" / "chrome"
    )
    assert not retired_cache.exists()


def test_browser_playwright_cache_removes_retired_usr_cache_when_tmp_valid(
    monkeypatch, tmp_path
):
    _patch_playwright_cache_root(monkeypatch, tmp_path)
    primary_cache = tmp_path / "tmp" / "playwright"
    retired_cache = tmp_path / "usr" / "plugins" / "_browser" / "playwright"
    _write_playwright_binary(primary_cache)
    _write_playwright_binary(retired_cache)

    result = browser_hooks_module.cleanup_playwright_cache()

    assert result["errors"] == []
    assert result["migrated"] == ""
    assert str(retired_cache) in result["removed"]
    assert get_playwright_binary() == (
        primary_cache / "chromium-1169" / "chrome-linux" / "chrome"
    )
    assert not retired_cache.exists()


def test_browser_playwright_cache_missing_dirs_do_not_raise(monkeypatch, tmp_path):
    _patch_playwright_cache_root(monkeypatch, tmp_path)

    result = browser_hooks_module.cleanup_playwright_cache()

    assert result["errors"] == []
    assert result["migrated"] == ""
    assert result["removed"] == []
    assert not (tmp_path / "tmp" / "playwright").exists()
    assert browser_playwright_module.get_playwright_cache_dirs() == [
        tmp_path / "tmp" / "playwright",
        tmp_path / "usr" / "plugins" / "_browser" / "playwright",
        tmp_path / "usr" / "browser" / "playwright",
    ]
    assert get_playwright_binary() is None


def test_browser_extension_storage_uses_plugin_user_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        browser_extension_manager_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )

    assert get_extensions_root() == tmp_path / "usr" / "_browser" / "extensions"


def test_browser_extension_manager_uninstalls_only_managed_extensions(monkeypatch, tmp_path):
    monkeypatch.setattr(
        browser_extension_manager_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    managed_extension = get_extensions_root() / "chrome-web-store" / ("a" * 32)
    external_extension = tmp_path / "external-extension"
    for extension_dir, name in (
        (managed_extension, "Managed Extension"),
        (external_extension, "External Extension"),
    ):
        extension_dir.mkdir(parents=True)
        (extension_dir / "manifest.json").write_text(
            json.dumps({"name": name, "version": "1.0.0"}),
            encoding="utf-8",
        )

    saved_configs = []
    monkeypatch.setattr(
        browser_extension_manager_module,
        "get_browser_config",
        lambda: {
            "extension_paths": [str(managed_extension), str(external_extension)],
        },
    )
    monkeypatch.setattr(
        browser_extension_manager_module.plugins,
        "save_plugin_config",
        lambda _plugin, _project, _agent, config: saved_configs.append(config.copy()),
    )

    entries = browser_extension_manager_module.list_browser_extensions()
    managed_entry = next(item for item in entries if item["path"] == str(managed_extension))
    external_entry = next(item for item in entries if item["path"] == str(external_extension))

    assert managed_entry["can_delete"] is True
    assert managed_entry["managed"] is True
    assert external_entry["can_delete"] is False

    result = uninstall_browser_extension(str(managed_extension))

    assert result["name"] == "Managed Extension"
    assert result["extension_paths"] == [str(external_extension)]
    assert not managed_extension.exists()
    assert external_extension.exists()
    assert saved_configs[-1]["extension_paths"] == [str(external_extension)]

    with pytest.raises(ValueError, match="Only Browser-managed"):
        uninstall_browser_extension(str(external_extension))
    assert external_extension.exists()


def test_browser_extension_manager_exposes_openable_manifest_ui(monkeypatch, tmp_path):
    monkeypatch.setattr(
        browser_extension_manager_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    extension_dir = get_extensions_root() / "local-options"
    extension_dir.mkdir(parents=True)
    (extension_dir / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 3,
                "name": "Openable Extension",
                "version": "1.0.0",
                "options_ui": {"page": "options/index.html"},
                "action": {"default_popup": "popup.html"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        browser_extension_manager_module,
        "get_browser_config",
        lambda: {"extension_paths": [str(extension_dir)]},
    )

    entry = browser_extension_manager_module.list_browser_extensions()[0]
    expected_id = browser_extension_manager_module._extension_id_from_path(extension_dir)

    assert entry["id"] == expected_id
    assert entry["has_ui"] is True
    assert entry["open_label"] == "Options"
    assert entry["open_url"] == f"chrome-extension://{expected_id}/options/index.html"
    assert entry["ui"]["targets"][1]["url"] == f"chrome-extension://{expected_id}/popup.html"


def test_browser_extension_manager_parses_web_store_urls():
    extension_id = "a" * 32

    assert parse_chrome_web_store_extension_id(extension_id) == extension_id
    assert (
        parse_chrome_web_store_extension_id(
            f"https://chromewebstore.google.com/detail/example/{extension_id}"
        )
        == extension_id
    )
    assert (
        parse_chrome_web_store_extension_id(
            f"https://chrome.google.com/webstore/detail/example/{extension_id}?hl=en"
        )
        == extension_id
    )


def test_browser_extension_manager_extracts_crx3_zip_payload():
    payload = b"PK\x03\x04zip-payload"
    header = b"metadata"
    crx = b"Cr24" + (3).to_bytes(4, "little") + len(header).to_bytes(4, "little") + header + payload

    assert _crx_zip_payload(crx) == payload


def test_browser_extension_manager_skips_same_version_reinstall(monkeypatch, tmp_path):
    extension_id = "a" * 32
    monkeypatch.setattr(
        browser_extension_manager_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    target = get_extensions_root() / "chrome-web-store" / extension_id
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(
        json.dumps({"name": "Current", "version": "1.0.0"}),
        encoding="utf-8",
    )
    (target / "keep.txt").write_text("current", encoding="utf-8")

    def download(_extension_id, archive_path):
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"name": "Current", "version": "1.0.0"}))
            archive.writestr("replacement.txt", "should not be extracted")

    monkeypatch.setattr(browser_extension_manager_module, "_download_crx", download)
    monkeypatch.setattr(
        browser_extension_manager_module,
        "get_browser_config",
        lambda: {"extension_paths": [str(target)]},
    )
    monkeypatch.setattr(
        browser_extension_manager_module.plugins,
        "save_plugin_config",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        browser_extension_manager_module,
        "close_all_runtimes_sync",
        lambda: pytest.fail("same-version reinstall restarted Browser runtimes"),
    )
    monkeypatch.setattr(
        browser_extension_manager_module,
        "_safe_extract_zip",
        lambda *_args: pytest.fail("same-version reinstall extracted the package"),
    )

    result = browser_extension_manager_module.install_chrome_web_store_extension(extension_id)

    assert result["version"] == "1.0.0"
    assert (target / "keep.txt").read_text(encoding="utf-8") == "current"
    assert not (target / "replacement.txt").exists()


def test_browser_extension_manager_stages_updates_and_restarts_runtime(monkeypatch, tmp_path):
    extension_id = "a" * 32
    monkeypatch.setattr(
        browser_extension_manager_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    target = get_extensions_root() / "chrome-web-store" / extension_id
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(
        json.dumps({"name": "Old", "version": "1.0.0"}),
        encoding="utf-8",
    )
    (target / "old.txt").write_text("old", encoding="utf-8")

    def download(_extension_id, archive_path):
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"name": "Updated", "version": "2.0.0"}))
            archive.writestr("new.txt", "new")

    saved_configs = []
    restarts = []
    monkeypatch.setattr(browser_extension_manager_module, "_download_crx", download)
    monkeypatch.setattr(
        browser_extension_manager_module,
        "get_browser_config",
        lambda: {"extension_paths": [str(target)]},
    )
    monkeypatch.setattr(
        browser_extension_manager_module.plugins,
        "save_plugin_config",
        lambda _plugin, _project, _agent, config: saved_configs.append(config.copy()),
    )
    def restart():
        listed_paths = [
            extension["path"]
            for extension in browser_extension_manager_module.list_browser_extensions()
        ]
        restarts.append(((target / "old.txt").exists(), listed_paths))

    monkeypatch.setattr(browser_extension_manager_module, "close_all_runtimes_sync", restart)

    result = browser_extension_manager_module.install_chrome_web_store_extension(extension_id)

    assert result["name"] == "Updated"
    assert result["version"] == "2.0.0"
    assert restarts == [(True, [str(target)])]
    assert saved_configs[-1]["extension_paths"] == [str(target)]
    assert (target / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (target / "old.txt").exists()
    assert list(target.parent.iterdir()) == [target]


def test_browser_extension_manager_uses_modern_chrome_prodversion(monkeypatch):
    extension_id = "a" * 32

    assert _normalize_chrome_prodversion("Google Chrome 147.0.7727.55") == "147.0.7727.55"
    assert _normalize_chrome_prodversion("Chromium 124") == "124.0.0.0"

    monkeypatch.setenv("A0_BROWSER_EXTENSION_PRODVERSION", "147.0.7727.55")
    assert _detect_chrome_prodversion() == "147.0.7727.55"

    url = _build_web_store_download_url(extension_id, prodversion=_detect_chrome_prodversion())
    assert "prod=chromecrx" in url
    assert "prodversion=147.0.7727.55" in url
    assert "prodversion=120.0.0.0" not in url


def test_browser_quick_settings_and_config_management():
    panel = (PROJECT_ROOT / "plugins/_browser/webui/browser-panel.html").read_text()
    config = (PROJECT_ROOT / "plugins/_browser/webui/config.html").read_text()
    for action in ("Create New Extension with A0", "Chrome Web Store URL", "Install URL", "Scan with A0"):
        assert action not in panel
        assert action in config
    for label in ("Browser LLM Preset", "Chrome Extensions", "More settings", "Configure host browser", "Page zoom"):
        assert label in panel
    assert "Installed extensions" not in panel
    assert "openExtensionUi(extension)" in panel
    assert "setRuntimeBackend('host_required')" in panel
    assert "setRuntimeBackend('container')" in panel
    assert 'x-show="$store.browserPage.runtimeBackend === \'host_required\'"' in panel
    for action in ("history", "clearData", "passwords", "addresses", "extensions", "downloadSettings", "downloads"):
        assert f"openBrowserPage('{action}')" in config
    assert "Do not include" in config
    assert 'x-model.boolean="config.annotation_screenshots"' in config


def test_browser_viewer_allows_slow_extension_startup():
    js = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )

    assert "const BROWSER_SUBSCRIBE_TIMEOUT_MS = 60000;" in js
    assert "const BROWSER_FIRST_INSTALL_TIMEOUT_MS = 300000;" in js
    assert "const BROWSER_COMMAND_TIMEOUT_MS = 45000;" in js
    assert "? BROWSER_FIRST_INSTALL_TIMEOUT_MS" in js
    assert ": BROWSER_SUBSCRIBE_TIMEOUT_MS" in js
    assert "browserInstallExpected" in js
    assert "Installing Chromium for the first Browser run" not in js


def test_browser_viewer_creates_chat_when_no_context_is_selected():
    js = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )

    assert "async ensureContextId()" in js
    assert "async createChatContextForBrowser()" in js
    assert 'callJsonApi("/chat_create"' in js
    assert 'import { getContext, setContext } from "/index.js";' in js
    assert "setContext(contextId)" in js
    assert "chatsStore.setSelected?.(contextId)" in js
    assert "this.contextId = existingContextId;" in js
    assert "this.contextId = contextId;" in js
    assert "let targetContextId = requestedContextId" in js
    assert "|| this.resolveContextId();" in js
    assert "targetContextId = await this.ensureContextId();" in js
    assert "contextId: targetContextId" in js
    assert "No active chat context is selected." not in js


def test_browser_canvas_startup_waits_for_raw_viewport_settle():
    js = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )

    assert "const CANVAS_VIEWPORT_SETTLE_MS = 520;" in js
    assert "const SURFACE_VIEWPORT_STABLE_FRAMES = 4;" in js
    assert "const SURFACE_VIEWPORT_MAX_WAIT_MS = 1200;" in js
    assert "surfaceViewportMeasurement()" in js
    assert "rawWidth" in js
    assert "rawHeight" in js
    assert "const key = `${viewport.rawWidth}x${viewport.rawHeight}`;" in js
    assert "Date.now() - this._surfaceOpenedAt >= CANVAS_VIEWPORT_SETTLE_MS" in js
    assert "while (Date.now() - startedAt <= SURFACE_VIEWPORT_MAX_WAIT_MS)" in js
    assert "this._openPromise && this._openSignature === openSignature" in js
    assert "isCurrentSurfaceOpen(surfaceSequence)" in js
    assert "isCanvasSurfaceVisible(element)" in js
    assert "scheduleViewportSyncForSurface" in js
    assert "const targetChanged = Boolean(" in js
    assert "if (this.hasFrame() && !targetChanged)" in js
    assert "this.cancelFrameRender();" in js
    assert "this.resetRenderedFrame();" in js


def test_browser_interactive_modal_handoff_reconciles_after_xpra_resize():
    js = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )

    assert "const INTERACTIVE_VIEWPORT_SETTLE_MS = 320;" in js
    assert "const surfaceMode = this._mode;" in js
    assert 'surfaceMode === "modal" && this.usesInteractiveTransport()' in js
    assert "this.scheduleViewportSyncForSurface(sequence, INTERACTIVE_VIEWPORT_SETTLE_MS, surfaceMode);" in js
    assert "scheduleViewportSyncForSurface(sequence, delayMs = 0, mode = this._mode)" in js
    assert "this._mode !== mode" in js
    assert "(!force && !restartStream && this._lastViewportKey === key)" in js


def test_browser_surface_handoffs_keep_existing_frame_until_replacement_arrives():
    js = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )
    prepare_start = js.index("prepareSurfaceOpen(nextMode")
    prepare_block = js[prepare_start: js.index("resetViewportTracking()", prepare_start)]
    viewport_start = js.index("resetRenderedFrameIfViewportChanged(viewport =")
    viewport_block = js[viewport_start: js.index("async waitForSurfaceViewport", viewport_start)]
    clear_start = js.index("clearRenderedFrameIfViewportChanged()")
    clear_block = js[clear_start: js.index("beginCommand()", clear_start)]

    assert "modeChanged" not in prepare_block
    assert "if (this.hasFrame() && !targetChanged)" in prepare_block
    assert "this.resetRenderedFrame();" in prepare_block
    assert "this.cancelFrameRender();" in viewport_block
    assert "this.resetRenderedFrame();" not in viewport_block
    assert "this.cancelFrameRender();" in clear_block
    assert "this.resetRenderedFrame();" not in clear_block


def test_browser_canvas_surface_open_waits_for_visible_panel():
    js = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "webui"
        / "right_canvas_register_surfaces"
        / "register-browser.js"
    ).read_text(encoding="utf-8")

    assert "waitForVisibleCanvasPanel" in js
    assert "isVisibleCanvasPanel(panel)" in js
    assert 'panel.closest(".browser-canvas-surface")' in js
    assert 'panel.querySelector(".browser-stage")' in js
    assert "getBoundingClientRect" in js
    assert "stableCount >= 2" in js
    assert "forceCanvasWidthNudgeAfterBrowserMount" not in js


def test_browser_canvas_does_not_resize_after_first_accepted_frame():
    js = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )

    assert "_canvasSurfaceReadySequence" not in js
    assert "_canvasFirstFrameAcceptedSequence" not in js
    assert "_canvasFirstFrameNudgeSequence" not in js
    assert "scheduleCanvasWidthNudgeAfterFirstFrame" not in js
    assert "forceRightCanvasWidthNudge" not in js
    assert "canvas.setWidth?.(nudgedWidth" not in js


def test_browser_canvas_restarts_stream_after_page_navigation():
    js = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )

    assert "async restartCanvasStreamAfterPageChange()" in js
    assert "if (!this.usesScreencastTransport())" in js
    assert '["navigate", "back", "forward", "reload"].includes(commandName)' in js
    assert "await this.restartCanvasStreamAfterPageChange();" in js
    assert "await this.waitForSurfaceViewport({ sequence: surfaceSequence });" in js
    assert "await this.syncViewport(true, { restartStream: true });" in js
    reconnect_index = js.index("contextId: this.activeBrowserContextId")
    restart_index = js.index("await this.restartCanvasStreamAfterPageChange();")
    assert reconnect_index < restart_index


def test_browser_entry_points_prefer_canvas_and_modal_dock_handoff():
    browser_button_path = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "webui"
        / "chat-input-bottom-actions-start"
        / "browser-button.html"
    )
    tool_handler = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "webui"
        / "get_tool_message_handler"
        / "browser-tool-handler.js"
    ).read_text(encoding="utf-8")
    after_loop_handler = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "webui"
        / "set_messages_after_loop"
        / "auto-open-browser-results.js"
    ).read_text(encoding="utf-8")
    register_js = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "webui"
        / "surfaces_register"
        / "register-browser.js"
    ).read_text(encoding="utf-8")
    browser_store = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )
    canvas_store = (PROJECT_ROOT / "webui" / "components" / "canvas" / "right-canvas-store.js").read_text(
        encoding="utf-8"
    )
    modals_js = (PROJECT_ROOT / "webui" / "js" / "modals.js").read_text(encoding="utf-8")
    surfaces_js = (PROJECT_ROOT / "webui" / "js" / "surfaces.js").read_text(encoding="utf-8")

    assert not browser_button_path.exists()
    assert 'defaultOpenMode: "modal"' not in register_js
    assert "beginDockHandoff()" in register_js
    assert "beginSurfaceHandoff" in register_js
    assert "finishDockHandoff()" in register_js
    assert "cancelDockHandoff()" in register_js
    assert "defaultOpenMode" not in canvas_store
    assert "await surface.beginDockHandoff?.(payload)" in canvas_store
    assert "await this.closeDockSourceModal(payload, modalPath)" in canvas_store
    assert "delete openPayload.closeSourceModal" in canvas_store
    assert "await surface.finishDockHandoff?.({ ...openPayload, opened })" in canvas_store
    assert "await surface.cancelDockHandoff?.(payload)" in canvas_store
    assert "async closeDockSourceModal" in canvas_store

    assert "dock(metadata.surfaceId" in surfaces_js
    assert "button.disabled = true" in surfaces_js
    assert "dockSurface(metadata.surfaceId" not in modals_js

    assert "beginSurfaceHandoff()" in browser_store
    assert "finishSurfaceHandoff()" in browser_store
    assert "cancelSurfaceHandoff()" in browser_store
    assert "releaseSurfaceBindings()" in browser_store
    assert "this.releaseSurfaceBindings();" in browser_store

    assert "async function openBrowserSurface" in tool_handler
    assert 'await openSurface("browser", payload);' in tool_handler
    assert "rightCanvasStore" not in tool_handler
    assert "window.ensureModalOpen" not in tool_handler
    assert "window.openModal" not in tool_handler
    assert "function syncOpenBrowserCanvas" in tool_handler
    assert "async function syncOpenBrowserCanvas" in after_loop_handler
    assert "syncBrowserResultsIntoOpenCanvas" in after_loop_handler
    assert '${contextId || ""}' in tool_handler
    assert "contextId || \"\"" in after_loop_handler
    assert '"context_id"' in after_loop_handler
    assert '"contextId"' in after_loop_handler
    assert "rightCanvasStore" not in after_loop_handler
    assert "window.ensureModalOpen" not in after_loop_handler
    assert "window.openModal" not in after_loop_handler

    for js in (tool_handler, after_loop_handler):
        assert "openBrowserModal" not in js
        assert "isBrowserCanvasAlreadyOpen" in js
        assert '[data-surface-id="browser"].is-active .browser-panel' in js
        assert "autoOpenBrowserCanvas" not in js
        assert "autoOpenedBrowsers" not in js
        assert "syncedBrowserCanvases" in js
        assert "const FOCUS_ACTIONS = new Set" in js
        assert "FOCUS_ACTIONS.has(action)" in js

    assert 'id: "browser"' in surfaces_js
    assert "/plugins/_browser/webui/main.html" in surfaces_js

    for js in (tool_handler, after_loop_handler, register_js, browser_store, modals_js, surfaces_js):
        assert "globalThis.Alpine" not in js
        assert "Alpine?.store" not in js
        assert "Alpine.store" not in js


def test_surface_buttons_keep_modal_and_canvas_entry_points_separate():
    canvas_store = (PROJECT_ROOT / "webui" / "components" / "canvas" / "right-canvas-store.js").read_text(
        encoding="utf-8"
    )
    canvas_html = (PROJECT_ROOT / "webui" / "components" / "canvas" / "right-canvas.html").read_text(
        encoding="utf-8"
    )
    canvas_css = (PROJECT_ROOT / "webui" / "components" / "canvas" / "right-canvas.css").read_text(
        encoding="utf-8"
    )
    modals_js = (PROJECT_ROOT / "webui" / "js" / "modals.js").read_text(encoding="utf-8")
    modals_css = (PROJECT_ROOT / "webui" / "css" / "modals.css").read_text(encoding="utf-8")
    surfaces_js = (PROJECT_ROOT / "webui" / "js" / "surfaces.js").read_text(encoding="utf-8")
    surfaces_css = (PROJECT_ROOT / "webui" / "css" / "surfaces.css").read_text(encoding="utf-8")
    close_block = canvas_store[
        canvas_store.index("async close()"):
        canvas_store.index("async dockSurface")
    ]
    undock_block = canvas_store[
        canvas_store.index("async undockSurface"):
        canvas_store.index("async openModalSurface")
    ]
    open_modal_block = canvas_store[
        canvas_store.index("async openModalSurface"):
        canvas_store.index("async undockActiveSurface")
    ]
    should_render_block = canvas_store[
        canvas_store.index("\n  shouldRender()"):
        canvas_store.index("};\n\nexport const store")
    ]
    surface_button_block = surfaces_js[
        surfaces_js.index("function createModalSurfaceButton"):
        surfaces_js.index("function configureModalSurfaceSwitcher")
    ]

    assert "surfaceModes: {}" in canvas_store
    assert "mountedSurfaces: {}" in canvas_store
    assert "recordSurfaceMode(surfaceId" in canvas_store
    assert "latestSurfaceMode(surfaceId)" in canvas_store
    assert "markSurfaceMounted(targetId)" in canvas_store
    assert "isSurfaceRendered(id)" in canvas_store
    assert "isSurfaceVisible(id)" in canvas_store
    assert 'import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";' in canvas_store
    assert "async openLatest(surfaceId" in canvas_store
    assert "async openModalSurface(surfaceId" in canvas_store
    assert "this.recordSurfaceMode(targetId, SURFACE_MODE_DOCKED" in canvas_store
    assert "this.recordSurfaceMode(targetId, SURFACE_MODE_FLOATING)" in canvas_store
    assert "surfaceModes: this.surfaceModes" in canvas_store
    assert "normalizeSurfaceMode(mode)" in canvas_store
    assert "migratePersistedSurfaceState" in canvas_store
    assert "if (this.isMobileMode && !surface.actionOnly)" not in canvas_store
    assert "return await this.openModalSurface(targetId, payload);" in canvas_store
    assert "return await this.open(targetId, payload);" in canvas_store
    assert 'return await this.open(this.activeSurfaceId || this.panelSurfaces[0]?.id || "", { source: "mobile-toggle" });' in canvas_store
    assert "isWelcomeVisible()" in canvas_store
    assert "return !this.isWelcomeVisible();" in should_render_block
    assert "isMobileMode" not in should_render_block
    assert 'document.body.classList.toggle("right-canvas-open", this.isOpen && !this.isMobileMode && this.shouldRender());' in canvas_store
    assert "this.mountedSurfaces = {}" not in close_block
    assert "surface?.close" not in close_block
    assert "this.mountedSurfaces = {}" not in undock_block
    assert "failed to close while undocking" not in undock_block
    assert "this.mountedSurfaces = {}" not in open_modal_block
    assert "failed to close before modal open" not in open_modal_block

    assert '@click="$store.rightCanvas.openLatest(surface.id)"' not in canvas_html
    assert canvas_html.count('@click="$store.rightCanvas.open(surface.id)"') == 2
    assert "body.right-canvas-mobile-mode .right-canvas-rail" in canvas_css
    assert "display: flex !important;" in canvas_css
    assert "body.right-canvas-mobile-mode .right-canvas-shell" in canvas_css
    assert "body.right-canvas-mobile-mode .right-canvas,\nbody.right-canvas-mobile-mode .right-canvas-rail" not in canvas_css

    assert "recordMode(metadata.surfaceId, SURFACE_MODE_FLOATING)" in surfaces_js
    assert "configureModalSurfaceSwitcher" in surfaces_js
    assert "surface-switcher" in surfaces_js
    assert "surface-button" in surfaces_js
    assert "SINGLE_VISIBLE_MODAL_SURFACE_PATHS" not in modals_js
    assert "modal-surface-parked" in surfaces_js
    assert "parkSiblingSurfaceModals(activeModal)" in surfaces_js
    assert "activateModal(modal)" in modals_js
    assert "closeSurfaceGroupModals" not in modals_js
    assert "closeSurfaceGroupModals" in surfaces_js
    assert "const closed = await closeSurfaceGroupModals()" in surfaces_js
    assert "globalThis.closeSurfaceGroupModals = closeSurfaceGroupModals" in surfaces_js
    assert "button.title = title" not in modals_js
    assert "button.title = metadata.title" not in modals_js
    assert "rightCanvasStore.panelSurfaces" not in modals_js
    assert 'await recordMode(normalizedId, SURFACE_MODE_FLOATING)' in surfaces_js
    assert "const openPromise = ensureModalOpen(targetModalPath)" in surface_button_block
    assert "await closeModal(modal.path)" not in surface_button_block
    assert "modalRequiresExplicitClose" in modals_js
    assert "modalSurfaceMetadata" not in modals_js
    assert "modal-content-loaded" in modals_js
    assert '"plugins/_browser/webui/main.html"' not in modals_js
    assert '"plugins/_office/webui/main.html"' not in modals_js
    assert "&& !modalRequiresExplicitClose(newModal)" in modals_js
    assert "if (modalRequiresExplicitClose(modalStack[modalStack.length - 1])) return;" in modals_js
    assert ".modal-surface-switcher" not in modals_css

    modal_stack_z = int(re.search(r"const baseZIndex = (\d+);", modals_js).group(1))
    modal_css_z = int(re.search(r"\.modal \{[^}]*z-index: (\d+);", modals_css, re.S).group(1))
    legacy_overlay_z = int(re.search(r"\.modal-overlay \{[^}]*z-index: (\d+);", modals_css, re.S).group(1))
    mobile_canvas_z = int(
        re.search(
            r"body\.right-canvas-mobile-mode \.right-canvas \{[^}]*z-index: (\d+);",
            canvas_css,
            re.S,
        ).group(1)
    )
    assert mobile_canvas_z == 3400
    assert modal_stack_z > mobile_canvas_z
    assert modal_css_z > mobile_canvas_z
    assert legacy_overlay_z > mobile_canvas_z
    assert "@media (max-width: 420px)" in canvas_css
    assert "body.right-canvas-mobile-mode .right-canvas-rail {\n    gap: 5px;" in canvas_css
    assert "transform: translateY(-50%) scale(0.92);" in canvas_css
    assert ".surface-switcher" in surfaces_css
    assert ".surface-button" in surfaces_css
    assert ".modal-surface-button.is-active" in surfaces_css
    assert ".modal-surface-image" in surfaces_css
    assert ".modal.modal-surface-parked" in surfaces_css
    assert "@media (max-width: 768px)" in surfaces_css
    assert ".modal-inner.surface-modal .surface-modal-action-group-surfaces" in surfaces_css
    assert ".modal-inner.surface-modal .surface-modal-action-group-window" in surfaces_css
    assert ".modal-inner.surface-modal .surface-modal-action-group-new" in surfaces_css
    assert ".modal-inner.editor-modal .surface-modal-action-group-new" in surfaces_css
    assert ".surface-modal-new-action:not(.editor-header-actions)" in surfaces_css
    assert "const safeMinWidth = Math.min(minWidth, maxWidth)" in surfaces_js
    assert "grid-auto-flow: column" in surfaces_css
    assert 'id: "browser"' in surfaces_js
    assert 'id: "desktop"' in surfaces_js
    assert "/plugins/_browser/webui/main.html" in surfaces_js
    assert "/plugins/_desktop/webui/main.html" in surfaces_js


def test_transient_ui_layers_above_modals_below_confirm_dialogs():
    index_css = (PROJECT_ROOT / "webui" / "index.css").read_text(encoding="utf-8")
    modals_js = (PROJECT_ROOT / "webui" / "js" / "modals.js").read_text(encoding="utf-8")
    modals_css = (PROJECT_ROOT / "webui" / "css" / "modals.css").read_text(encoding="utf-8")
    toast_html = (
        PROJECT_ROOT / "webui" / "components" / "notifications" / "notification-toast-stack.html"
    ).read_text(encoding="utf-8")

    modal_base_z = int(re.search(r"const baseZIndex = (\d+);", modals_js).group(1))
    legacy_overlay_z = int(re.search(r"\.modal-overlay \{[^}]*z-index: (\d+);", modals_css, re.S).group(1))
    confirm_z = int(re.search(r"\.confirm-dialog-backdrop \{[^}]*z-index: (\d+);", modals_css, re.S).group(1))
    toast_z = int(re.search(r"\.toast-stack-container \{[^}]*z-index: (\d+);", toast_html, re.S).group(1))
    tooltip_z_indexes = [
        int(z)
        for z in re.findall(r"\.tooltip \{[^}]*z-index: (\d+);", index_css, re.S)
    ]

    assert tooltip_z_indexes
    assert toast_z > max(modal_base_z + 20, legacy_overlay_z)
    assert all(z > toast_z for z in tooltip_z_indexes)
    assert all(z < confirm_z for z in [toast_z, *tooltip_z_indexes])


def test_browser_tool_does_not_auto_open_canvas_policy_is_documented():
    prompt = (
        PROJECT_ROOT / "plugins" / "_browser" / "prompts" / "agent.system.tool.browser.md"
    ).read_text(encoding="utf-8")
    from helpers import tokens

    config = (PROJECT_ROOT / "plugins" / "_browser" / "default_config.yaml").read_text(
        encoding="utf-8"
    )
    config_html = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "config.html").read_text(
        encoding="utf-8"
    )
    config_store_js = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-config-store.js"
    ).read_text(encoding="utf-8")

    assert "must not open a Browser surface automatically" in prompt
    assert "Use the tool headlessly unless the user opens the Browser surface" in prompt
    assert "optional visible WebUI viewer" in prompt
    assert "screenshot" in prompt
    assert "vision_load" in prompt
    assert "select_option" in prompt
    assert "set_checked" in prompt
    assert "upload_file" in prompt
    assert "browser-form-workflows" in prompt
    assert "first load `browser-automation` with `skills_tool:load`" in prompt
    assert "`browser-automation` links to `browser-form-workflows`" in prompt
    assert "does not automatically load screenshots" in prompt
    browser_skill = (PROJECT_ROOT / "plugins" / "_browser" / "skills" / "browser-automation" / "SKILL.md").read_text(encoding="utf-8")
    assert "chrome://inspect/#remote-debugging" in browser_skill
    assert "opera://inspect/#remote-debugging" in browser_skill
    assert tokens.approximate_tokens(prompt) <= 650
    assert "already open" in config
    assert "already-open Browser surface" in config_html
    assert "chrome://inspect/#remote-debugging" in config_html
    assert "opera://inspect/#remote-debugging" in config_html
    assert "Safari Settings &gt; Advanced" in config_html
    assert "Show features for web developers" in config_html
    assert "Allow remote automation" in config_html
    assert "dedicated automation window" in config_html
    assert "Safari setup steps" in config_html
    assert "Chromium browser setup steps" in config_html
    assert "openHostBrowserSetup('chrome')" in config_html
    assert "openHostBrowserSetup('opera')" in config_html
    assert "openHostBrowserSetup('edge')" in config_html
    assert "hostBrowserSetupAvailable('chrome')" in config_html
    assert "hostBrowserSetupAvailable('opera')" in config_html
    assert "hostBrowserSetupAvailable('edge')" in config_html
    assert "Brave, Vivaldi, and Chromium are supported" in config_html
    assert 'const BROWSER_SETUP_API = "/plugins/_browser/host_browser_setup"' in config_store_js
    assert "openHostBrowserSetup(browserFamily)" in config_store_js
    assert "hostBrowserSetupAvailable(browserFamily)" in config_store_js
    assert "Manual debug endpoint" in config_html
    assert "A0_HOST_BROWSER_REMOTE_DEBUGGING_ENDPOINTS" in config_html
    assert "Custom endpoint" in config_html
    assert "localhost:9222" in config_html
    assert "customHostBrowserEndpointDiagnostic" in config_store_js
    assert "http(s):// discovery address" in config_store_js
    assert "HOST_BROWSER_STATUS_REFRESH_MS = 1000" in config_store_js


def test_browser_skills_are_plugin_owned_and_progressively_linked():
    automation_path = (
        PROJECT_ROOT / "plugins" / "_browser" / "skills" / "browser-automation" / "SKILL.md"
    )
    skill_path = PROJECT_ROOT / "plugins" / "_browser" / "skills" / "browser-form-workflows" / "SKILL.md"
    assert automation_path.exists()
    assert skill_path.exists()
    automation = automation_path.read_text(encoding="utf-8")
    skill = skill_path.read_text(encoding="utf-8")
    assert skill.startswith("---\n")
    automation_frontmatter = automation.split("---", 2)[1]
    frontmatter = skill.split("---", 2)[1]
    assert "name: browser-automation" in automation_frontmatter
    assert "triggers:" in automation_frontmatter
    assert "browser screenshot" in automation_frontmatter
    assert "host browser" in automation_frontmatter
    assert "name: browser-form-workflows" in frontmatter
    assert "description:" in frontmatter
    assert "triggers:" in frontmatter
    assert "fill web form" in frontmatter
    assert "file upload" in frontmatter
    assert "progressive-disclosure workflow guide" in automation
    assert "`browser-form-workflows` with `skills_tool:load`" in automation
    assert 'skill_name: "browser-form-workflows"' in automation
    assert "form-specific extension of `browser-automation`" in skill
    assert "select_option" in skill
    assert "set_checked" in skill
    assert "upload_file" in skill
    assert "browser:screenshot" in skill
    assert "vision_load" in skill


def test_browser_canvas_uses_plain_panel_without_debug_probe():
    panel_html = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "webui"
        / "right-canvas-panels"
        / "browser-panel.html"
    ).read_text(encoding="utf-8")
    browser_store = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js").read_text(
        encoding="utf-8"
    )
    register_js = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "webui"
        / "right_canvas_register_surfaces"
        / "register-browser.js"
    ).read_text(encoding="utf-8")
    canvas_store = (PROJECT_ROOT / "webui" / "components" / "canvas" / "right-canvas-store.js").read_text(
        encoding="utf-8"
    )
    modals_js = (PROJECT_ROOT / "webui" / "js" / "modals.js").read_text(encoding="utf-8")

    assert 'x-component path="/plugins/_browser/webui/browser-panel.html" mode="canvas"' in panel_html
    assert "browserCanvasRemountKey" not in panel_html
    assert "remountBrowserCanvasOnce" not in panel_html
    assert "data-remount-slot" not in panel_html

    for js in (browser_store, register_js, canvas_store, modals_js):
        assert "__a0BrowserDebug" not in js
        assert "browserDebug" not in js
        assert "emitBrowserDebug" not in js
        assert ".debug(" not in js


def test_browser_ui_spinners_have_browser_local_animation():
    main_html = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-panel.html").read_text(
        encoding="utf-8"
    )
    config_html = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "config.html").read_text(
        encoding="utf-8"
    )

    assert ":class=\"{ spinning: $store.browserConfig.extensionActionLoading }\"" in config_html
    assert "@keyframes browser-spin" in main_html
    assert "@keyframes browser-config-spin" in config_html


def test_browser_extension_settings_stay_user_facing():
    config_html = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "config.html").read_text(
        encoding="utf-8"
    )
    config_store = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-config-store.js"
    ).read_text(encoding="utf-8")

    assert "Choose which installed Chrome extensions Browser loads." in config_html
    assert "Installed extensions" in config_html
    assert "Browser tabs" in config_html
    assert "Separate per chat" in config_html
    assert "Shared across chats" in config_html
    assert "Maximum tabs per chat" in config_html
    assert "Each chat shows only its own tabs. Browser sign-ins are shared across chats." in config_html
    assert "The tab strip shows tabs from every active chat. Browser sign-ins are shared across chats." in config_html
    assert 'x-model="$store.browserConfig.config.browser_tab_scope"' in config_html
    assert 'x-model.number="$store.browserConfig.config.max_open_tabs"' in config_html
    assert 'x-model="$store.browserConfig.config.proxy_server"' in config_html
    assert 'x-model="$store.browserConfig.config.proxy_bypass"' in config_html
    assert 'x-model="$store.browserConfig.config.proxy_username"' in config_html
    assert 'x-model="$store.browserConfig.config.proxy_password"' in config_html
    assert '<details\n            class="browser-config-proxy"' in config_html
    assert "<summary>Proxy server</summary>" in config_html
    assert 'type="password"' in config_html
    assert "normalizeMaxOpenTabs()" in config_html
    assert "BROWSER_TAB_SCOPES" in config_store
    assert "HARD_MAX_OPEN_TABS = 50" in config_store
    assert "extensionDeleteTitle(extension)" in config_html
    assert "deleteExtension(extension)" in config_html
    assert "Delete extension" in config_store
    assert 'import { showConfirmDialog } from "/js/confirmDialog.js";' in config_store
    assert "const safeName = name.replace" in config_store
    assert "const confirmed = await showConfirmDialog({" in config_store
    assert "globalThis.confirm" not in config_store
    assert "<textarea" not in config_html
    assert "Enabled extension directories" not in config_html
    assert "Chrome Web Store URL installs" not in config_html
    assert "Browser caches Playwright Chromium" not in config_html


def test_browser_tab_switch_completes_without_reloading_shared_interactive_viewer():
    source = (PROJECT_ROOT / "plugins/_browser/webui/browser-store.js").read_text(encoding="utf-8")
    source = source[source.index("const BROWSER_SUBSCRIBE_TIMEOUT_MS"):source.index("export const store")]
    script = """
import assert from 'node:assert/strict';
let responseData;
let superseded = false;
const websocket = { request: async () => {
  if (superseded) model._connectSequence++;
  return { results: [{ ok: true, data: responseData }] };
} };
""" + source + """
Object.assign(model, {
  loading: false, contextId: 'ctx', activeBrowserContextId: 'ctx', activeBrowserId: 2,
  _bindSocketEvents: async () => {},
  currentViewportSize: () => ({ width: 900, height: 600 }),
});
for (const [transport, oldUrl, nextUrl, stale, busy] of [
  ['interactive', '/viewer', '/viewer', false, false],
  ['interactive', '', '/viewer', false, true],
  ['interactive', '/viewer', '/new-viewer', false, true],
  ['screencast', '/viewer', '', false, true],
  ['snapshot', '', '', false, true],
  ['interactive', '/viewer', '/viewer', true, true],
]) {
  Object.assign(model, {
    viewerTransport: transport, interactiveViewUrl: oldUrl,
    switchingBrowserId: 2, _surfaceSwitching: true,
  });
  responseData = {
    browsers: [{ id: 2, context_id: 'ctx', loading: false }],
    active_browser_id: 2, viewer_transport: transport,
    interactive_view: { available: Boolean(nextUrl), url: nextUrl },
  };
  superseded = stale;
  await model.connectViewer({ browserId: 2, contextId: 'ctx' });
  assert.equal(model.isBusy(), busy, JSON.stringify([transport, oldUrl, nextUrl, stale]));
  assert.equal(model.isBrowserLoading(model.browsers[0]), busy);
  assert.equal(model._surfaceSwitching, busy);
  assert.equal(model.switchingBrowserId, busy ? 2 : null);
  assert.equal(model.interactiveViewUrl, stale ? oldUrl : nextUrl);
}
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True, text=True)


def test_browser_viewer_clears_empty_context_and_ignores_late_responses():
    source = (PROJECT_ROOT / "plugins/_browser/webui/browser-store.js").read_text(encoding="utf-8")
    source = source[source.index("const BROWSER_SUBSCRIBE_TIMEOUT_MS"):source.index("export const store")]
    script = """
import assert from 'node:assert/strict';
const ok = data => ({ results: [{ ok: true, data }] });
const empty = context_id => ({ context_id, active_browser_id: null, browsers: [],
  viewer_transport: 'snapshot', interactive_view: null });
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return {promise, resolve}; };
let request = async () => ok(empty('empty'));
const websocket = { request: (...args) => request(...args), emit: async () => {} };
const chatsStore = { selected: 'old' };
""" + source + """
Object.assign(model, {
  loading: false, _surfaceMounted: true,
  contextId: 'old', activeBrowserContextId: 'old', activeBrowserId: 1,
  browsers: [{ id: 1, context_id: 'old', currentUrl: 'https://old.example' }],
  address: 'https://old.example', addressFocused: true,
  frameState: { id: 1, currentUrl: 'https://old.example' },
  switchingBrowserId: 1, _surfaceSwitching: true,
  _bindSocketEvents: async () => {},
  currentViewportSize: () => ({ width: 900, height: 600 }),
  isVisibleBrowserSurface: () => true,
  syncViewportAfterSurfaceOpen: async () => {},
});
// Empty subscriptions are authoritative, even if the previous tab still exists elsewhere.
await model.connectViewer({ browserId: null, contextId: 'empty' });
assert.equal(model.activeBrowserId, null);
assert.equal(model.address, '');
assert.equal(model.frameState, null);
assert.equal(model.isBusy(), false);

// A structured server failure must release the same spinner as a transport failure.
for (const transportFailure of [false, true]) {
  Object.assign(model, { switchingBrowserId: 1, _surfaceSwitching: true });
  request = async () => {
    if (transportFailure) throw new Error('offline');
    return { results: [{ ok: false, error: { error: 'offline' } }] };
  };
  await assert.rejects(model.connectViewer({ contextId: 'empty' }), /offline/);
  assert.equal(model.isBusy(), false);
  assert.equal(model.connected, false);
}

// Two pending context refreshes finish out of order. Only the latest may subscribe.
const slow = deferred();
const fast = deferred();
const subscriptions = [];
model.refreshBrowserSessions = async id => {
  if (id === 'slow') await slow.promise;
  if (id === 'fast') await fast.promise;
};
request = async (event, data) => {
  subscriptions.push(data.context_id);
  return ok(empty(data.context_id));
};
const switchingSlow = model.syncViewerToSelectedContext('slow');
await Promise.resolve();
const switchingFast = model.syncViewerToSelectedContext('fast');
await Promise.resolve();
slow.resolve();
await switchingSlow;
assert.equal(model.loading, true);
fast.resolve();
await switchingFast;
assert.deepEqual(subscriptions, ['fast']);
assert.equal(model.contextId, 'fast');
assert.equal(model.isBusy(), false);

// Leaving a chat also invalidates an already pending viewer response.
const pending = deferred();
request = async () => pending.promise;
const connecting = model.connectViewer({ browserId: 1, contextId: 'old' });
await Promise.resolve();
await Promise.resolve();
await model.syncViewerToSelectedContext('');
pending.resolve(ok({ active_browser_id: 1, browsers: model.browsers,
  viewer_transport: 'interactive', interactive_view: { available: true, url: '/old-viewer' } }));
await connecting;
assert.equal(model.contextId, '');
assert.equal(model.activeBrowserId, null);
assert.equal(model.address, '');
assert.equal(model.interactiveViewUrl, '');
assert.equal(model.isBusy(), false);

// A late open-command result cannot take the user back to their previous chat.
const commandReply = deferred();
request = async () => commandReply.promise;
model.contextIdForNewBrowser = async () => 'old';
const opening = model.command('open');
await Promise.resolve();
await model.syncViewerToSelectedContext('');
commandReply.resolve(ok({ result: { id: 1, context_id: 'old', currentUrl: 'https://old.example' },
  browsers: [{ id: 1, context_id: 'old' }] }));
await opening;
assert.equal(model.contextId, '');
assert.equal(model.address, '');
assert.equal(model.activeBrowserId, null);
assert.equal(model.isBusy(), false);
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True, text=True)


def test_browser_viewer_uses_tabs_for_session_switching():
    main_html = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-panel.html").read_text(
        encoding="utf-8"
    )
    browser_store = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js"
    ).read_text(encoding="utf-8")

    assert 'class="browser-session-tabs" role="tablist"' in main_html
    assert 'class="browser-tab"' in main_html
    assert 'class="browser-new-tab surface-control"' in main_html
    assert 'browser in $store.browserPage.visibleBrowsers()' in main_html
    assert ':key="$store.browserPage.browserTabKey(browser)"' in main_html
    assert "browser.context_id" in main_html
    assert ':title="$store.browserPage.browserTabTooltip(browser)"' in main_html
    assert ':aria-busy="$store.browserPage.isBrowserLoading(browser).toString()"' in main_html
    assert 'class="browser-tab-loading"' in main_html
    assert "'is-visible': $store.browserPage.isBrowserLoading(browser)" in main_html
    tab_button = main_html.index('class="browser-tab"')
    tab_button_end = main_html.index("</button>", tab_button)
    tab_spinner = main_html.index('class="browser-tab-loading"', tab_button_end)
    tab_close = main_html.index('class="browser-tab-close"', tab_spinner)
    assert tab_button_end < tab_spinner < tab_close
    assert "<span x-text=\"$store.browserPage.loadingMessage()\">Loading</span>" not in main_html
    assert "isBrowserLoading(browser)" in browser_store
    assert "loadingMessage()" not in browser_store
    assert 'class="browser-empty browser-starting" role="status" aria-live="polite"' in main_html
    assert "browserLoadingLabel()" in browser_store
    assert "Starting Browser…" in browser_store
    assert "browser-tab-context" not in main_html
    assert 'handleSelectedContextChange($store.chats?.selected)' in main_html
    assert "activeBrowserContextId" in browser_store
    assert "sameBrowserTab" in browser_store
    assert "applyBrowserListing" in browser_store
    assert "syncViewerToSelectedContext(selectedContextId)" in browser_store
    assert "async syncViewerToSelectedContext" in browser_store
    assert "const selectedContextId = this.normalizeContextId(chatsStore.selected);" in browser_store
    assert "this.contextId = selectedContextId;" in browser_store
    assert "isVisibleBrowserSurface()" in browser_store
    assert "firstBrowserInContext(selectedContextId)" in browser_store
    assert "visibleBrowsers()" in browser_store
    assert 'tabScope: "per_context"' in browser_store
    assert "applyTabScope(data)" in browser_store
    assert 'if (this.tabScope === "shared") return browsers;' in browser_store
    assert "requestedContextId && requestedContextId !== inFlightContextId" in browser_store
    assert "create_browser: Boolean(options.createBrowser || options.create_browser)" in browser_store
    assert "browserTabTooltip(browser)" in browser_store
    assert "browserChatTitle(browser = {})" in browser_store
    assert "contextId.slice" not in browser_store
    assert '"browser_viewer_sessions"' in browser_store
    assert "$store.browserPage.openNewBrowser()" in main_html
    assert "browser-select" not in main_html
    assert "browser-live-dot" not in main_html
    assert "async openNewBrowser()" in browser_store
    assert "browserTabTitle(browser)" in browser_store
    assert "Review with A0" not in browser_store
    assert "Using ${this.mainModelSummary}" in browser_store


def test_browser_tabs_close_without_confirmation_or_busy_lock():
    main_html = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-panel.html").read_text(
        encoding="utf-8"
    )
    browser_store = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js"
    ).read_text(encoding="utf-8")
    close_start = main_html.index('class="browser-tab-close"')
    close_end = main_html.index("</button>", close_start)
    close_markup = main_html[close_start:close_end]

    assert '@click.stop="$store.browserPage.closeBrowser(browser.id, browser.context_id)"' in main_html
    assert "@pointerdown.stop" in close_markup
    assert "$confirmClick" not in main_html
    assert "isBusy()" not in close_markup
    assert ':disabled="$store.browserPage.isClosingBrowser(browser.id, browser.context_id)"' in close_markup
    assert "--browser-tab-close-size: 32px;" in main_html
    assert "async closeBrowser(id, contextId = \"\")" in browser_store
    assert "isClosingBrowser(id, contextId = \"\")" in browser_store
    assert "_closingBrowserIds" in browser_store
    assert "_commandInFlightCount" in browser_store


def test_browser_viewer_defaults_to_interactive_with_screencast_and_snapshot_fallbacks():
    ws_browser = (PROJECT_ROOT / "plugins" / "_browser" / "api" / "ws_browser.py").read_text(
        encoding="utf-8"
    )
    main_html = (PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-panel.html").read_text(
        encoding="utf-8"
    )
    runtime = (
        PROJECT_ROOT / "plugins" / "_browser" / "helpers" / "runtime.py"
    ).read_text(encoding="utf-8")
    browser_store = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js"
    ).read_text(encoding="utf-8")
    browser_tool_handler = (
        PROJECT_ROOT / "plugins" / "_browser" / "extensions" / "webui" / "get_tool_message_handler" / "browser-tool-handler.js"
    ).read_text(encoding="utf-8")

    assert 'runtime.call("screenshot"' in ws_browser
    assert 'VIEWER_TRANSPORT_SNAPSHOT = "snapshot"' in ws_browser
    assert 'VIEWER_TRANSPORT_SCREENCAST = "screencast"' in ws_browser
    assert 'VIEWER_TRANSPORT_INTERACTIVE = "interactive"' in ws_browser
    assert "async def _effective_viewer(" in ws_browser
    assert "return VIEWER_TRANSPORT_SCREENCAST, viewer" in ws_browser
    assert "def _viewer_transport(data: dict[str, Any])" in ws_browser
    assert "return VIEWER_TRANSPORT_SNAPSHOT" in ws_browser
    assert "self._stream_state" in ws_browser
    assert "SCREENCAST_STREAM_QUALITY = 80" in ws_browser
    assert "SCREENSHOT_QUALITY = 92" in ws_browser
    assert "initial_viewport = self._viewport_from_data(data)" in ws_browser
    assert '"set_viewport"' in ws_browser
    assert "start_screencast" in ws_browser
    assert '"attach_screencast_consumer"' in ws_browser
    assert "asyncio.run_coroutine_threadsafe" in ws_browser
    assert 'runtime.call(\n                            "read_screencast_frame"' not in ws_browser
    assert "read_screencast_frame" in runtime
    assert "FRAME_READ_TIMEOUT_SECONDS" in ws_browser
    assert "FRAME_IDLE_POLL_SECONDS" not in ws_browser
    assert "except TimeoutError:" in ws_browser
    assert "stop_screencast" in ws_browser
    assert "viewer_transport == VIEWER_TRANSPORT_SCREENCAST" in ws_browser
    assert "viewer_transport != VIEWER_TRANSPORT_INTERACTIVE" in ws_browser
    assert "if viewer_transport == VIEWER_TRANSPORT_INTERACTIVE" in ws_browser
    assert '"viewer_transport": viewer_transport' in ws_browser
    assert "viewer_transport: str = VIEWER_TRANSPORT_SNAPSHOT" in ws_browser
    assert '"Page.startScreencast"' in runtime
    assert '"Page.screencastFrame"' in runtime
    assert '"Page.screencastFrameAck"' in runtime
    assert "async def attach_screencast_consumer" in runtime
    assert "async def attach_consumer" in runtime
    assert "stop_callback: Any | None = None" in runtime
    assert "def _notify_stopped(self) -> None:" in runtime
    assert "server_loop.call_soon_threadsafe(stop_event.set)" in ws_browser
    assert "await self._deliver_frame(" in runtime
    assert "await asyncio.wrap_future(future)" in runtime
    assert '"Page.stopScreencast"' in runtime
    assert '"Emulation.setDeviceMetricsOverride"' in runtime
    assert '"Emulation.setVisibleSize"' in runtime
    assert "asyncio.Queue(maxsize=1)" in runtime
    assert "await self._stop_screencasts_for_browser(resolved_id)" in runtime
    assert "queueFrameRender" in browser_store
    assert "requestAnimationFrame" in browser_store
    assert "function frameImageSource(data = {})" in browser_store
    assert "const BROWSER_BINARY_FRAME_REQUESTS_ENABLED = false;" in browser_store
    assert "const BROWSER_BINARY_PAYLOADS_SUPPORTED = typeof Blob" in browser_store
    assert "const BROWSER_CANVAS_FRAMES_SUPPORTED = typeof globalThis.createImageBitmap" in browser_store
    assert "if (data.encoding === \"binary\") return null;" in browser_store
    assert "async function loadFrameBitmap(src, options = {})" in browser_store
    assert "return await globalThis.createImageBitmap(blob);" in browser_store
    assert 'const BROWSER_VIEWER_TRANSPORT_SNAPSHOT = "snapshot";' in browser_store
    assert 'const BROWSER_VIEWER_TRANSPORT_SCREENCAST = "screencast";' in browser_store
    assert 'const BROWSER_VIEWER_TRANSPORT_INTERACTIVE = "interactive";' in browser_store
    assert "const VIEWPORT_SYNC_INTERVAL_MS = 50;" in browser_store
    assert "viewerTransport: BROWSER_VIEWER_TRANSPORT_INTERACTIVE" in browser_store
    assert "return BROWSER_VIEWER_TRANSPORT_INTERACTIVE;" in browser_store
    assert "usesInteractiveTransport()" in browser_store
    assert "isInteractiveSurface(stage = null)" in browser_store
    assert "prepareInteractiveViewFrame(frame = null)" in browser_store
    assert 'style.id = "a0-xpra-browser-frame-css";' in browser_store
    assert "#shadow_pointer" in browser_store
    assert "xpraWindow._set_decorated?.(false);" in browser_store
    assert "xpraWindow.updateCSSGeometry?.();" in browser_store
    assert "syncInteractiveViewSize()" in browser_store
    assert "frame?.contentWindow?.client?._screen_resized?.();" in browser_store
    assert "applyViewer(data = {})" in browser_store
    assert "requestedViewerTransport()" in browser_store
    assert "normalizeViewerTransport(value = \"\")" in browser_store
    assert "usesScreencastTransport()" in browser_store
    assert "supportsBinaryFrames()" in browser_store
    assert "captureDevicePixelRatio()" in browser_store
    assert "frameDimensionsFromData(data = null)" in browser_store
    assert "frameDimensionsFromMetadata(metadata = null)" in browser_store
    assert "metadata.expectedWidth || metadata.deviceWidth || metadata.jpegWidth" in browser_store
    assert "dimensions: this.frameDimensionsFromData(data)" in browser_store
    assert "useCanvas: true" in browser_store
    assert "let dimensions = options?.dimensions || null" in browser_store
    assert "dimensions ||= await loadFrameDimensions(frameSrc)" in browser_store
    assert "paintFrameBitmap(bitmap)" in browser_store
    assert "if (canvas.width !== bitmap.width) canvas.width = bitmap.width;" in browser_store
    assert "freezeCanvasFrameToImage()" in browser_store
    assert "currentFrameCanvas()" in browser_store
    assert 'this._stageElement?.querySelector?.(".browser-frame-canvas")' in browser_store
    assert 'canvas.toDataURL("image/jpeg", 0.86)' in browser_store
    assert "this.frameSrc = frameSrc;" in browser_store
    assert "hasFrame()" in browser_store
    assert "frameCanvasReady: false" in browser_store
    assert "attachFrameCanvas(canvas = null)" in browser_store
    assert "viewer_transport: this.requestedViewerTransport()" in browser_store
    assert "binary_frames: this.supportsBinaryFrames()" in browser_store
    assert "slim_frames: true" in browser_store
    assert "device_pixel_ratio: this.captureDevicePixelRatio()" in browser_store
    assert "viewport_width: initialViewport?.width" in browser_store
    assert "viewport_height: initialViewport?.height" in browser_store
    assert "restart_stream: restartStream && this.usesScreencastTransport()" in browser_store
    assert 'restart_screencast=bool(data.get("restart_stream"))' in ws_browser
    assert "restart_screencast: bool = False" in runtime
    assert "should_restart_screencast = changed or restart_screencast" in runtime
    assert "await self._apply_cdp_viewport({\"width\": width, \"height\": height})" in runtime
    assert "await page.set_viewport_size(viewport)" in runtime
    assert "VIEWPORT_REMOUNT_PAUSE_SECONDS" not in runtime
    assert "_nudged_viewport" not in runtime
    assert 'wait_until="commit"' in ws_browser
    assert 'restartStream: this._mode === "canvas" && this.usesScreencastTransport()' in browser_store
    assert "this.frameState = data.state || null" not in browser_store
    assert "function loadFrameDimensions(src)" in browser_store
    assert "frameMatchesViewport(dimensions = null, viewport = null)" in browser_store
    assert "shouldAcceptMismatchedFrame" not in browser_store
    assert "requestViewportSyncAfterRejectedFrame()" in browser_store
    assert "this.applySnapshot(data.snapshot);" in browser_store
    assert "if (!this.frameCanvasReady || !this.usesScreencastTransport())" in browser_store
    assert "else if (!data.state)" in browser_store
    assert '"snapshot": snapshot' in ws_browser
    assert '"binary_frames": binary_frames' in ws_browser
    assert '"slim_frames": slim_frames' in ws_browser
    assert "capture_scale=capture_scale" in ws_browser
    assert "base64.b64decode(image, validate=False)" in ws_browser
    assert '"encoding"] = "binary"' in ws_browser
    assert "def _frame_payload(" in ws_browser
    assert "def _emit_viewer_state(" in ws_browser
    assert 'const BROWSER_SNAPSHOT_META_KEY = "browser_snapshot";' in browser_tool_handler
    assert "staticScreenshotUri(kvps)" in browser_tool_handler
    assert "/components/modals/image-viewer/image-viewer-store.js" in browser_tool_handler
    assert "function openStaticScreenshot(uri = \"\")" in browser_tool_handler
    assert "imageViewerStore.open(src, { name: \"Browser screenshot\" });" in browser_tool_handler
    assert "if (staticUri) {" in browser_tool_handler
    assert "openStaticScreenshot(staticUri);" in browser_tool_handler
    assert "delete displayKvps[BROWSER_SNAPSHOT_META_KEY];" in browser_tool_handler
    assert "startBrowserScreenshotPreview(button, image, resolveBrowserPayload)" in browser_tool_handler
    assert "FRAME_FALLBACK_SCREENSHOT_SECONDS" not in ws_browser
    assert '"browser_viewer_state"' in ws_browser
    assert '"frame_source": VIEWER_TRANSPORT_SCREENCAST' in ws_browser
    assert '"viewer_transport": VIEWER_TRANSPORT_SCREENCAST' in ws_browser
    assert "fallback_screenshot" not in ws_browser
    assert "canvas_wheel_screenshot" not in ws_browser
    assert "surface_mode: this._mode" not in browser_store
    assert '<canvas class="browser-frame browser-frame-canvas"' in main_html
    assert '<iframe class="browser-interactive-frame"' in main_html
    assert 'x-if="$store.browserPage.isInteractiveSurface($el.parentElement)"' in main_html
    assert 'aria-label="Browser viewport"' in main_html
    assert 'title="Interactive Browser viewport"' not in main_html
    assert 'allow="clipboard-read; clipboard-write"' in main_html
    assert 'x-init="$store.browserPage.attachFrameCanvas($el)"' in main_html
    assert '<img class="browser-frame browser-frame-image"' in main_html
    assert "$store.browserPage.hasFrame()" in main_html
    assert "overflow: hidden;" in main_html
    assert "object-fit: contain;" in main_html
    assert "image-rendering: auto;" in main_html


def test_browser_viewer_frame_payload_supports_binary_slim_frames():
    payload = ws_browser_module.WsBrowser._frame_payload(
        {
            "image": SMALL_JPEG_10X10,
            "mime": "image/jpeg",
            "metadata": {"expectedWidth": 900, "expectedHeight": 600},
        },
        context_id="ctx",
        viewer_id="viewer",
        browser_id=1,
        sequence=3,
        binary_frames=True,
    )

    assert payload["encoding"] == "binary"
    assert payload["image"] == __import__("base64").b64decode(SMALL_JPEG_10X10)
    assert payload["width"] == 900
    assert payload["height"] == 600
    assert payload["seq"] == 3
    assert "browsers" not in payload
    assert "state" not in payload


def test_browser_viewer_frame_dimensions_reject_crops_but_allow_uniform_scaling():
    dimensions = ws_browser_module.WsBrowser._frame_dimensions

    assert dimensions(
        {
            "expectedWidth": 900,
            "expectedHeight": 600,
            "jpegWidth": 1800,
            "jpegHeight": 1200,
        }
    ) == {"width": 900, "height": 600}
    assert dimensions(
        {
            "expectedWidth": 900,
            "expectedHeight": 600,
            "jpegWidth": 900,
            "jpegHeight": 500,
        }
    ) == {"width": 900, "height": 500}


def test_browser_navigation_errors_stay_inside_native_browser_page():
    runtime = (
        PROJECT_ROOT / "plugins" / "_browser" / "helpers" / "runtime.py"
    ).read_text(encoding="utf-8")

    assert "Error as PlaywrightError" in runtime
    assert "except PlaywrightError as exc:" in runtime
    assert "Browser navigation showed a native error page" in runtime
    assert "await page.goto(url, wait_until=wait_until, timeout=30000)" in runtime
    assert "except (PlaywrightError, PlaywrightTimeoutError):" in runtime


def test_browser_annotate_mode_ui_and_prompt_hooks():
    panel_html = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-panel.html"
    ).read_text(encoding="utf-8")
    browser_store = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js"
    ).read_text(encoding="utf-8")

    assert "Annotate" in panel_html
    assert "Annotating" in panel_html
    assert "browser-annotation-layer" in panel_html
    assert "browser-annotation-tray" in panel_html
    assert "annotationTrayStyle()" in panel_html
    assert "startAnnotationTrayDrag($event)" in panel_html
    assert "Draft to chat" not in panel_html
    assert "Send now" not in panel_html
    assert 'class="browser-annotation-popover-close"' in panel_html
    assert panel_html.count('class="browser-annotation-mic mic-inactive"') == 2
    assert 'class="browser-annotation-send"' in panel_html
    assert 'name="arrow_forward"' in panel_html
    assert 'name="add_comment"' not in panel_html
    assert "data-whisper-microphone" in panel_html
    assert "syncAnnotationMicrophoneUI()" in panel_html
    assert "startAnnotationVoice(true)" in panel_html
    assert "@pointerdown.stop.prevent=\"$store.browserPage.startAnnotationSelection($event)\"" in panel_html
    assert "clearAnnotationHover()" in panel_html
    assert "@keydown.window=\"$store.browserPage.handleKeydown($event)\"" in panel_html
    assert "annotationComments: []" in browser_store
    assert "annotationHover: null" in browser_store
    assert "annotationTrayPosition: null" in browser_store
    assert "pendingAnnotations()" in browser_store
    assert "annotationBatchLabel()" in browser_store
    assert "updateAnnotationHover(event)" in browser_store
    assert "startAnnotationVoice(draftComment = false)" in browser_store
    assert "this.annotationDraftText = existing" in browser_store
    assert "options.sendImmediately" in browser_store
    assert "clampAnnotationTrayPosition" in browser_store
    assert '"browser_viewer_annotation"' in browser_store
    assert 'event?.key === "." && (event.metaKey || event.ctrlKey)' in browser_store
    assert "Browser annotations" in browser_store
    assert "Instruction:" in browser_store
    assert "Page ${pageIndex + 1}" in browser_store
    assert "Comment:" in browser_store
    assert "Coordinates:" in browser_store
    assert "Selector:" in browser_store
    assert "DOM:" in browser_store
    assert "value=\\\"[redacted]\\\"" in browser_store

    whisper_store = (
        PROJECT_ROOT / "plugins" / "_whisper_stt" / "webui" / "whisper-stt-store.js"
    ).read_text(encoding="utf-8")
    assert "finalTranscriptHandler" in whisper_store
    assert "deliverVoiceMessage(text)" in whisper_store
    assert '"[data-whisper-microphone], #microphone-button"' in whisper_store


def test_browser_visual_mode_bridges_clipboard_shortcuts():
    browser_store = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js"
    ).read_text(encoding="utf-8")
    runtime = (
        PROJECT_ROOT / "plugins" / "_browser" / "helpers" / "runtime.py"
    ).read_text(encoding="utf-8")
    ws_browser = (
        PROJECT_ROOT / "plugins" / "_browser" / "api" / "ws_browser.py"
    ).read_text(encoding="utf-8")

    assert 'import { copyToClipboard } from "/components/messages/action-buttons/simple-action-buttons.js";' in browser_store
    assert "BROWSER_VISUAL_SHORTCUT_KEYS" in browser_store
    assert "handleVisualBrowserShortcut(event)" in browser_store
    assert "visualBrowserStageForEvent(event)" in browser_store
    assert "isLocalEditableTarget(event?.target)" in browser_store
    assert 'return { action: "paste" };' in browser_store
    assert 'return { action: "copy" };' in browser_store
    assert 'return { action: "cut" };' in browser_store
    assert 'return { key: "Control+A" };' in browser_store
    assert 'return { key: shift ? "Control+Shift+Z" : "Control+Z" };' in browser_store
    assert 'input_type: "clipboard"' in browser_store
    assert "pasteHostClipboardToBrowser()" in browser_store
    assert "copyBrowserClipboardToHost" in browser_store
    assert "Browser paste needs clipboard permission in this tab." in browser_store

    assert "CLIPBOARD_BRIDGE_SCRIPT" in runtime
    assert "async def clipboard" in runtime
    assert "insertFromPaste" in runtime
    assert "deleteByCut" in runtime
    assert "keyboard.insert_text" in runtime
    assert 'input_type == "clipboard"' in ws_browser
    assert 'runtime.call(\n                    "clipboard"' in ws_browser


def test_browser_visual_mode_only_forwards_text_producing_alt_keys():
    browser_store = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-store.js"
    ).read_text(encoding="utf-8")
    start = browser_store.index("function isAltTextInput")
    end = browser_store.index("\n}\n", start) + 3
    helper = browser_store[start:end]
    script = helper + """
const check = (condition, message) => {
  if (!condition) throw new Error(message);
};
check(isAltTextInput({ key: "@", altKey: true, ctrlKey: true }, "Windows"), "AltGr text was blocked");
check(isAltTextInput({ key: "€", altKey: true, getModifierState: (name) => name === "AltGraph" }, "Linux"), "AltGraph text was blocked");
check(isAltTextInput({ key: "@", altKey: true }, "MacIntel"), "Option text was blocked");
check(!isAltTextInput({ key: "f", altKey: true }, "Windows"), "Windows Alt shortcut became text");
check(!isAltTextInput({ key: "d", altKey: true }, "Linux"), "Linux Alt shortcut became text");
check(!isAltTextInput({ key: "@", altKey: true, metaKey: true }, "MacIntel"), "Command shortcut became text");
"""

    subprocess.run(["node", "--input-type=module", "-e", script], check=True, text=True)


def test_browser_runtime_and_content_helper_expose_annotation_target():
    runtime = (
        PROJECT_ROOT / "plugins" / "_browser" / "helpers" / "runtime.py"
    ).read_text(encoding="utf-8")
    helper = (
        PROJECT_ROOT / "plugins" / "_browser" / "assets" / "browser-page-content.js"
    ).read_text(encoding="utf-8")
    dom_helper = (
        PROJECT_ROOT / "plugins" / "_browser" / "assets" / "browser-dom-helper.js"
    ).read_text(encoding="utf-8")

    assert "DOM_HELPER_PATH" in runtime
    assert "browser-dom-helper.js" in runtime
    assert "globalThis.__spaceBrowserDomHelper__?.captureDocument" in runtime
    assert "async def annotation_target" in runtime
    assert "globalThis.__spaceBrowserPageContent__.annotate(payload || null)" in runtime
    assert "function annotate(payload = null)" in helper
    assert "annotate," in helper
    assert "boundingBoxFor," in helper
    assert "pointFor," in helper
    assert "select(referenceId, valueOrValues)" in helper
    assert "setChecked(referenceId, checked)" in helper
    assert "fileInputFor," in helper
    assert "sanitizeAnnotationDom" in helper
    assert "password" in helper
    assert "__spaceBrowserDomHelper__" in dom_helper
    assert "captureDocument(payload)" in dom_helper
    assert "clickNode(frameChain, nodeId)" in dom_helper
    assert "requestChildFrameOperation" in dom_helper
    assert "data-space-browser-frame-chain" in dom_helper


def test_browser_content_helper_keeps_label_wrapped_controls_referenceable():
    helper = (
        PROJECT_ROOT / "plugins" / "_browser" / "assets" / "browser-page-content.js"
    ).read_text(encoding="utf-8")

    assert 'const VERSION = "13"' in helper
    assert "function patchOpenShadowDom" in helper
    assert "Element.prototype.attachShadow = patched" in helper
    assert "const REQUIRED_API_NAMES = Object.freeze([" in helper
    assert "requiredApis: REQUIRED_API_NAMES.slice()" in helper
    assert "ready()" in helper
    for api_name in ("click", "scroll", "submit", "type", "typeSubmit"):
        assert f'"{api_name}"' in helper
    assert "function renderControlLabelReferences" in helper
    assert "getLabelElementText(labelElement, element)" in helper
    assert "return renderControlLabelReferences(node, context);" in helper
    assert "return renderControlLabelReferences(element, context);" in helper
    assert "function isGlobalOrDelegatedEventBinding" in helper
    assert 'parts.includes("window")' in helper
    assert 'parts.includes("outside")' in helper
    assert 'actionStrategy: entry.helperBacked ? "frame_chain_ref" : "dom_ref"' in helper
    assert 'actionStrategy: "frame_chain_ref"' in helper
    assert "frameChain: Array.isArray(entry?.frameChain)" in helper


def test_browser_panel_exposes_agent_friendly_address_input():
    panel = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-panel.html"
    ).read_text(encoding="utf-8")

    assert 'class="browser-address-form" aria-label="Browser navigation"' in panel
    assert 'class="browser-address" aria-label="Browser address" name="browser_address"' in panel


def test_browser_panel_groups_mobile_toolbar_controls_above_address():
    panel = (
        PROJECT_ROOT / "plugins" / "_browser" / "webui" / "browser-panel.html"
    ).read_text(encoding="utf-8")

    toolbar_index = panel.index('<div class="browser-toolbar surface-toolbar">')
    nav_index = panel.index('<div class="browser-navigation">', toolbar_index)
    controls_index = panel.index('<div class="browser-session-controls surface-toolbar-group">', toolbar_index)
    address_index = panel.index('<form class="browser-address-form"', toolbar_index)

    assert nav_index < controls_index < address_index
    assert ".browser-panel {\n      --browser-chrome-surface:" in panel
    assert "container-type: inline-size;" in panel
    assert "@container (max-width: 460px)" in panel
    assert ".browser-toolbar {\n        grid-template-columns: auto minmax(0, 1fr) auto;" in panel
    assert '          "nav . controls"\n          "address address address";' in panel
    assert ".browser-session-controls {\n        width: auto;" in panel
    assert ".browser-address-form {\n        width: 100%;" in panel


def test_browser_runtime_requires_current_content_helper_for_modifier_clicks():
    runtime = (
        PROJECT_ROOT / "plugins" / "_browser" / "helpers" / "runtime.py"
    ).read_text(encoding="utf-8")

    assert "__spaceBrowserPageContent__?.ready?.()" in runtime
    assert "context.add_init_script" not in runtime
    assert "isolated_context=False" in runtime


@pytest.mark.anyio
async def test_browser_dom_helper_clicks_content_ref_inside_iframe():
    pytest.importorskip("patchright.async_api")
    from patchright.async_api import async_playwright

    browser_binary = get_playwright_binary()
    if not browser_binary:
        pytest.skip("Patchright Chromium binary is not installed")

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(
                executable_path=str(browser_binary),
                headless=True,
                args=["--no-sandbox"],
            )
        except Exception as exc:
            pytest.skip(f"Patchright Chromium could not launch: {exc}")

        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.set_content(
                """
                <html>
                  <body>
                    <iframe srcdoc="
                      <html>
                        <body>
                          <button id='inside' onclick=&quot;document.body.dataset.clicked = 'yes'; this.textContent = 'Clicked inside frame'&quot;>
                            Frame Launch
                          </button>
                        </body>
                      </html>
                    "></iframe>
                  </body>
                </html>
                """
            )
            core = _BrowserRuntimeCore("patchright-helper")
            await core._ensure_content_helper(page)

            captured = await page.evaluate(
                "(payload) => globalThis.__spaceBrowserPageContent__.capture(payload || null)",
                None,
            )
            document_content = str(captured.get("document") or "")
            match = re.search(r"\[button (\d+)\]\s*Frame Launch", document_content)
            assert match, document_content

            action = await page.evaluate(
                "(ref) => globalThis.__spaceBrowserPageContent__.click(ref)",
                match.group(1),
            )
            frame = next(frame for frame in page.frames if frame != page.main_frame)
            assert await frame.evaluate("() => document.body.dataset.clicked") == "yes"
            assert action["status"]["reacted"] is True
        finally:
            await browser.close()


@pytest.mark.anyio
async def test_browser_screencast_acknowledges_and_drops_stale_frames():
    first_image = SMALL_JPEG_10X10

    class FakeSession:
        def __init__(self):
            self.handlers = {}
            self.sent = []
            self.detached = False

        def on(self, event, handler):
            self.handlers[event] = handler

        async def send(self, method, params=None):
            self.sent.append((method, params or {}))

        async def detach(self):
            self.detached = True

    session = FakeSession()
    screencast = _BrowserScreencast(
        stream_id="stream",
        browser_id=7,
        session=session,
        mime="image/jpeg",
    )

    await screencast.start(
        quality=92,
        every_nth_frame=1,
        viewport={"width": 1118, "height": 662},
        capture_scale=2,
    )
    session.handlers["Page.screencastFrame"](
        {"data": first_image, "metadata": {"deviceWidth": 10}, "sessionId": 1}
    )
    session.handlers["Page.screencastFrame"](
        {"data": "second", "metadata": {"deviceWidth": 200}, "sessionId": 2}
    )
    await asyncio.sleep(0)

    frame = await screencast.next_frame(timeout=0.1)

    assert frame["browser_id"] == 7
    assert frame["image"] == "second"
    assert frame["metadata"]["deviceWidth"] == 200
    assert frame["metadata"]["expectedWidth"] == 1118
    assert frame["metadata"]["expectedHeight"] == 662
    metrics_calls = [
        params
        for method, params in session.sent
        if method == "Emulation.setDeviceMetricsOverride"
    ]
    visible_calls = [
        params
        for method, params in session.sent
        if method == "Emulation.setVisibleSize"
    ]
    assert metrics_calls == [
        {
            "width": 1118,
            "height": 662,
            "deviceScaleFactor": 1,
            "mobile": False,
            "dontSetVisibleSize": True,
        },
    ]
    assert visible_calls == [{"width": 1118, "height": 662}]
    start_index = next(
        index
        for index, (method, _params) in enumerate(session.sent)
        if method == "Page.startScreencast"
    )
    start_params = session.sent[start_index][1]
    assert start_params["quality"] == 92
    assert start_params["maxWidth"] == 2236
    assert start_params["maxHeight"] == 1324
    cdp_viewport_indices = [
        index
        for index, (method, _params) in enumerate(session.sent)
        if method.startswith("Emulation.")
    ]
    assert max(cdp_viewport_indices) < start_index
    assert ("Page.screencastFrameAck", {"sessionId": 1}) in session.sent
    assert ("Page.screencastFrameAck", {"sessionId": 2}) in session.sent

    await screencast.stop()

    assert ("Page.stopScreencast", {}) in session.sent
    assert session.detached is True


@pytest.mark.anyio
async def test_browser_screencast_acks_after_consumer_settles():
    class FakeSession:
        def __init__(self):
            self.handlers = {}
            self.sent = []

        def on(self, event, handler):
            self.handlers[event] = handler

        async def send(self, method, params=None):
            self.sent.append((method, params or {}))

        async def detach(self):
            pass

    session = FakeSession()
    delivered = []
    delivery = concurrent.futures.Future()
    screencast = _BrowserScreencast(
        stream_id="stream",
        browser_id=7,
        session=session,
        mime="image/jpeg",
    )
    screencast.frame_consumer = lambda frame: delivered.append(frame) or delivery

    await screencast.start(quality=92, every_nth_frame=1, viewport={"width": 640, "height": 480})
    session.handlers["Page.screencastFrame"](
        {"data": SMALL_JPEG_10X10, "metadata": {}, "sessionId": 21}
    )
    await asyncio.sleep(0)

    assert delivered
    assert ("Page.screencastFrameAck", {"sessionId": 21}) not in session.sent

    delivery.set_result(None)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert ("Page.screencastFrameAck", {"sessionId": 21}) in session.sent

    await screencast.stop()


@pytest.mark.anyio
async def test_browser_screencast_notifies_consumer_when_frame_task_stops_before_delivery():
    class FakeSession:
        def __init__(self):
            self.handlers = {}
            self.sent = []
            self.detached = False

        def on(self, event, handler):
            self.handlers[event] = handler

        async def send(self, method, params=None):
            self.sent.append((method, params or {}))

        async def detach(self):
            self.detached = True

    session = FakeSession()
    delivered = []
    stopped = []
    screencast = _BrowserScreencast(
        stream_id="stream",
        browser_id=7,
        session=session,
        mime="image/jpeg",
    )

    await screencast.start(quality=92, every_nth_frame=1, viewport={"width": 640, "height": 480})
    await screencast.attach_consumer(
        lambda frame: delivered.append(frame),
        lambda: stopped.append(True),
    )

    def fail_jpeg_probe(_data):
        raise RuntimeError("jpeg probe failed")

    screencast._jpeg_size = fail_jpeg_probe
    session.handlers["Page.screencastFrame"](
        {"data": SMALL_JPEG_10X10, "metadata": {}, "sessionId": 29}
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert delivered == []
    assert stopped == [True]
    assert screencast.stopped is True
    assert ("Page.screencastFrameAck", {"sessionId": 29}) in session.sent

    await screencast.stop()

    assert ("Page.stopScreencast", {}) in session.sent
    assert session.detached is True


@pytest.mark.anyio
async def test_browser_screencast_stop_notifies_consumer_once():
    class FakeSession:
        def __init__(self):
            self.handlers = {}
            self.sent = []

        def on(self, event, handler):
            self.handlers[event] = handler

        async def send(self, method, params=None):
            self.sent.append((method, params or {}))

        async def detach(self):
            pass

    session = FakeSession()
    stopped = []
    screencast = _BrowserScreencast(
        stream_id="stream",
        browser_id=7,
        session=session,
        mime="image/jpeg",
    )

    await screencast.start(quality=92, every_nth_frame=1, viewport={"width": 640, "height": 480})
    await screencast.attach_consumer(lambda frame: None, lambda: stopped.append(True))
    await screencast.stop()
    await screencast.stop()

    assert stopped == [True]
    assert ("Page.stopScreencast", {}) in session.sent


@pytest.mark.anyio
async def test_browser_screencast_attach_consumer_flushes_queued_frame():
    class FakeSession:
        def __init__(self):
            self.handlers = {}
            self.sent = []

        def on(self, event, handler):
            self.handlers[event] = handler

        async def send(self, method, params=None):
            self.sent.append((method, params or {}))

        async def detach(self):
            pass

    session = FakeSession()
    delivered = []
    delivery = concurrent.futures.Future()
    delivery.set_result(None)
    screencast = _BrowserScreencast(
        stream_id="stream",
        browser_id=7,
        session=session,
        mime="image/jpeg",
    )

    await screencast.start(quality=92, every_nth_frame=1, viewport={"width": 640, "height": 480})
    session.handlers["Page.screencastFrame"](
        {"data": SMALL_JPEG_10X10, "metadata": {}, "sessionId": 31}
    )
    await asyncio.sleep(0)

    await screencast.attach_consumer(lambda frame: delivered.append(frame) or delivery)

    assert delivered
    assert delivered[0]["image"] == SMALL_JPEG_10X10
    assert await screencast.pop_frame() is None

    await screencast.stop()


@pytest.mark.anyio
async def test_browser_screencast_passes_wrong_viewport_frames_to_frontend_validator():
    class FakeSession:
        def __init__(self):
            self.handlers = {}
            self.sent = []

        def on(self, event, handler):
            self.handlers[event] = handler

        async def send(self, method, params=None):
            self.sent.append((method, params or {}))

        async def detach(self):
            pass

    session = FakeSession()
    screencast = _BrowserScreencast(
        stream_id="stream",
        browser_id=7,
        session=session,
        mime="image/jpeg",
    )

    await screencast.start(quality=92, every_nth_frame=1, viewport={"width": 1118, "height": 662})
    for session_id in range(1, 14):
        session.handlers["Page.screencastFrame"](
            {"data": SMALL_JPEG_10X10, "metadata": {}, "sessionId": session_id}
        )
    await asyncio.sleep(0)

    frame = await screencast.pop_frame()

    assert frame is not None
    assert frame["image"] == SMALL_JPEG_10X10
    assert frame["metadata"]["jpegWidth"] == 10
    assert frame["metadata"]["jpegHeight"] == 10
    assert frame["metadata"]["expectedWidth"] == 1118
    assert frame["metadata"]["expectedHeight"] == 662
    assert ("Page.screencastFrameAck", {"sessionId": 13}) in session.sent

    await screencast.stop()


def test_browser_docker_installs_full_chromium_to_tmp_cache():
    script = (
        PROJECT_ROOT / "docker" / "run" / "fs" / "ins" / "install_playwright.sh"
    ).read_text(encoding="utf-8")
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "PLAYWRIGHT_BROWSERS_PATH=/a0/tmp/playwright" in script
    assert "patchright install chromium --no-shell" in script
    assert "playwright install chromium" not in script
    assert "uv pip install" not in script
    assert "patchright==1.61.2" in requirements
    assert "--only-shell" not in script

    runtime = (PROJECT_ROOT / "plugins" / "_browser" / "helpers" / "runtime.py").read_text(
        encoding="utf-8"
    )
    assert "from patchright.async_api import async_playwright" in runtime
    assert "from playwright.async_api import async_playwright" not in runtime
    assert runtime.index("hooks.prepare_playwright_cache()") < runtime.index(
        "from patchright.async_api import async_playwright"
    )
    install_additional = (
        PROJECT_ROOT / "docker" / "run" / "fs" / "ins" / "install_additional.sh"
    ).read_text(encoding="utf-8")
    assert '"headless": not bool(browser_display)' in runtime
    assert 'launch_kwargs["env"] = {**os.environ, "DISPLAY": browser_display}' in runtime
    assert 'launch_kwargs["no_viewport"] = True' in runtime
    assert '"windowState": "fullscreen"' not in runtime
    assert "self.interactive_view.ensure_display()" in runtime
    assert "  xvfb \\" in install_additional
    assert "  xdotool \\" in install_additional
    assert "  xclip \\" in install_additional


def test_browser_docker_pins_python_313_compatible_desktop_packages():
    install_additional = (
        PROJECT_ROOT / "docker" / "run" / "fs" / "ins" / "install_additional.sh"
    ).read_text(encoding="utf-8")

    assert 'https://snapshot.debian.org/archive/debian/20260624T000000Z/' in install_additional
    assert 'Dir::Etc::sourceparts=-' in install_additional
    assert 'LIBREOFFICE_VERSION="4:26.2.4.2-1"' in install_additional
    assert 'XPRA_VERSION="6.5.2-r0-1"' in install_additional
    assert 'XPRA_HTML5_VERSION="19-r1-1"' in install_additional
    assert 'XPRA_HTML5_VERSION="21-r1-1"' in install_additional
    assert '"python3-uno=$LIBREOFFICE_VERSION"' in install_additional
    from plugins._desktop import hooks as desktop_hooks
    assert f'ATK_VERSION="{desktop_hooks.ATK_VERSION}"' in install_additional
    for package in desktop_hooks.ATK_RUNTIME_PACKAGES:
        assert f'"{package}=$ATK_VERSION"' in install_additional
    assert '  "${ATK_PACKAGES[@]}" \\' in install_additional
    assert "PYTHON_VERSION" not in install_additional
    assert '--allow-downgrades' in install_additional
    assert "  gir1.2-gtk-3.0 \\" in install_additional
    assert '"xpra-client=$XPRA_VERSION"' in install_additional
    assert '"xpra-client-gtk3=$XPRA_VERSION"' in install_additional
    assert '"xpra-server=$XPRA_VERSION"' in install_additional
    assert '"xpra-html5=$XPRA_HTML5_VERSION"' in install_additional
    assert "apt-get download" not in install_additional
    assert install_additional.index('cat >/etc/apt/a0-desktop.list') < install_additional.index('apt-get "${APT_OPTIONS[@]}" update')
    assert "https://xpra.org/beta" not in install_additional


def test_browser_startup_migration_prepares_current_playwright_binary():
    extension = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "python"
        / "startup_migration"
        / "_20_browser_playwright_cache.py"
    ).read_text(encoding="utf-8")

    assert "class BrowserPlaywrightCacheMigration(Extension)" in extension
    assert "virtual_desktop_routes.install_route_hooks()" in extension
    assert "hooks.prepare_playwright_cache()" in extension
    assert "PrintStyle.warning" in extension




def test_browser_interactive_view_keyboard_options(monkeypatch):
    import plugins._browser.helpers.interactive_view as iv_module

    view = BrowserInteractiveView("ctx-kb")

    # no layout -> no xpra keyboard args
    monkeypatch.setattr(
        iv_module, "keyboard_options", lambda: {"layout": "", "variant": ""}
    )
    assert view._keyboard_xpra_args() == []

    # layout + variant -> pinned server layout, sync disabled
    monkeypatch.setattr(
        iv_module,
        "keyboard_options",
        lambda: {"layout": "de", "variant": "mac"},
    )
    assert view._keyboard_xpra_args() == [
        "--keyboard-sync=no",
        "--keyboard-layout", "de",
        "--keyboard-variant", "mac",
    ]


def test_browser_interactive_view_applies_keyboard_layout(monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(browser_interactive_view_module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        browser_interactive_view_module.shutil,
        "which",
        lambda name: "/usr/bin/setxkbmap" if name == "setxkbmap" else None,
    )
    monkeypatch.setattr(
        browser_interactive_view_module,
        "keyboard_options",
        lambda: {"layout": "de", "variant": "mac"},
    )

    view = BrowserInteractiveView("ctx-kb-apply")
    view.display = 42
    view._apply_keyboard_layout()

    assert commands == [["/usr/bin/setxkbmap", "-display", ":42", "-layout", "de", "-variant", "mac"]]

    # no configured layout -> no setxkbmap call
    monkeypatch.setattr(
        browser_interactive_view_module,
        "keyboard_options",
        lambda: {"layout": "", "variant": ""},
    )
    view._apply_keyboard_layout()
    assert len(commands) == 1


def test_browser_xpra_uses_websocket_transport_and_bounded_service_waits(monkeypatch, tmp_path):
    view = BrowserInteractiveView("ctx-startup")
    view.state_dir = tmp_path
    view.display = 71
    commands = []
    monkeypatch.setenv("XPRA_SYSTEM_DBUS_TIMEOUT", "7")
    monkeypatch.delenv("XPRA_SYSTEM_CUPS_TIMEOUT", raising=False)
    monkeypatch.setattr(view, "_free_port", lambda: 44001)
    monkeypatch.setattr(view, "_keyboard_xpra_args", lambda: [])
    monkeypatch.setattr(view, "_wait_for_port", lambda *_: None)
    monkeypatch.setattr(
        browser_interactive_view_module.subprocess, "Popen",
        lambda command, **kwargs: commands.append((command, kwargs)),
    )

    view._start_xpra("xpra")

    command, kwargs = commands[0]
    assert "--mmap=no" in command
    assert "--bind-tcp=127.0.0.1:44001" in command
    assert kwargs["env"]["XPRA_SYSTEM_DBUS_TIMEOUT"] == "7"
    assert kwargs["env"]["XPRA_SYSTEM_CUPS_TIMEOUT"] == "1"


def test_browser_interactive_views_use_isolated_loopback_sessions(monkeypatch, tmp_path):
    class FakeProcess:
        def __init__(self):
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    next_display = iter((71, 72))
    next_port = iter((44001, 44002))

    def fake_ensure_display(view):
        view.display = next(next_display)
        view._xvfb = FakeProcess()
        return view.display_name

    def fake_resize(view, width, height):
        view.width, view.height = virtual_desktop.normalize_size(width, height)
        return {"ok": True, "width": view.width, "height": view.height}

    def fake_start_xpra(view, xpra):
        assert xpra == "/usr/bin/xpra"
        view.port = next(next_port)
        view._xpra = FakeProcess()

    monkeypatch.setattr(
        browser_interactive_view_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    monkeypatch.setattr(BrowserInteractiveView, "ensure_display", fake_ensure_display)
    monkeypatch.setattr(BrowserInteractiveView, "resize", fake_resize)
    monkeypatch.setattr(BrowserInteractiveView, "_start_xpra", fake_start_xpra)
    monkeypatch.setattr(
        browser_interactive_view_module,
        "collect_status",
        lambda: {
            "available": True,
            "missing": [],
            "binaries": {"xpra": "/usr/bin/xpra"},
            "xpra_html_root": "/usr/share/xpra/www",
        },
    )

    views = [BrowserInteractiveView("ctx-a"), BrowserInteractiveView("ctx-b")]
    try:
        viewers = [view.ensure_viewer(1200, 700) for view in views]

        assert views[0].token != views[1].token
        assert views[0].display != views[1].display
        assert all(viewer["available"] for viewer in viewers)
        for view, viewer in zip(views, viewers, strict=True):
            endpoint = virtual_desktop.proxy_for_token(view.token)
            assert endpoint is not None
            assert endpoint.host == "127.0.0.1"
            assert endpoint.owner == "browser"
            assert endpoint.port == view.port
            assert viewer["token"] == view.token
            assert "file_transfer=false" in viewer["url"]
            assert "printing=false" in viewer["url"]
    finally:
        for view in views:
            view.close()

    assert all(virtual_desktop.proxy_for_token(view.token) is None for view in views)


@pytest.mark.anyio
@pytest.mark.parametrize("width,height", [(1200, 700), (0, 0)])
async def test_browser_interactive_viewer_reuses_the_automated_page(width, height):
    class FakePage:
        viewport_size = {"width": 1800, "height": 1050}

    class FakeInteractiveView:
        def __init__(self):
            self.ensure_calls = []

        def ensure_viewer(self, width, height):
            self.ensure_calls.append((width, height))
            return {
                "available": True,
                "token": "browser-token",
                "url": "/desktop/session/browser-token/",
                "width": width or 1200,
                "height": height or 700,
            }

    page = FakePage()
    interactive_view = FakeInteractiveView()
    viewport_calls = []
    stopped = []
    core = _BrowserRuntimeCore("ctx")
    core.context = object()
    core.pages[7] = BrowserPage(id=7, page=page)
    core.interactive_view = interactive_view

    async def ensure_started():
        return None

    async def stop_screencasts(browser_id):
        stopped.append(browser_id)

    async def set_viewport(browser_id, width, height, **kwargs):
        viewport_calls.append((browser_id, width, height, kwargs))
        return {"state": {"id": browser_id}, "viewport": {"width": width, "height": height}}

    core.ensure_started = ensure_started
    core._stop_screencasts_for_browser = stop_screencasts
    core.set_viewport = set_viewport

    result = await core.interactive_viewer(7, width=width, height=height)

    assert core.pages[7].page is page
    assert interactive_view.ensure_calls == [(width, height)]
    assert stopped == [7]
    assert viewport_calls == [(7, 1200, 700, {"resize_interactive": True})]
    assert core.last_interacted_browser_id == 7
    assert result["url"] == "/desktop/session/browser-token/"


@pytest.mark.anyio
async def test_browser_interactive_window_clips_chrome_without_fullscreen():
    commands = []

    class FakeSession:
        async def send(self, method, params=None):
            commands.append((method, params))
            if method == "Browser.getWindowForTarget":
                return {"windowId": 7}
            if method == "Browser.getWindowBounds":
                return {
                    "bounds": {
                        "windowState": "normal",
                        "left": 0,
                        "top": 0,
                        "width": 1024,
                        "height": 768,
                    }
                }
            return {}

        async def detach(self):
            commands.append(("detach", None))

    class FakeContext:
        async def new_cdp_session(self, page):
            assert page is fake_page
            return FakeSession()

    class FakeInteractiveView:
        display = 0
        width = 1200
        height = 700

    class FakePage:
        async def evaluate(self, script, **kwargs):
            commands.append(("evaluate", script))
            return 87

    fake_page = FakePage()
    core = _BrowserRuntimeCore("ctx")
    core.context = FakeContext()
    core.interactive_view = FakeInteractiveView()

    await core._fit_browser_window(fake_page)
    core.interactive_view.width = 1280
    core.interactive_view.height = 720
    await core._fit_browser_window(fake_page)
    await core._reset_browser_window_session()

    assert commands == [
        ("Browser.getWindowForTarget", None),
        ("Browser.getWindowBounds", {"windowId": 7}),
        (
            "evaluate",
            "() => Math.max(0, globalThis.outerHeight - globalThis.innerHeight)",
        ),
        (
            "Browser.setWindowBounds",
            {
                "windowId": 7,
                "bounds": {
                    "windowState": "normal",
                    "left": 0,
                    "top": -87,
                    "width": 1200,
                    "height": 787,
                },
            },
        ),
        (
            "Browser.setWindowBounds",
            {
                "windowId": 7,
                "bounds": {
                    "windowState": "normal",
                    "left": 0,
                    "top": -87,
                    "width": 1280,
                    "height": 807,
                },
            },
        ),
        ("detach", None),
    ]


@pytest.mark.anyio
async def test_browser_viewer_falls_back_when_interactive_runtime_is_unavailable():
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            return {"available": False, "error": "xpra unavailable"}

    handler = ws_browser_module.WsBrowser(SimpleNamespace(), threading.RLock(), manager=None)
    transport, viewer = await handler._effective_viewer(
        FakeRuntime(),
        7,
        {
            "viewer_transport": "interactive",
            "viewport_width": 1200,
            "viewport_height": 700,
        },
    )

    assert transport == ws_browser_module.VIEWER_TRANSPORT_SCREENCAST
    assert viewer == {"available": False, "error": "xpra unavailable"}
    assert calls == [("interactive_viewer", (7,), {"width": 1200, "height": 700})]


def test_browser_runtime_removes_stale_profile_singletons(monkeypatch, tmp_path):
    monkeypatch.setattr(
        browser_runtime_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    core = _BrowserRuntimeCore("stale-profile")
    core.profile_dir.mkdir(parents=True)

    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        (core.profile_dir / name).symlink_to("missing-host-999999")

    core._release_orphaned_profile_singleton()

    assert not any(
        (core.profile_dir / name).exists() or (core.profile_dir / name).is_symlink()
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket")
    )


@pytest.mark.anyio
async def test_browser_first_open_reuses_headful_bootstrap_page(monkeypatch):
    class BootstrapPage:
        url = "about:blank"

        @staticmethod
        def is_closed():
            return False

    page = BootstrapPage()

    class Context:
        pages = [page]

        @staticmethod
        async def new_page():
            raise AssertionError("The first headful tab must reuse Chrome's bootstrap page")

    core = _BrowserRuntimeCore("headful")
    core.context = Context()
    core._bootstrap_page = page

    async def register(registered_page, context_id=None):
        assert registered_page is page
        assert context_id == "headful"
        browser_page = BrowserPage(id=1, page=registered_page, context_id=context_id or "")
        core.pages[1] = browser_page
        return browser_page

    async def settle(_page, short=False):
        return None

    async def state(browser_id):
        return {"id": browser_id, "currentUrl": "about:blank"}

    core._register_page = register
    core._settle = settle
    core._state = state
    monkeypatch.setattr(
        browser_runtime_module,
        "get_browser_config",
        lambda: {"default_homepage": "about:blank", "max_open_tabs": 8},
    )

    result = await core.open()

    assert result == {"id": 1, "state": {"id": 1, "currentUrl": "about:blank"}}
    assert core._bootstrap_page is None


@pytest.mark.anyio
async def test_browser_runtime_restarts_when_cached_context_is_stale():
    starts = []
    stopped = []

    class StaleContext:
        @property
        def pages(self):
            raise RuntimeError("Target page, context or browser has been closed")

    class LiveContext:
        pages = []

    class FakePlaywright:
        async def stop(self):
            stopped.append(True)

    core = _BrowserRuntimeCore("ctx")
    core.context = StaleContext()
    core.playwright = FakePlaywright()
    core.pages[4] = browser_runtime_module.BrowserPage(id=4, page=object())
    core.last_interacted_browser_id = 4

    async def fake_start():
        starts.append(True)
        core.context = LiveContext()

    core._start = fake_start

    await core.ensure_started()

    assert starts == [True]
    assert stopped == [True]
    assert isinstance(core.context, LiveContext)
    assert core.pages == {}
    assert core.last_interacted_browser_id is None


def test_browser_runtime_context_close_event_clears_cached_state():
    core = _BrowserRuntimeCore("ctx")
    core.context = object()
    core.pages[4] = browser_runtime_module.BrowserPage(id=4, page=object())
    core.last_interacted_browser_id = 4

    core._on_context_closed()

    assert core.context is None
    assert core.pages == {}
    assert core.last_interacted_browser_id is None


def test_browser_save_plugin_config_restarts_runtimes_on_change(monkeypatch):
    restarted = []

    monkeypatch.setattr(
        browser_hooks_module,
        "_load_saved_browser_config",
        lambda project_name="", agent_profile="": {
            "extension_paths": [],
            "proxy_server": "",
        },
    )
    monkeypatch.setattr(
        browser_hooks_module,
        "close_all_runtimes_sync",
        lambda: restarted.append(True),
    )

    result = browser_hooks_module.save_plugin_config(
        {
            "extension_paths": [],
            "proxy_server": "http://proxy.example:3128",
        },
        project_name="",
        agent_profile="",
    )

    assert result["proxy_server"] == "http://proxy.example:3128"
    assert result["model_preset"] == ""
    assert restarted == [True]


def test_browser_save_plugin_config_does_not_restart_runtimes_for_preset_only(monkeypatch):
    restarted = []

    monkeypatch.setattr(
        browser_hooks_module,
        "_load_saved_browser_config",
        lambda project_name="", agent_profile="": {
            "extension_paths": [],
            "model_preset": "",
        },
    )
    monkeypatch.setattr(
        browser_hooks_module,
        "close_all_runtimes_sync",
        lambda: restarted.append(True),
    )

    result = browser_hooks_module.save_plugin_config(
        {
            "extension_paths": [],
            "model_preset": "Research",
        },
        project_name="",
        agent_profile="",
    )

    assert result["model_preset"] == "Research"
    assert restarted == []


def test_browser_save_plugin_config_does_not_restart_runtimes_for_viewer_settings(monkeypatch):
    restarted = []

    monkeypatch.setattr(
        browser_hooks_module,
        "_load_saved_browser_config",
        lambda project_name="", agent_profile="": {
            "extension_paths": [],
            "browser_tab_scope": "per_context",
            "max_open_tabs": 32,
        },
    )
    monkeypatch.setattr(
        browser_hooks_module,
        "close_all_runtimes_sync",
        lambda: restarted.append(True),
    )

    result = browser_hooks_module.save_plugin_config(
        {
            "extension_paths": [],
            "browser_tab_scope": "shared",
            "max_open_tabs": 12,
        },
        project_name="",
        agent_profile="",
    )

    assert result["browser_tab_scope"] == "shared"
    assert result["max_open_tabs"] == 12
    assert restarted == []


@pytest.mark.anyio
async def test_browser_tool_dispatches_direct_actions(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args):
            calls.append((method, args))
            if method == "content":
                return {"document": "[link 1] Example"}
            return {"ok": True, "method": method, "args": args}

    async def fake_get_runtime(context_id, create=True, agent=None):
        del create, agent
        assert context_id == "ctx"
        return FakeRuntime()

    monkeypatch.setattr(browser_tool_module, "get_runtime", fake_get_runtime)
    agent = SimpleNamespace(context=SimpleNamespace(id="ctx"))
    tool = browser_tool_module.Browser(
        agent=agent,
        name="browser",
        method=None,
        args={},
        message="",
        loop_data=None,
    )

    response = await tool.execute(action="content", browser_id=1)

    assert response.message == "[link 1] Example"
    assert calls == [("content", (1, None))]


@pytest.mark.anyio
async def test_browser_tool_dispatches_v1_agent_actions(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            return {"ok": True, "method": method, "args": args, "kwargs": kwargs}

    async def fake_get_runtime(context_id, create=True, agent=None):
        del create, agent
        assert context_id == "ctx"
        return FakeRuntime()

    monkeypatch.setattr(browser_tool_module, "get_runtime", fake_get_runtime)
    agent = SimpleNamespace(context=SimpleNamespace(id="ctx"))

    async def execute(**kwargs):
        tool = browser_tool_module.Browser(
            agent=agent,
            name="browser",
            method=kwargs.pop("_method", None),
            args={},
            message="",
            loop_data=None,
        )
        response = await tool.execute(**kwargs)
        assert response.break_loop is False

    await execute(action="screenshot", browser_id=1, quality=91, full_page=True, path="/tmp/a.jpg")
    await execute(action="hover", browser_id=1, ref=2, offset_x=3, offset_y=4)
    await execute(action="double_click", browser_id=1, x=10, y=20, button="left", modifiers=["Shift"])
    await execute(action="right_click", browser_id=1, ref=3, modifiers="Control")
    await execute(action="drag", browser_id=1, ref=4, target_ref=5, target_offset_x=6, target_offset_y=7)
    await execute(action="wheel", browser_id=1, x=8, y=9, delta_x=1, delta_y=2)
    await execute(action="keyboard", browser_id=1, key="Enter")
    await execute(_method="clipboard", action="paste", browser_id=1, text="hello")
    await execute(action="copy", browser_id=1)
    await execute(action="set_viewport", browser_id=1, width=1280, height=720)
    await execute(action="select_option", browser_id=1, ref=6, value="CA")
    await execute(action="set_checked", browser_id=1, ref=7, checked=False)
    await execute(action="upload_file", browser_id=1, ref=8, paths=["/tmp/a.txt"])
    await execute(action="key_chord", browser_id=1, keys="CTRL+A")
    await execute(action="click", browser_id=1, x=10, y=20)
    await execute(action="type", browser_id=1, text="agent-zero.ai")

    assert calls == [
        ("screenshot_file", (1,), {"quality": 91, "full_page": True, "path": "/tmp/a.jpg"}),
        ("hover", (1,), {"ref": 2, "x": 0.0, "y": 0.0, "offset_x": 3, "offset_y": 4}),
        (
            "double_click",
            (1,),
            {
                "ref": None,
                "x": 10,
                "y": 20,
                "button": "left",
                "modifiers": ["Shift"],
                "offset_x": 0.0,
                "offset_y": 0.0,
            },
        ),
        (
            "right_click",
            (1,),
            {
                "ref": 3,
                "x": 0.0,
                "y": 0.0,
                "modifiers": ["Control"],
                "offset_x": 0.0,
                "offset_y": 0.0,
            },
        ),
        (
            "drag",
            (1,),
            {
                "ref": 4,
                "target_ref": 5,
                "x": 0.0,
                "y": 0.0,
                "to_x": 0.0,
                "to_y": 0.0,
                "offset_x": 0.0,
                "offset_y": 0.0,
                "target_offset_x": 6,
                "target_offset_y": 7,
            },
        ),
        ("wheel", (1, 8, 9, 1, 2), {}),
        ("keyboard", (1,), {"key": "Enter", "text": ""}),
        ("clipboard", (1,), {"action": "paste", "text": "hello"}),
        ("clipboard", (1,), {"action": "copy", "text": ""}),
        ("set_viewport", (1, 1280, 720), {}),
        ("select_option", (1, 6), {"value": "CA", "values": None}),
        ("set_checked", (1, 7), {"checked": False}),
        ("upload_file", (1, 8), {"path": "", "paths": ["/tmp/a.txt"]}),
        ("key_chord", (1, ["Control", "A"]), {}),
        ("mouse", (1, "click", 10, 20), {"button": "left", "modifiers": None}),
        ("keyboard", (1,), {"key": "", "text": "agent-zero.ai"}),
    ]


@pytest.mark.anyio
async def test_browser_tool_resolves_selector_for_reference_actions(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            if method == "content":
                return {"input.browser-address": "[input text 31] Browser address"}
            return {"ok": True, "method": method, "args": args, "kwargs": kwargs}

    async def fake_get_runtime(context_id, create=True, agent=None):
        del create, agent
        assert context_id == "ctx"
        return FakeRuntime()

    monkeypatch.setattr(browser_tool_module, "get_runtime", fake_get_runtime)
    tool = browser_tool_module.Browser(
        agent=SimpleNamespace(context=SimpleNamespace(id="ctx")),
        name="browser",
        method=None,
        args={},
        message="",
        loop_data=None,
    )

    response = await tool.execute(
        action="type_submit",
        browser_id=1,
        selector="input.browser-address",
        text="agent-zero.ai",
    )

    assert response.break_loop is False
    assert calls == [
        ("content", (1, {"selector": "input.browser-address"}), {}),
        ("type_submit", (1, "31", "agent-zero.ai"), {}),
    ]


@pytest.mark.anyio
async def test_browser_runtime_multi_accepts_human_shaped_input_calls():
    calls = []
    core = _BrowserRuntimeCore("ctx")

    async def fake_mouse(browser_id, event_type, x, y, *, button="left", modifiers=None):
        calls.append(("mouse", browser_id, event_type, x, y, button, modifiers))
        return {"ok": True}

    async def fake_keyboard(browser_id, *, key="", text=""):
        calls.append(("keyboard", browser_id, key, text))
        return {"ok": True}

    async def fake_key_chord(browser_id, keys):
        calls.append(("key_chord", browser_id, keys))
        return {"ok": True}

    core.mouse = fake_mouse
    core.keyboard = fake_keyboard
    core.key_chord = fake_key_chord

    assert await core._dispatch_call({"action": "click", "browser_id": 1, "x": 10, "y": 20}) == {"ok": True}
    assert await core._dispatch_call({"action": "type", "browser_id": 1, "text": "agent-zero.ai"}) == {"ok": True}
    assert await core._dispatch_call({"action": "key_chord", "browser_id": 1, "keys": "CTRL+A"}) == {"ok": True}

    assert calls == [
        ("mouse", 1, "click", 10.0, 20.0, "left", None),
        ("keyboard", 1, "", "agent-zero.ai"),
        ("key_chord", 1, ["Control", "A"]),
    ]


@pytest.mark.anyio
async def test_browser_tool_records_static_history_screenshot(monkeypatch, tmp_path):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            if method == "open":
                return {
                    "id": 1,
                    "state": {
                        "id": 1,
                        "context_id": "browser-context",
                        "currentUrl": "https://example.com/",
                        "title": "Example Domain",
                    },
                }
            if method == "screenshot_file":
                return {
                    "browser_id": args[0],
                    "ephemeral": True,
                    "ephemeral_ref": "a0-ephemeral-image://fake",
                    "mime": "image/jpeg",
                    "state": {"id": args[0], "context_id": "browser-context"},
                }
            raise AssertionError(method)

    async def fake_get_runtime(context_id, create=True, agent=None):
        del create, agent
        assert context_id == "chat"
        return FakeRuntime()

    class FakeLog:
        id = "tool-log-id"

        def __init__(self):
            self.updates = []

        def update(self, **kwargs):
            self.updates.append(kwargs)

    monkeypatch.setattr(browser_tool_module, "get_runtime", fake_get_runtime)
    monkeypatch.setitem(
        sys.modules,
        "helpers.persist_chat",
        SimpleNamespace(
            get_chat_folder_path=lambda context_id: str(tmp_path / "usr" / "chats" / context_id)
        ),
    )

    log = FakeLog()
    tool = browser_tool_module.Browser(
        agent=SimpleNamespace(context=SimpleNamespace(id="chat")),
        name="browser",
        method=None,
        args={"action": "open", "url": "https://example.com"},
        message="",
        loop_data=None,
    )
    tool.log = log

    response = await tool.execute(action="open", url="https://example.com")

    assert response.break_loop is False
    assert calls[0] == ("open", ("https://example.com",), {})
    assert calls[1][0] == "screenshot_file"
    assert calls[1][1] == (1,)
    assert calls[1][2]["quality"] == browser_tool_module.HISTORY_SCREENSHOT_QUALITY
    assert calls[1][2]["full_page"] is False
    assert calls[1][2]["path"] == ""
    assert "Screenshot" not in log.updates[-1]
    assert log.updates[-1]["browser_snapshot"]["browser_id"] == 1
    assert log.updates[-1]["browser_snapshot"]["context_id"] == "chat"
    assert log.updates[-1]["browser_snapshot"]["browser_context_id"] == "browser-context"
    assert log.updates[-1]["browser_snapshot"]["ephemeral"] is True
    assert log.updates[-1]["browser_snapshot"]["ephemeral_ref"] == "a0-ephemeral-image://fake"


@pytest.mark.anyio
async def test_browser_multi_dispatch_accepts_v1_actions():
    calls = []
    core = _BrowserRuntimeCore("ctx")

    async def record(method):
        async def inner(*args, **kwargs):
            calls.append((method, args, kwargs))
            return {"method": method}
        return inner

    for method in (
        "screenshot_file",
        "hover",
        "double_click",
        "right_click",
        "drag",
        "wheel",
        "keyboard",
        "clipboard",
        "set_viewport",
        "select_option",
        "set_checked",
        "upload_file",
    ):
        setattr(core, method, await record(method))

    results = await core.multi(
        [
            {"action": "screenshot", "browser_id": 1, "quality": 5, "full_page": True},
            {"action": "hover", "browser_id": 1, "ref": 2},
            {"action": "double_click", "browser_id": 1, "x": 1, "y": 2},
            {"action": "right_click", "browser_id": 1, "ref": 3},
            {"action": "drag", "browser_id": 1, "ref": 4, "target_ref": 5},
            {"action": "wheel", "browser_id": 1, "delta_y": 100},
            {"action": "keyboard", "browser_id": 1, "key": "Enter"},
            {"action": "paste", "browser_id": 1, "text": "x"},
            {"action": "set_viewport", "browser_id": 1, "width": 640, "height": 480},
            {"action": "select_option", "browser_id": 1, "ref": 6, "values": ["a", "b"]},
            {"action": "set_checked", "browser_id": 1, "ref": 7, "checked": False},
            {"action": "upload_file", "browser_id": 1, "ref": 8, "path": "/tmp/file.txt"},
        ]
    )

    assert all(result["ok"] for result in results)
    assert [call[0] for call in calls] == [
        "screenshot_file",
        "hover",
        "double_click",
        "right_click",
        "drag",
        "wheel",
        "keyboard",
        "clipboard",
        "set_viewport",
        "select_option",
        "set_checked",
        "upload_file",
    ]


@pytest.mark.anyio
async def test_browser_viewer_subscribe_unregisters_stream(monkeypatch):
    class FakeRuntime:
        def __init__(self) -> None:
            self.opened = False

        async def call(self, method, *args):
            if method == "list":
                if self.opened:
                    return {
                        "browsers": [{"id": 1, "currentUrl": "about:blank", "title": ""}],
                        "last_interacted_browser_id": 1,
                    }
                return {"browsers": [], "last_interacted_browser_id": None}
            if method == "open":
                self.opened = True
                return {"id": 1, "state": {"id": 1, "currentUrl": "about:blank"}}
            raise AssertionError(method)

    fake_runtime = FakeRuntime()

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is False
        return fake_runtime

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "per_context"})
    monkeypatch.setattr(
        ws_browser_module.AgentContext,
        "get",
        staticmethod(lambda context_id: SimpleNamespace(id=context_id)),
    )

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_subscribe",
        {"context_id": "ctx", "correlationId": "c1"},
        "sid-1",
    )

    assert result["context_id"] == "ctx"
    assert result["active_browser_id"] is None
    assert fake_runtime.opened is False
    assert ("sid-1", "ctx") in ws_browser_module.WsBrowser._streams

    await handler.on_disconnect("sid-1")

    assert ("sid-1", "ctx") not in ws_browser_module.WsBrowser._streams


@pytest.mark.anyio
async def test_browser_viewer_subscribe_can_create_blank_tab_when_requested(monkeypatch):
    class FakeRuntime:
        def __init__(self) -> None:
            self.opened = False

        async def call(self, method, *args, **kwargs):
            if method == "list":
                if self.opened:
                    return {
                        "browsers": [{"id": 1, "currentUrl": "about:blank", "title": ""}],
                        "last_interacted_browser_id": 1,
                    }
                return {"browsers": [], "last_interacted_browser_id": None}
            if method == "open":
                assert kwargs == {"wait_until": "commit"}
                self.opened = True
                return {"id": 1, "state": {"id": 1, "currentUrl": "about:blank"}}
            raise AssertionError(method)

    fake_runtime = FakeRuntime()

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is True
        return fake_runtime

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "per_context"})
    monkeypatch.setattr(
        ws_browser_module.AgentContext,
        "get",
        staticmethod(lambda context_id: SimpleNamespace(id=context_id)),
    )

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_subscribe",
        {"context_id": "ctx", "create_browser": True},
        "sid-create",
    )

    assert result["active_browser_id"] == 1
    assert fake_runtime.opened is True

    await handler.on_disconnect("sid-create")


@pytest.mark.anyio
async def test_browser_viewer_subscribe_returns_initial_snapshot(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            if method == "list":
                return {
                    "browsers": [{"id": 1, "context_id": "ctx", "currentUrl": "https://example.com/"}],
                    "last_interacted_browser_id": 1,
                }
            if method == "set_viewport":
                return {"state": {"id": args[0], "currentUrl": "https://example.com/"}}
            if method == "screenshot":
                return {
                    "browser_id": args[0],
                    "mime": "image/jpeg",
                    "image": "jpeg-data",
                    "state": {"id": args[0], "context_id": "ctx", "currentUrl": "https://example.com/"},
                }
            raise AssertionError(method)

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is False
        return FakeRuntime()

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "per_context"})
    monkeypatch.setattr(
        ws_browser_module.AgentContext,
        "get",
        staticmethod(lambda context_id: SimpleNamespace(id=context_id)),
    )

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_subscribe",
        {
            "context_id": "ctx",
            "browser_id": 1,
            "viewport_width": 900,
            "viewport_height": 600,
        },
        "sid-snapshot",
    )

    assert result["active_browser_id"] == 1
    assert result["snapshot"]["image"] == "jpeg-data"
    assert result["browsers"] == [{"id": 1, "context_id": "ctx", "currentUrl": "https://example.com/"}]
    assert result["all_browsers"] is False
    assert result["tab_scope"] == "per_context"
    assert ("screenshot", (1,), {"quality": ws_browser_module.SCREENSHOT_QUALITY}) in calls

    await handler.on_disconnect("sid-snapshot")


@pytest.mark.anyio
async def test_browser_viewer_subscribe_skips_snapshot_for_interactive(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append(method)
            if method == "list":
                return {
                    "browsers": [{"id": 1, "context_id": "ctx", "currentUrl": "about:blank"}],
                    "last_interacted_browser_id": 1,
                }
            if method == "interactive_viewer":
                return {"available": True, "browser_id": 1, "url": "/desktop/session/test/"}
            if method == "screenshot":
                raise AssertionError("Interactive Browser must not wait for a redundant screenshot")
            raise AssertionError(method)

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is False
        return FakeRuntime()

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "per_context"})
    monkeypatch.setattr(
        ws_browser_module.AgentContext,
        "get",
        staticmethod(lambda context_id: SimpleNamespace(id=context_id)),
    )

    handler = ws_browser_module.WsBrowser(SimpleNamespace(), threading.RLock(), manager=None)
    result = await handler.process(
        "browser_viewer_subscribe",
        {"context_id": "ctx", "browser_id": 1, "viewer_transport": "interactive"},
        "sid-interactive",
    )

    assert result["viewer_transport"] == "interactive"
    assert result["snapshot"] is None
    assert "screenshot" not in calls
    await handler.on_disconnect("sid-interactive")


@pytest.mark.anyio
async def test_browser_viewer_subscribe_without_runtime_does_not_create_runtime(monkeypatch):
    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is False
        return None

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "has_restorable_browser_tabs", lambda context_id: False)
    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "per_context"})
    monkeypatch.setattr(
        ws_browser_module.AgentContext,
        "get",
        staticmethod(lambda context_id: SimpleNamespace(id=context_id)),
    )

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_subscribe",
        {"context_id": "ctx"},
        "sid-empty",
    )

    assert result["active_browser_id"] is None
    assert result["browsers"] == []
    assert ("sid-empty", "ctx") not in ws_browser_module.WsBrowser._streams


@pytest.mark.anyio
async def test_browser_viewer_subscribe_starts_runtime_for_saved_tabs(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            if method == "list":
                return {
                    "browsers": [
                        {"id": 4, "context_id": "ctx", "currentUrl": "https://example.com/"}
                    ],
                    "last_interacted_browser_id": 4,
                }
            if method == "interactive_viewer":
                return {"available": True, "browser_id": 4, "url": "/desktop/session/test/"}
            raise AssertionError(method)

    async def fake_get_runtime(context_id, create=True):
        calls.append(create)
        return FakeRuntime() if create else None

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "has_restorable_browser_tabs", lambda context_id: True)
    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "per_context"})
    monkeypatch.setattr(
        ws_browser_module.AgentContext,
        "get",
        staticmethod(lambda context_id: SimpleNamespace(id=context_id)),
    )

    handler = ws_browser_module.WsBrowser(SimpleNamespace(), threading.RLock(), manager=None)
    result = await handler.process(
        "browser_viewer_subscribe",
        {"context_id": "ctx", "viewer_transport": "interactive"},
        "sid-restore",
    )

    assert calls[:2] == [False, True]
    assert result["active_browser_id"] == 4
    assert result["browsers"][0]["currentUrl"] == "https://example.com/"
    await handler.on_disconnect("sid-restore")


@pytest.mark.anyio
async def test_browser_runtime_sessions_are_context_qualified(monkeypatch):
    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            assert method == "list"
            return {
                "browsers": [{"id": 1, "context_id": "ctx-a", "currentUrl": "https://example.com/"}],
                "last_interacted_browser_id": 1,
            }

    with browser_runtime_module._runtime_lock:
        previous_runtimes = dict(browser_runtime_module._runtimes)
        browser_runtime_module._runtimes.clear()
        browser_runtime_module._runtimes["ctx-a"] = FakeRuntime()
    try:
        sessions = await list_runtime_sessions()
    finally:
        with browser_runtime_module._runtime_lock:
            browser_runtime_module._runtimes.clear()
            browser_runtime_module._runtimes.update(previous_runtimes)

    assert sessions == [
        {
            "context_id": "ctx-a",
            "browsers": [{"id": 1, "context_id": "ctx-a", "currentUrl": "https://example.com/"}],
            "last_interacted_browser_id": 1,
        }
    ]


@pytest.mark.anyio
async def test_shared_runtime_session_list_includes_restored_inactive_chats(monkeypatch):
    class FakeSharedRuntime:
        async def call_for(self, context_id, method):
            assert context_id == browser_runtime_module.SHARED_RUNTIME_ID
            assert method == "list_all"
            return {
                "browsers": [
                    {"id": 1, "context_id": "ctx-a", "currentUrl": "https://example.com/"},
                    {"id": 2, "context_id": "ctx-b", "currentUrl": "https://example.org/"},
                ],
                "last_interacted_browser_ids": {"ctx-a": 1, "ctx-b": 2},
            }

    monkeypatch.setattr(
        browser_runtime_module,
        "get_browser_config",
        lambda: {"browser_tab_scope": "shared"},
    )
    with browser_runtime_module._runtime_lock:
        previous_runtimes = dict(browser_runtime_module._runtimes)
        previous_shared = browser_runtime_module._shared_runtime
        browser_runtime_module._runtimes.clear()
        browser_runtime_module._shared_runtime = FakeSharedRuntime()
    try:
        sessions = await list_runtime_sessions()
    finally:
        with browser_runtime_module._runtime_lock:
            browser_runtime_module._runtimes.clear()
            browser_runtime_module._runtimes.update(previous_runtimes)
            browser_runtime_module._shared_runtime = previous_shared

    assert [session["context_id"] for session in sessions] == ["ctx-a", "ctx-b"]
    assert [session["last_interacted_browser_id"] for session in sessions] == [1, 2]


@pytest.mark.anyio
async def test_browser_context_handles_share_one_runtime(monkeypatch):
    class FakeSharedRuntime:
        instances = []

        def __init__(self, context_id):
            self.context_id = context_id
            self.calls = []
            self.closed = []
            self.instances.append(self)

        async def call_for(self, context_id, method, *args, **kwargs):
            self.calls.append((context_id, method, args, kwargs))
            return {"context_id": context_id, "method": method}

        async def close(self, delete_profile=False):
            self.closed.append(delete_profile)

    monkeypatch.setattr(browser_runtime_module, "BrowserRuntime", FakeSharedRuntime)
    with browser_runtime_module._runtime_lock:
        previous_runtimes = dict(browser_runtime_module._runtimes)
        previous_shared = browser_runtime_module._shared_runtime
        browser_runtime_module._runtimes.clear()
        browser_runtime_module._shared_runtime = None
    try:
        first = await browser_runtime_module.get_runtime("ctx-a")
        second = await browser_runtime_module.get_runtime("ctx-b")

        assert first is not second
        assert first._runtime is second._runtime
        assert len(FakeSharedRuntime.instances) == 1
        assert FakeSharedRuntime.instances[0].context_id == browser_runtime_module.SHARED_RUNTIME_ID
        assert await first.call("list") == {"context_id": "ctx-a", "method": "list"}
        assert await second.call("open", "https://example.org/") == {
            "context_id": "ctx-b",
            "method": "open",
        }

        await browser_runtime_module.close_runtime("ctx-a", delete_profile=True)
        assert browser_runtime_module._shared_runtime is FakeSharedRuntime.instances[0]
        assert FakeSharedRuntime.instances[0].calls[-1][:2] == ("ctx-a", "close_context")

        await browser_runtime_module.close_all_runtimes()
        assert FakeSharedRuntime.instances[0].closed == [False]
    finally:
        with browser_runtime_module._runtime_lock:
            browser_runtime_module._runtimes.clear()
            browser_runtime_module._runtimes.update(previous_runtimes)
            browser_runtime_module._shared_runtime = previous_shared


@pytest.mark.anyio
async def test_shared_browser_runtime_keeps_tabs_context_scoped():
    class FakePage:
        def __init__(self, url):
            self.url = url
            self.closed = False

        async def evaluate(self, script, **kwargs):
            return {"title": self.url, "canGoBack": False, "loading": False}

        async def close(self):
            self.closed = True

    core = _BrowserRuntimeCore(browser_runtime_module.SHARED_RUNTIME_ID)
    page_a = FakePage("https://example.com/")
    page_b = FakePage("https://example.org/")
    core.context = object()
    core.pages = {
        1: BrowserPage(1, page_a, "ctx-a"),
        2: BrowserPage(2, page_b, "ctx-b"),
    }
    core._set_last_interacted("ctx-a", 1)
    core._set_last_interacted("ctx-b", 2)

    token = core.request_context_id.set("ctx-a")
    try:
        listing = await core.list()
        assert [browser["id"] for browser in listing["browsers"]] == [1]
        assert listing["last_interacted_browser_id"] == 1
        with pytest.raises(KeyError, match="Browser 2 is not open"):
            await core.state(2)
        await core.close_context()
    finally:
        core.request_context_id.reset(token)

    assert page_a.closed is True
    assert page_b.closed is False
    token = core.request_context_id.set("ctx-b")
    try:
        listing = await core.list()
        assert [browser["id"] for browser in listing["browsers"]] == [2]
        assert listing["browsers"][0]["context_id"] == "ctx-b"
    finally:
        core.request_context_id.reset(token)


@pytest.mark.anyio
async def test_shared_browser_runtime_matches_popup_to_its_opener_context():
    core = _BrowserRuntimeCore(browser_runtime_module.SHARED_RUNTIME_ID)
    opener_a = object()
    opener_b = object()
    core.pages = {
        1: BrowserPage(1, opener_a, "ctx-a"),
        2: BrowserPage(2, opener_b, "ctx-b"),
    }
    loop = asyncio.get_running_loop()
    waiter_a = loop.create_future()
    waiter_b = loop.create_future()
    core._pending_popups = [waiter_a, waiter_b]
    core._pending_popup_contexts = {
        waiter_a: "ctx-a",
        waiter_b: "ctx-b",
    }

    class Popup:
        async def opener(self):
            return opener_b

    context_id = await core._new_page_context_id(Popup())

    assert context_id == "ctx-b"
    assert core._pop_pending_popup(context_id) is waiter_b
    assert core._pending_popups == [waiter_a]


def test_explicit_open_claims_page_registered_by_playwright_event():
    class Page:
        @staticmethod
        def on(event, callback):
            assert event in {"close", "framenavigated"}

    core = _BrowserRuntimeCore(browser_runtime_module.SHARED_RUNTIME_ID)
    page = Page()
    registered = core._register_page_locked(
        page,
        "ctx-a",
    )
    core._set_last_interacted("ctx-a", registered.id)

    token = core.request_context_id.set("ctx-b")
    try:
        claimed = core._register_page_locked(page, "ctx-b")
    finally:
        core.request_context_id.reset(token)

    assert claimed is registered
    assert claimed.context_id == "ctx-b"
    assert core._last_interacted_browser_ids.get("ctx-a") is None


@pytest.mark.anyio
async def test_browser_restores_per_context_then_all_shared_tabs(monkeypatch):
    saved = []
    browser_config = {"browser_tab_scope": "per_context", "max_open_tabs": 32}

    class Page:
        def __init__(self):
            self.url = "about:blank"

        @staticmethod
        def is_closed():
            return False

        @staticmethod
        def on(event, callback):
            assert event in {"close", "framenavigated"}

    class Context:
        async def new_page(self):
            return Page()

    async def goto(page, url, **kwargs):
        page.url = url

    monkeypatch.setattr(
        browser_runtime_module,
        "get_browser_config",
        lambda: browser_config,
    )
    monkeypatch.setattr(
        browser_runtime_module,
        "_save_browser_tabs",
        lambda tabs: saved.append(tabs),
    )

    core = _BrowserRuntimeCore(browser_runtime_module.SHARED_RUNTIME_ID)
    core.context = Context()
    core._restore_state_loaded = True
    core._restore_state_exists = True
    core._restore_entries = [
        {"context_id": "ctx-a", "url": "https://example.com/one", "active": True},
        {"context_id": "ctx-b", "url": "https://example.org/two", "active": True},
    ]
    monkeypatch.setattr(core, "_goto", goto)

    token = core.request_context_id.set("ctx-a")
    try:
        await core._restore_tabs_for_scope()
    finally:
        core.request_context_id.reset(token)

    assert [page.context_id for page in core.pages.values()] == ["ctx-a"]
    assert [entry["context_id"] for entry in saved[-1]] == ["ctx-b", "ctx-a"]

    browser_config["browser_tab_scope"] = "shared"
    token = core.request_context_id.set("ctx-a")
    try:
        await core._restore_tabs_for_scope()
    finally:
        core.request_context_id.reset(token)

    assert [page.context_id for page in core.pages.values()] == ["ctx-a", "ctx-b"]
    assert {entry["url"] for entry in saved[-1]} == {
        "https://example.com/one",
        "https://example.org/two",
    }
    assert core._restored_all is True


def test_unexpected_browser_exit_keeps_last_saved_tabs(monkeypatch):
    saved = []
    restore_entries = [
        {"context_id": "ctx-a", "url": "https://example.com/", "active": True}
    ]
    monkeypatch.setattr(
        browser_runtime_module,
        "_save_browser_tabs",
        lambda tabs: saved.append(tabs),
    )

    core = _BrowserRuntimeCore(browser_runtime_module.SHARED_RUNTIME_ID)
    core.context = object()
    core._restore_state_loaded = True
    core._restore_entries = restore_entries
    core.pages = {1: BrowserPage(1, SimpleNamespace(url="https://example.com/"), "ctx-a")}

    core._on_context_closed()

    assert saved == []
    assert core._restore_entries == restore_entries
    assert core.pages == {}


def test_shared_browser_runtime_adopts_first_requesting_legacy_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(
        browser_runtime_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    legacy_profile = tmp_path / "tmp" / "browser" / "sessions" / "ctx-a"
    (legacy_profile / "Default").mkdir(parents=True)
    (legacy_profile / "Default" / "Cookies").write_bytes(b"legacy-session")

    core = _BrowserRuntimeCore(browser_runtime_module.SHARED_RUNTIME_ID)
    core._adopt_legacy_profile("ctx-a")

    assert not legacy_profile.exists()
    assert (core.profile_dir / "Default" / "Cookies").read_bytes() == b"legacy-session"


@pytest.mark.anyio
async def test_browser_runtime_refuses_new_tabs_when_context_limit_is_reached(monkeypatch):
    core = _BrowserRuntimeCore("ctx-limit")
    core.pages = {
        1: BrowserPage(1, SimpleNamespace()),
        2: BrowserPage(2, SimpleNamespace()),
    }

    async def fake_ensure_started():
        return None

    monkeypatch.setattr(core, "ensure_started", fake_ensure_started)
    monkeypatch.setattr(
        browser_runtime_module,
        "get_browser_config",
        lambda: {"max_open_tabs": 2, "default_homepage": "about:blank"},
    )

    with pytest.raises(RepairableException, match="Browser tab limit reached"):
        await core.open("https://example.com/")


@pytest.mark.anyio
async def test_browser_viewer_command_returns_only_requested_context_tabs(monkeypatch):
    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            if method == "list":
                return {
                    "browsers": [{"id": 1, "context_id": "ctx-a", "currentUrl": "about:blank"}],
                    "last_interacted_browser_id": 1,
                }
            raise AssertionError(method)

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx-a"
        return FakeRuntime()

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "per_context"})

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=_TestWsManager(),
    )

    result = await handler.process(
        "browser_viewer_command",
        {"context_id": "ctx-a", "command": "list"},
        "sid-1",
    )

    assert result["all_browsers"] is False
    assert result["tab_scope"] == "per_context"
    assert result["active_browser_context_id"] == "ctx-a"
    assert result["browsers"] == [{"id": 1, "context_id": "ctx-a", "currentUrl": "about:blank"}]


@pytest.mark.anyio
async def test_browser_viewer_command_can_return_shared_context_tabs(monkeypatch):
    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            if method == "list":
                return {
                    "browsers": [{"id": 1, "context_id": "ctx-a", "currentUrl": "about:blank"}],
                    "last_interacted_browser_id": 1,
                }
            raise AssertionError(method)

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx-a"
        return FakeRuntime()

    async def fake_list_runtime_sessions():
        return [
            {
                "context_id": "ctx-a",
                "browsers": [{"id": 1, "context_id": "ctx-a", "currentUrl": "about:blank"}],
                "last_interacted_browser_id": 1,
            },
            {
                "context_id": "ctx-b",
                "browsers": [{"id": 1, "context_id": "ctx-b", "currentUrl": "https://example.org/"}],
                "last_interacted_browser_id": 1,
            },
        ]

    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "shared"})
    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "list_runtime_sessions", fake_list_runtime_sessions)

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=_TestWsManager(),
    )

    result = await handler.process(
        "browser_viewer_command",
        {"context_id": "ctx-a", "command": "list"},
        "sid-1",
    )

    assert result["all_browsers"] is True
    assert result["tab_scope"] == "shared"
    assert result["active_browser_context_id"] == "ctx-a"
    assert [browser["context_id"] for browser in result["browsers"]] == ["ctx-a", "ctx-b"]


@pytest.mark.anyio
async def test_browser_viewer_sessions_lists_only_requested_context_without_creating(monkeypatch):
    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            assert method == "list"
            return {
                "browsers": [{"id": 1, "context_id": "ctx-b", "currentUrl": "about:blank"}],
                "last_interacted_browser_id": 1,
            }

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx-b"
        assert create is False
        return FakeRuntime()

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)
    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "per_context"})

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_sessions",
        {"context_id": "ctx-b"},
        "sid-1",
    )

    assert result == {
        "context_id": "ctx-b",
        "browsers": [{"id": 1, "context_id": "ctx-b", "currentUrl": "about:blank"}],
        "all_browsers": False,
        "tab_scope": "per_context",
    }


@pytest.mark.anyio
async def test_browser_viewer_sessions_can_list_shared_context_tabs(monkeypatch):
    async def fake_list_runtime_sessions():
        return [
            {
                "context_id": "ctx-a",
                "browsers": [{"id": 1, "context_id": "ctx-a", "currentUrl": "about:blank"}],
                "last_interacted_browser_id": 1,
            },
            {
                "context_id": "ctx-b",
                "browsers": [{"id": 1, "context_id": "ctx-b", "currentUrl": "https://example.org/"}],
                "last_interacted_browser_id": 1,
            },
        ]

    async def fail_get_runtime(*args, **kwargs):
        raise AssertionError("shared sessions refresh must not fetch one runtime")

    monkeypatch.setattr(ws_browser_module, "get_browser_config", lambda: {"browser_tab_scope": "shared"})
    monkeypatch.setattr(ws_browser_module, "list_runtime_sessions", fake_list_runtime_sessions)
    monkeypatch.setattr(ws_browser_module, "get_runtime", fail_get_runtime)

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_sessions",
        {"context_id": "ctx-b"},
        "sid-1",
    )

    assert result == {
        "context_id": "ctx-b",
        "browsers": [
            {"id": 1, "context_id": "ctx-a", "currentUrl": "about:blank"},
            {"id": 1, "context_id": "ctx-b", "currentUrl": "https://example.org/"},
        ],
        "all_browsers": True,
        "tab_scope": "shared",
    }


@pytest.mark.anyio
async def test_browser_viewer_viewport_input_dispatches_resize(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            return {"ok": True, "method": method, "args": args}

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is False
        return FakeRuntime()

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_input",
        {
            "context_id": "ctx",
            "browser_id": 7,
            "input_type": "viewport",
            "width": 1280,
            "height": 720,
            "restart_stream": True,
            "viewer_transport": "interactive",
        },
        "sid-1",
    )

    assert result == {
        "state": {"ok": True, "method": "set_viewport", "args": (7, 1280, 720)},
        "snapshot": None,
    }
    assert calls == [
        (
            "set_viewport",
            (7, 1280, 720),
            {
                "restart_screencast": True,
                "resize_interactive": True,
                "include_state": False,
            },
        )
    ]


@pytest.mark.anyio
async def test_browser_interactive_resize_uses_native_window_viewport():
    fitted = []

    class FakePage:
        viewport_size = None

        async def set_viewport_size(self, viewport):
            raise AssertionError("Interactive native viewport must not enable emulation")

    class FakeInteractiveView:
        display = 0
        width = 1024
        height = 768

        def resize(self, width, height):
            self.width = width
            self.height = height
            return {"ok": True, "width": width, "height": height}

    page = FakePage()
    core = _BrowserRuntimeCore("ctx")
    core.context = object()
    core.pages[7] = browser_runtime_module.BrowserPage(id=7, page=page)
    core.interactive_view = FakeInteractiveView()

    async def fake_fit(fitted_page):
        fitted.append(fitted_page)

    async def fake_state(browser_id):
        return {"id": browser_id}

    core._fit_browser_window = fake_fit
    core._state = fake_state

    result = await core.set_viewport(
        7,
        1280,
        720,
        resize_interactive=True,
        include_state=False,
    )

    assert result == {
        "state": None,
        "viewport": {"width": 1280, "height": 720},
    }
    assert fitted == [page]


@pytest.mark.anyio
async def test_browser_runtime_restarts_screencast_without_resizing_same_viewport():
    viewport_calls = []
    stopped = []
    settled = []

    class FakePage:
        viewport_size = {"width": 1280, "height": 720}

        async def set_viewport_size(self, viewport):
            viewport_calls.append(dict(viewport))

    core = _BrowserRuntimeCore("ctx")
    core.context = object()
    core.pages[7] = browser_runtime_module.BrowserPage(id=7, page=FakePage())

    async def fake_stop_screencasts(browser_id):
        stopped.append(browser_id)

    async def fake_settle(page, short=False):
        settled.append(short)

    async def fake_state(browser_id):
        return {"id": browser_id}

    core._stop_screencasts_for_browser = fake_stop_screencasts
    core._settle = fake_settle
    core._state = fake_state

    result = await core.set_viewport(7, 1280, 720, restart_screencast=True)

    assert result == {
        "state": {"id": 7},
        "viewport": {"width": 1280, "height": 720},
    }
    assert viewport_calls == []
    assert stopped == [7]
    assert settled == [True]


@pytest.mark.anyio
async def test_browser_runtime_applies_changed_viewport_once():
    calls = []
    stopped = []
    settled = []

    class FakePage:
        viewport_size = {"width": 1024, "height": 768}

        async def set_viewport_size(self, viewport):
            calls.append(("viewport", dict(viewport)))

    core = _BrowserRuntimeCore("ctx")
    core.context = object()
    core.pages[7] = browser_runtime_module.BrowserPage(id=7, page=FakePage())

    async def fake_stop_screencasts(browser_id):
        stopped.append(browser_id)

    async def fake_settle(page, short=False):
        settled.append(short)

    async def fake_state(browser_id):
        return {"id": browser_id}

    core._stop_screencasts_for_browser = fake_stop_screencasts
    core._settle = fake_settle
    core._state = fake_state

    result = await core.set_viewport(7, 672, 789)

    assert result == {
        "state": {"id": 7},
        "viewport": {"width": 672, "height": 789},
    }
    assert calls == [
        ("viewport", {"width": 672, "height": 789}),
    ]
    assert stopped == [7]
    assert settled == [True]


@pytest.mark.anyio
async def test_browser_runtime_screenshot_file_defaults_to_chat_scoped_artifact(monkeypatch, tmp_path):
    screenshot_calls = []

    def fake_get_abs_path(*parts):
        return str(tmp_path.joinpath(*parts))

    def fake_normalize_a0_path(path):
        return "/a0/" + str(Path(path).relative_to(tmp_path)).replace("\\", "/")

    monkeypatch.setattr(browser_runtime_module.files, "get_abs_path", fake_get_abs_path)
    monkeypatch.setattr(browser_runtime_module.files, "normalize_a0_path", fake_normalize_a0_path)

    class FakePage:
        url = "about:blank"
        viewport_size = {"width": 1024, "height": 768}

        async def screenshot(self, **kwargs):
            screenshot_calls.append(kwargs)
            if kwargs.get("path"):
                Path(kwargs["path"]).parent.mkdir(parents=True, exist_ok=True)
                Path(kwargs["path"]).write_bytes(b"image-bytes")
            return b"image-bytes"

        async def evaluate(self, script, payload=None, **kwargs):
            return {"title": "Blank", "canGoBack": False, "loading": False}

    core = _BrowserRuntimeCore(browser_runtime_module.SHARED_RUNTIME_ID)
    core.context = object()
    core.pages[5] = browser_runtime_module.BrowserPage(
        id=5,
        page=FakePage(),
        context_id="ctx/id",
    )
    token = core.request_context_id.set("ctx/id")

    try:
        result = await core.screenshot_file(5, quality=500)
    finally:
        core.request_context_id.reset(token)

    assert Path(result["path"]).read_bytes() == b"image-bytes"
    assert result["a0_path"].startswith("/a0/usr/chats/ctx_id/screenshots/browser/browser-5-")
    assert result["context_id"] == "ctx/id"
    assert result["mime"] == "image/jpeg"
    assert result["ephemeral"] is False
    assert result["chat_scoped"] is True
    assert result["vision_load"] == {
        "tool_name": "vision_load",
        "tool_args": {"paths": [result["a0_path"]]},
    }
    assert "image" not in result
    assert not list((tmp_path / "tmp" / "browser" / "screenshots").rglob("*.jpg"))
    assert screenshot_calls[-1]["type"] == "jpeg"
    assert screenshot_calls[-1]["quality"] == 95
    assert screenshot_calls[-1]["full_page"] is False
    assert "path" not in screenshot_calls[-1]

    png_path = tmp_path / "custom.png"
    token = core.request_context_id.set("ctx/id")
    try:
        png_result = await core.screenshot_file(5, quality=1, full_page=True, path=str(png_path))
    finally:
        core.request_context_id.reset(token)

    assert png_result["path"] == str(png_path)
    assert png_result["mime"] == "image/png"
    assert screenshot_calls[-1] == {
        "path": str(png_path),
        "type": "png",
        "full_page": True,
    }


@pytest.mark.anyio
async def test_vision_load_materializes_ephemeral_browser_refs(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "helpers.tool", SimpleNamespace(Response=_TestResponse, Tool=_TestTool, coerce_bool=helpers.tool.coerce_bool))
    history_stub = ModuleType("helpers.history")

    class _RawMessage(dict):
        def __init__(self, raw_content, preview):
            super().__init__(raw_content=raw_content, preview=preview)

    history_stub.RawMessage = _RawMessage
    monkeypatch.setitem(sys.modules, "helpers.history", history_stub)
    monkeypatch.delitem(sys.modules, "tools.vision_load", raising=False)
    import tools.vision_load as vision_load_module

    def fake_get_abs_path(*parts):
        return str(tmp_path.joinpath(*parts))

    def fake_normalize_a0_path(path):
        return "/a0/" + str(Path(path).relative_to(tmp_path)).replace("\\", "/")

    monkeypatch.setattr(vision_load_module.chat_media.files, "get_abs_path", fake_get_abs_path)
    monkeypatch.setattr(vision_load_module.chat_media.files, "normalize_a0_path", fake_normalize_a0_path)
    monkeypatch.setattr(vision_load_module, "get_chat_model_config", lambda _agent: {"vision": True, "max_embeds": 10})
    monkeypatch.setattr(vision_load_module, "get_vision_model_config", lambda _agent: {})

    tool_results = []
    messages = []
    updates = []
    agent = SimpleNamespace(
        context=SimpleNamespace(
            id="ctx-vision", get_data=lambda *_args, **_kwargs: None
        ),
        agent_name="Agent 0",
        hist_add_tool_result=lambda *args, **kwargs: tool_results.append((args, kwargs)),
        hist_add_message=lambda *args, **kwargs: messages.append((args, kwargs)),
    )
    ref = vision_load_module.ephemeral_images.put_image(
        context_id="ctx-vision",
        mime="image/jpeg",
        data=SMALL_JPEG_10X10,
        name="browser-shot.jpg",
    )
    tool = vision_load_module.VisionLoad(
        agent=agent,
        name="vision_load",
        method=None,
        args={"paths": [ref]},
        message="",
        loop_data=None,
    )
    tool.log = SimpleNamespace(id="vision-log", update=lambda **kwargs: updates.append(kwargs))

    response = await tool.execute(paths=[ref])
    await tool.after_execution(response)

    assert vision_load_module.ephemeral_images.get_image(ref, context_id="ctx-vision") is None
    assert tool.loaded_paths == ["browser-shot.jpg"]
    raw_message = messages[0][1]["content"]
    stored_ref = raw_message["raw_content"][0]["image_url"]["url"]
    assert stored_ref.startswith("/a0/usr/chats/ctx-vision/screenshots/browser/browser-shot-")
    stored_path = tmp_path / stored_ref.removeprefix("/a0/")
    assert stored_path.read_bytes() == __import__("base64").b64decode(SMALL_JPEG_10X10)
    assert updates[-1]["content"] == response.message


@pytest.mark.anyio
async def test_browser_runtime_ref_point_resolution_applies_offsets():
    eval_payloads = []
    moves = []

    class FakeMouse:
        async def move(self, x, y, **kwargs):
            moves.append((x, y, kwargs))

    class FakePage:
        url = "about:blank"

        def __init__(self):
            self.mouse = FakeMouse()

        async def evaluate(self, script, payload=None, **kwargs):
            eval_payloads.append((script, payload))
            if payload and "offsets" in payload:
                return {
                    "x": 10 + payload["offsets"]["offset_x"],
                    "y": 20 + payload["offsets"]["offset_y"],
                    "rect": {"x": 10, "y": 20, "width": 100, "height": 40},
                    "selector": "#target",
                }
            return {"title": "Blank", "canGoBack": False, "loading": False}

    core = _BrowserRuntimeCore("ctx")
    core.context = object()
    core.pages[7] = browser_runtime_module.BrowserPage(id=7, page=FakePage())
    core._ensure_content_helper = lambda _page: asyncio.sleep(0)

    result = await core.hover(7, ref=4, offset_x=3, offset_y=5)

    assert moves == [(13.0, 25.0, {})]
    assert result["action"]["point"]["selector"] == "#target"
    assert eval_payloads[0][1] == {
        "ref": 4,
        "offsets": {
            "offset_x": 3.0,
            "offset_y": 5.0,
            "useOffsets": True,
        },
    }


def test_browser_runtime_upload_path_normalization(monkeypatch, tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")

    monkeypatch.setattr(
        browser_runtime_module.files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )

    assert _BrowserRuntimeCore._normalize_upload_paths(path=str(first)) == [str(first)]
    assert _BrowserRuntimeCore._normalize_upload_paths(paths=["second.txt"]) == [str(second)]
    assert _BrowserRuntimeCore._normalize_upload_paths(path=str(first), paths=["second.txt"]) == [
        str(second),
        str(first),
    ]


@pytest.mark.anyio
async def test_browser_runtime_clipboard_paste_uses_dom_bridge():
    eval_payloads = []
    settled = []

    class FakeKeyboard:
        def __init__(self):
            self.inserted = []

        async def insert_text(self, text):
            self.inserted.append(text)

    class FakePage:
        url = "about:blank"

        def __init__(self):
            self.keyboard = FakeKeyboard()

        async def evaluate(self, script, payload=None, **kwargs):
            if payload is not None:
                eval_payloads.append((script, payload))
                return {
                    "action": "paste",
                    "text": payload["text"],
                    "changed": True,
                    "default_prevented": False,
                }
            return {"title": "Blank", "canGoBack": False, "loading": False}

    page = FakePage()
    core = _BrowserRuntimeCore("ctx")
    core.context = object()
    core.pages[7] = browser_runtime_module.BrowserPage(id=7, page=page)

    async def fake_settle(_page, short=False):
        settled.append(short)

    core._settle = fake_settle

    result = await core.clipboard(7, action="paste", text="hello")

    assert result["state"]["id"] == 7
    assert result["clipboard"]["changed"] is True
    assert result["clipboard"]["text"] == "hello"
    assert eval_payloads[0][1] == {"action": "paste", "text": "hello"}
    assert "insertFromPaste" in eval_payloads[0][0]
    assert page.keyboard.inserted == []
    assert settled == [True]


@pytest.mark.anyio
async def test_browser_runtime_clipboard_paste_falls_back_to_keyboard_insert_text():
    class FakeKeyboard:
        def __init__(self):
            self.inserted = []

        async def insert_text(self, text):
            self.inserted.append(text)

    class FakePage:
        url = "about:blank"

        def __init__(self):
            self.keyboard = FakeKeyboard()

        async def evaluate(self, script, payload=None, **kwargs):
            if payload is not None:
                return {
                    "action": "paste",
                    "text": payload["text"],
                    "changed": False,
                    "default_prevented": False,
                }
            return {"title": "Blank", "canGoBack": False, "loading": False}

    page = FakePage()
    core = _BrowserRuntimeCore("ctx")
    core.context = object()
    core.pages[7] = browser_runtime_module.BrowserPage(id=7, page=page)
    core._settle = lambda _page, short=False: asyncio.sleep(0)

    result = await core.clipboard(7, action="paste", text="hello")

    assert result["clipboard"]["changed"] is True
    assert result["clipboard"]["method"] == "keyboard.insert_text"
    assert page.keyboard.inserted == ["hello"]


@pytest.mark.anyio
async def test_browser_viewer_wheel_input_dispatches_scroll(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            return {"ok": True, "method": method, "args": args}

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is False
        return FakeRuntime()

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_input",
        {
            "context_id": "ctx",
            "browser_id": 3,
            "input_type": "wheel",
            "x": 320,
            "y": 480,
            "delta_x": 0,
            "delta_y": 640,
        },
        "sid-1",
    )

    assert result == {
        "state": {"ok": True, "method": "wheel", "args": (3, 320.0, 480.0, 0.0, 640.0)},
        "snapshot": None,
    }
    assert calls == [("wheel", (3, 320.0, 480.0, 0.0, 640.0), {})]


@pytest.mark.anyio
async def test_browser_viewer_clipboard_input_dispatches_runtime(monkeypatch):
    calls = []
    clipboard = {"action": "paste", "text": "hello", "changed": True}

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            return {
                "state": {"id": args[0], "currentUrl": "about:blank"},
                "clipboard": clipboard,
            }

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is False
        return FakeRuntime()

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    result = await handler.process(
        "browser_viewer_input",
        {
            "context_id": "ctx",
            "browser_id": 3,
            "input_type": "clipboard",
            "action": "paste",
            "text": "hello",
        },
        "sid-1",
    )

    assert result == {
        "state": {"id": 3, "currentUrl": "about:blank"},
        "clipboard": clipboard,
        "snapshot": None,
    }
    assert calls == [
        ("clipboard", (3,), {"action": "paste", "text": "hello"})
    ]


@pytest.mark.anyio
async def test_browser_viewer_annotation_dispatches_runtime(monkeypatch):
    calls = []

    class FakeRuntime:
        async def call(self, method, *args, **kwargs):
            calls.append((method, args, kwargs))
            return {
                "kind": "element",
                "point": {"x": 320, "y": 180},
                "target": {"tagName": "BUTTON", "selector": "#save"},
            }

    async def fake_get_runtime(context_id, create=True):
        assert context_id == "ctx"
        assert create is False
        return FakeRuntime()

    monkeypatch.setattr(ws_browser_module, "get_runtime", fake_get_runtime)

    handler = ws_browser_module.WsBrowser(
        SimpleNamespace(),
        threading.RLock(),
        manager=None,
    )

    payload = {
        "kind": "element",
        "point": {"x": 320, "y": 180},
        "viewport": {"width": 1280, "height": 720},
    }
    result = await handler.process(
        "browser_viewer_annotation",
        {
            "context_id": "ctx",
            "browser_id": 4,
            "viewer_id": "viewer-1",
            "payload": payload,
        },
        "sid-1",
    )

    assert result == {
        "annotation": {
            "kind": "element",
            "point": {"x": 320, "y": 180},
            "target": {"tagName": "BUTTON", "selector": "#save"},
        },
        "context_id": "ctx",
        "browser_id": 4,
        "viewer_id": "viewer-1",
    }
    assert calls == [("annotation_target", (4, payload), {})]


def test_browser_runtime_normalizes_multi_group_ids_and_modifiers():
    core = _BrowserRuntimeCore("ctx")

    assert core._multi_group_key({"browser_id": 7}) == 7
    assert core._multi_group_key({"browser_id": "7"}) == 7
    assert core._multi_group_key({"browser_id": "browser-7"}) == 7
    assert core._multi_group_key({"browser_id": ""}) is None
    assert core._normalize_modifiers("Control") == ["Control"]
    assert core._normalize_modifiers(["Control", " Shift "]) == ["Control", "Shift"]
    assert core._normalize_modifiers([]) is None

    with pytest.raises(ValueError):
        core._normalize_modifiers("Ctrl")


def test_browser_runtime_background_focus_restores_previous_active_tab():
    core = _BrowserRuntimeCore("ctx")
    core.pages[1] = browser_runtime_module.BrowserPage(id=1, page=object())
    core.pages[2] = browser_runtime_module.BrowserPage(id=2, page=object())

    assert core._background_focus_target(previous_focus=1, fallback_id=2) == 1

    core.pages.pop(1)

    assert core._background_focus_target(previous_focus=1, fallback_id=2) == 2


def test_browser_cleanup_extensions_follow_extensible_path_layout():
    extension = __import__("helpers.extension", fromlist=["_get_extension_classes"])
    remove_classes = extension._get_extension_classes(  # type: ignore[attr-defined]
        "_functions/agent/AgentContext/remove/start"
    )
    reset_classes = extension._get_extension_classes(  # type: ignore[attr-defined]
        "_functions/agent/AgentContext/reset/start"
    )

    assert any(cls.__name__ == "CleanupBrowserRuntimeOnRemove" for cls in remove_classes)
    assert any(cls.__name__ == "CleanupBrowserRuntimeOnReset" for cls in reset_classes)


def test_legacy_browser_dependency_is_removed():
    assert not (PROJECT_ROOT / "plugins" / ("_browser" + "_agent")).exists()
    assert ("browser" + "-use") not in (PROJECT_ROOT / "requirements.txt").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("timeout", [False, True])
def test_context_cleanup_preserves_shared_event_loop(monkeypatch, timeout):
    calls = []

    class CleanupTask:
        def __init__(self, thread_name):
            calls.append(("thread", thread_name))

        def start_task(self, fn, context_id, **kwargs):
            calls.append(("close", context_id))

        def result_sync(self, timeout):
            if should_timeout:
                raise TimeoutError("cleanup timed out")

        def kill(self, terminate_thread=False):
            assert not terminate_thread, "Other context cleanup tasks share this thread"
            calls.append(("cancel", None))

    should_timeout = timeout
    monkeypatch.setattr(browser_runtime_module, "DeferredTask", CleanupTask)
    if timeout:
        with pytest.raises(TimeoutError):
            browser_runtime_module.close_runtime_sync("first")
    else:
        browser_runtime_module.close_runtime_sync("first")
    assert calls == [("thread", "BrowserCleanup"), ("close", "first"), ("cancel", None)]


def test_browser_download_preferences_preserve_user_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(browser_runtime_module.files, "get_abs_path", lambda *parts: str(tmp_path.joinpath(*parts)))
    core = _BrowserRuntimeCore("downloads")
    path = core.profile_dir / "Default" / "Preferences"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"download": {"prompt_for_download": True}, "unrelated": {"keep": 1}}))
    core._prepare_download_preferences()
    saved = json.loads(path.read_text())
    assert saved["download"] == {"prompt_for_download": True, "default_directory": str(core.downloads_dir)}
    assert saved["unrelated"] == {"keep": 1}
    saved["download"]["default_directory"] = "/custom/downloads"
    path.write_text(json.dumps(saved))
    core._prepare_download_preferences()
    assert json.loads(path.read_text()) == saved


@pytest.mark.anyio
async def test_browser_zoom_targets_private_display_and_rejects_invalid_direction(monkeypatch):
    core = _BrowserRuntimeCore("zoom")
    calls = []

    async def started():
        pass

    async def focused():
        calls.append("focus")

    async def state(browser_id):
        return {"id": browser_id, "zoom": 110}

    core.ensure_started = started
    core._state = state
    core.interactive_view.display = 77
    core.pages[1] = BrowserPage(id=1, page=SimpleNamespace(bring_to_front=focused), context_id="zoom")
    monkeypatch.setattr(browser_runtime_module.shutil, "which", lambda name: "/usr/bin/xdotool")
    monkeypatch.setattr(browser_runtime_module.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    assert await core.zoom(1, "in") == {"id": 1, "zoom": 110}
    assert calls[0] == "focus"
    command, options = calls[1]
    assert command == ["/usr/bin/xdotool", "key", "--clearmodifiers", "ctrl+plus"]
    assert options["env"]["DISPLAY"] == ":77"
    assert options["check"] is True and options["timeout"] == 3
    with pytest.raises(ValueError, match="Zoom direction"):
        await core.zoom(1, "in; arbitrary-command")
    assert len(calls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("enabled,capture,expected", [(False, True, False), (True, False, False), (True, True, True)])
async def test_annotation_screenshots_require_saved_opt_in_and_explicit_capture(monkeypatch, enabled, capture, expected):
    calls = []
    agent = object()

    class Runtime:
        async def call(self, method, *args, **kwargs):
            calls.append(method)
            return {"image": "anBlZw==", "mime": "image/jpeg"} if method == "screenshot" else {"kind": "element"}

    async def runtime(*args, **kwargs):
        return Runtime()

    def config(agent=None):
        assert agent is not None
        return {"annotation_screenshots": enabled}

    monkeypatch.setattr(ws_browser_module, "get_runtime", runtime)
    monkeypatch.setattr(ws_browser_module.AgentContext, "get", lambda context_id: SimpleNamespace(agent0=agent))
    monkeypatch.setattr(ws_browser_module, "get_browser_config", config)
    handler = ws_browser_module.WsBrowser(SimpleNamespace(), threading.RLock(), manager=None)
    result = await handler.process("browser_viewer_annotation", {
        "context_id": "ctx", "browser_id": 1, "capture_screenshot": capture,
        "payload": {"kind": "element"},
    }, "sid")
    assert ("screenshot" in result) is expected
    if capture:
        assert result["annotation_screenshots"] is enabled
    assert calls == (["annotation_target", "screenshot"] if expected else ["annotation_target"])
    assert normalize_browser_config({})["annotation_screenshots"] is False
    assert normalize_browser_config({"annotation_screenshots": "false"})["annotation_screenshots"] is False


@pytest.mark.anyio
async def test_quick_browser_location_saves_current_project_and_validates_input(monkeypatch):
    from plugins._browser.api import extensions as api

    saved = []
    context = SimpleNamespace()
    agent = SimpleNamespace(context=context)
    handler = api.Extensions(SimpleNamespace(), threading.RLock())
    monkeypatch.setattr(handler, "_agent_from_input", lambda data: agent)
    monkeypatch.setattr(handler, "_browser_extension_payload", lambda agent=None: {"ok": True})
    monkeypatch.setattr(api, "get_browser_config", lambda agent=None: {"runtime_backend": "container", "proxy_server": "http://proxy.test"})
    monkeypatch.setattr(api.projects, "get_context_project_name", lambda ctx: "my-project")
    monkeypatch.setattr(api.plugins, "save_plugin_config", lambda *args: saved.append(args))
    for value in ("host_required", "container"):
        assert await handler.process({"action": "set_runtime_backend", "context_id": "ctx", "runtime_backend": value}, None) == {"ok": True}
        assert saved[-1] == ("_browser", "my-project", "", {"runtime_backend": value, "proxy_server": "http://proxy.test"})
    for value in ("wrong", [], None):
        result = await handler.process({"action": "set_runtime_backend", "runtime_backend": value}, None)
        assert result["ok"] is False
    monkeypatch.setattr(handler, "_agent_from_input", lambda data: None)
    result = await handler.process({"action": "set_runtime_backend", "context_id": "deleted", "runtime_backend": "container"}, None)
    assert result["ok"] is False
    assert len(saved) == 2


def test_browser_annotation_attachments_and_quick_setting_failure():
    source = (PROJECT_ROOT / "plugins/_browser/webui/browser-store.js").read_text()
    source = source[source.index("const BROWSER_SUBSCRIBE_TIMEOUT_MS"):source.index("export const store")]
    script = """
import assert from 'node:assert/strict';
let response;
let request;
const notices = [];
const notificationStore = { addFrontendToastOnly: (...args) => notices.push(args) };
const callJsonApi = async (path, payload) => { request = payload; return response; };
const attachmentsStore = { files: [], getAttachmentDisplayInfo: () => ({}), addAttachment(item) { this.files.push(item); } };
""" + source + """
Object.assign(model, { resolveContextId: () => 'ctx', contextId: 'ctx', activeBrowserContextId: 'ctx' });
model.annotationComments = [
  {id: 'ours', contextId: 'ctx', browserId: 1, screenshot: {image: btoa('jpeg')}},
  {id: 'other', contextId: 'other', browserId: 2, screenshot: {image: btoa('private')}},
];
model.attachAnnotationScreenshots();
assert.equal(attachmentsStore.files.length, 0);
model.annotationScreenshots = true;
model.attachAnnotationScreenshots();
assert.equal(attachmentsStore.files.length, 1);
assert.equal(await attachmentsStore.files[0].file.text(), 'jpeg');
assert.equal(attachmentsStore.files[0].name, 'annotation-1-ours.jpg');
response = {ok: true, runtime_backend: 'host_required', annotation_screenshots: false};
await model.setRuntimeBackend('host_required');
assert.equal(request.context_id, 'ctx');
assert.equal(model.runtimeBackend, 'host_required');
assert.equal(model.runtimeBackendSaving, false);
response = {ok: false, error: 'save failed'};
await model.setRuntimeBackend('container');
assert.equal(model.runtimeBackend, 'host_required');
assert.equal(model.runtimeBackendSaving, false);
assert.deepEqual(notices.at(-1), ['error', 'save failed']);
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True, text=True)
