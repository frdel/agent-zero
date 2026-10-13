import asyncio
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import helpers.settings as settings_module

ENV_TOKEN = "test-token-123"


def _isolate_settings(monkeypatch):
    """Keep tests away from on-disk settings, version reads, and sensitive loading."""
    monkeypatch.setattr(settings_module.git, "get_version", lambda: "v1")
    monkeypatch.setattr(settings_module, "_settings", None)
    monkeypatch.setattr(settings_module, "_read_settings_file", lambda: None)
    monkeypatch.setattr(settings_module, "_write_settings_file", lambda _current: None)
    monkeypatch.setattr(settings_module, "_load_sensitive_settings", lambda _current: None)


def test_env_token_used_when_set(monkeypatch):
    _isolate_settings(monkeypatch)
    monkeypatch.setenv("A0_SET_mcp_server_token", ENV_TOKEN)
    monkeypatch.setattr(settings_module, "create_auth_token", lambda: "derived-token")

    defaults = settings_module.get_default_settings()
    assert defaults["mcp_server_token"] == ENV_TOKEN

    normalized = settings_module.normalize_settings(defaults)
    assert normalized["mcp_server_token"] == ENV_TOKEN


def test_uppercase_env_token_used_when_snake_case_missing(monkeypatch):
    _isolate_settings(monkeypatch)
    monkeypatch.delenv("A0_SET_mcp_server_token", raising=False)
    monkeypatch.setenv("A0_SET_MCP_SERVER_TOKEN", ENV_TOKEN)
    monkeypatch.setattr(settings_module, "create_auth_token", lambda: "derived-token")

    defaults = settings_module.get_default_settings()
    assert defaults["mcp_server_token"] == ENV_TOKEN


def test_token_derived_when_env_missing(monkeypatch):
    _isolate_settings(monkeypatch)
    monkeypatch.delenv("A0_SET_mcp_server_token", raising=False)
    monkeypatch.delenv("A0_SET_MCP_SERVER_TOKEN", raising=False)
    monkeypatch.setattr(settings_module, "create_auth_token", lambda: "derived-token")

    defaults = settings_module.get_default_settings()
    assert defaults["mcp_server_token"] == "derived-token"

    normalized = settings_module.normalize_settings(defaults)
    assert normalized["mcp_server_token"] == "derived-token"


def test_env_token_survives_normalize_and_get_settings(monkeypatch):
    _isolate_settings(monkeypatch)
    monkeypatch.setenv("A0_SET_mcp_server_token", ENV_TOKEN)
    monkeypatch.setattr(settings_module, "create_auth_token", lambda: "derived-token")

    # normalize replaces any stored value with the resolved env token
    stale = settings_module.get_default_settings()
    stale["mcp_server_token"] = "stored-stale-token"
    normalized = settings_module.normalize_settings(stale)
    assert normalized["mcp_server_token"] == ENV_TOKEN

    # full get_settings() path (no settings file) exposes the env token
    current = settings_module.get_settings()
    assert current["mcp_server_token"] == ENV_TOKEN


def test_env_token_survives_set_settings_roundtrip(monkeypatch):
    _isolate_settings(monkeypatch)
    monkeypatch.setenv("A0_SET_mcp_server_token", ENV_TOKEN)
    monkeypatch.setattr(settings_module, "create_auth_token", lambda: "derived-token")

    base = settings_module.get_default_settings()
    saved = settings_module.set_settings(base, apply=False)
    assert saved["mcp_server_token"] == ENV_TOKEN

    reloaded = settings_module.get_settings()
    assert reloaded["mcp_server_token"] == ENV_TOKEN


def test_token_derived_when_env_missing_real_hash(monkeypatch):
    """Backward compat without stubbing: value must equal the real create_auth_token()."""
    _isolate_settings(monkeypatch)
    monkeypatch.delenv("A0_SET_mcp_server_token", raising=False)
    monkeypatch.delenv("A0_SET_MCP_SERVER_TOKEN", raising=False)

    defaults = settings_module.get_default_settings()
    assert defaults["mcp_server_token"] == settings_module.create_auth_token()

    normalized = settings_module.normalize_settings(defaults)
    assert normalized["mcp_server_token"] == settings_module.create_auth_token()


def test_invalid_env_token_falls_back_to_derived(monkeypatch):
    _isolate_settings(monkeypatch)
    monkeypatch.setenv("A0_SET_mcp_server_token", "invalid token!@#")
    monkeypatch.setattr(settings_module, "create_auth_token", lambda: "derived-token")

    defaults = settings_module.get_default_settings()
    assert defaults["mcp_server_token"] == "derived-token"


def test_apply_settings_pushes_env_token_to_mcp_and_a2a_proxies(monkeypatch):
    _isolate_settings(monkeypatch)
    monkeypatch.setenv("A0_SET_mcp_server_token", ENV_TOKEN)
    monkeypatch.setattr(settings_module, "create_auth_token", lambda: "derived-token")

    current = settings_module.get_default_settings()
    previous = {**current, "mcp_server_token": "old-derived-hash"}

    received_mcp: list[str] = []
    received_a2a: list[str] = []

    class FakeDeferredTask:
        def start_task(self, func, *args, **kwargs):
            asyncio.run(func(*args, **kwargs))
            return self

    class FakePrintStyle:
        def __init__(self, *args, **kwargs):
            pass

        def print(self, *args, **kwargs):
            pass

    class FakeMcpProxy:
        @classmethod
        def get_instance(cls):
            return cls()

        def reconfigure(self, token=None):
            received_mcp.append(token)

    class FakeA2aProxy:
        @classmethod
        def get_instance(cls):
            return cls()

        def reconfigure(self, token=None):
            received_a2a.append(token)

    agent_stub = ModuleType("agent")
    agent_stub.Agent = object

    class FakeAgentContext:
        @staticmethod
        def all():
            return []

    agent_stub.AgentContext = FakeAgentContext

    initialize_stub = ModuleType("initialize")
    initialize_stub.initialize_agent = lambda override_settings=None: None

    mcp_server_stub = ModuleType("helpers.mcp_server")
    mcp_server_stub.DynamicMcpProxy = FakeMcpProxy
    fasta2a_stub = ModuleType("helpers.fasta2a_server")
    fasta2a_stub.DynamicA2AProxy = FakeA2aProxy

    monkeypatch.setitem(sys.modules, "agent", agent_stub)
    monkeypatch.setitem(sys.modules, "initialize", initialize_stub)
    monkeypatch.setitem(sys.modules, "helpers.mcp_server", mcp_server_stub)
    monkeypatch.setitem(sys.modules, "helpers.fasta2a_server", fasta2a_stub)
    monkeypatch.setattr(settings_module, "_settings", current)
    monkeypatch.setattr(settings_module, "_apply_timezone_setting", lambda *args, **kwargs: None)
    monkeypatch.setattr(settings_module.defer, "DeferredTask", FakeDeferredTask)
    monkeypatch.setattr(settings_module, "PrintStyle", FakePrintStyle)
    monkeypatch.setattr(settings_module.NotificationManager, "send_notification", lambda **kwargs: None)

    settings_module._apply_settings(previous)

    # proxies must receive the normalized (env-overridden) token, not a fresh hash
    assert received_mcp == [ENV_TOKEN]
    assert received_a2a == [ENV_TOKEN]
