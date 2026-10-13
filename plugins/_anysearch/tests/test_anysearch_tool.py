from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from helpers import yaml as yaml_helper
from plugins._anysearch.helpers.anysearch_client import AnySearchError
from plugins._anysearch.tools import anysearch as anysearch_tool

# plugins/_anysearch/tests/test_anysearch_tool.py -> tests -> _anysearch ->
# plugins -> repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_SRC_DIR = Path(__file__).resolve().parents[1]


class _FakeAgent:
    """Minimal stand-in for the real Agent: only what Tool/execute touch."""

    agent_name = "test-agent"

    async def handle_intervention(self, message):
        return None


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def search(self, query, **kwargs):
        self.calls.append(("search", query, kwargs))
        if query == "boom":
            raise AnySearchError("simulated backend failure")
        return {
            "results": [
                {"title": "T", "url": "https://example.com", "content": "body"}
            ]
        }

    async def batch_search(self, queries, **kwargs):
        self.calls.append(("batch_search", queries, kwargs))
        return [
            {"query": "a", "ok": True, "data": {"results": [{"title": "A", "url": "u", "content": "c"}]}},
            {"query": "b", "ok": False, "error": "simulated failure"},
        ]

    async def get_sub_domains(self, domains):
        self.calls.append(("get_sub_domains", domains))
        return {
            "domains": [
                {
                    "domain": "finance",
                    "description": "Financial data",
                    "sub_domains": [
                        {
                            "sub_domain": "finance.quote",
                            "description": "Stock quotes",
                            "params": {"symbol": {"description": "Ticker", "required": True}},
                        }
                    ],
                }
            ]
        }

    async def extract(self, url):
        self.calls.append(("extract", url))
        return {"url": url, "title": "Example", "content": "extracted body text"}


def _make_tool(monkeypatch, fake_client: _FakeClient, config: dict | None = None) -> anysearch_tool.AnySearch:
    monkeypatch.setattr(anysearch_tool, "_build_client", lambda agent, config: fake_client)
    monkeypatch.setattr(anysearch_tool, "_plugin_config", lambda agent: config or {})
    tool = anysearch_tool.AnySearch.__new__(anysearch_tool.AnySearch)
    tool.agent = _FakeAgent()
    tool.name = "anysearch"
    return tool


@pytest.mark.asyncio
async def test_search_action_formats_results(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    response = await tool.execute(action="search", query="golang release")
    assert "T" in response.message
    assert "https://example.com" in response.message
    assert response.break_loop is False


@pytest.mark.asyncio
async def test_search_action_defaults_when_action_omitted(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    response = await tool.execute(query="golang release")
    assert fake_client.calls[0][0] == "search"
    assert "T" in response.message


@pytest.mark.asyncio
async def test_search_failure_returns_clear_error_not_exception(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    response = await tool.execute(action="search", query="boom")
    assert "failed" in response.message.lower()
    assert "simulated backend failure" in response.message
    assert response.break_loop is False


@pytest.mark.asyncio
async def test_vertical_search_forwards_tag_domain_and_params(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    await tool.execute(
        action="search",
        query="AAPL stock price",
        domain="finance",
        tag="finance.quote",
        sub_domain_params={"symbol": "AAPL"},
    )
    _, query, kwargs = fake_client.calls[0]
    assert query == "AAPL stock price"
    assert kwargs["domain"] == "finance"
    assert kwargs["tag"] == "finance.quote"
    # both aliases are forwarded untouched; the client resolves/validates them
    assert kwargs["sub_domain_params"] == {"symbol": "AAPL"}
    assert kwargs["params"] is None


@pytest.mark.asyncio
async def test_search_uses_configured_default_max_results_when_omitted(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": 3})
    await tool.execute(action="search", query="golang")
    _, _, kwargs = fake_client.calls[0]
    assert kwargs["max_results"] == 3


@pytest.mark.asyncio
async def test_search_explicit_max_results_overrides_config(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": 3})
    await tool.execute(action="search", query="golang", max_results=7)
    _, _, kwargs = fake_client.calls[0]
    assert kwargs["max_results"] == 7


@pytest.mark.asyncio
async def test_search_explicit_max_results_null_uses_configured_default(monkeypatch):
    # An explicit JSON `null` (Python None) must be treated exactly like an
    # omitted max_results, not passed through as a literal None to the
    # client — same precedence as a missing key.
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": 3})
    await tool.execute(action="search", query="golang", max_results=None)
    _, _, kwargs = fake_client.calls[0]
    assert kwargs["max_results"] == 3


@pytest.mark.asyncio
async def test_search_falls_back_to_hardcoded_default_without_config(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={})
    await tool.execute(action="search", query="golang")
    _, _, kwargs = fake_client.calls[0]
    assert kwargs["max_results"] == anysearch_tool.DEFAULT_MAX_RESULTS


@pytest.mark.asyncio
async def test_get_sub_domains_action(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    response = await tool.execute(action="get_sub_domains", domains=["finance"])
    assert "finance" in response.message
    assert "finance.quote" in response.message
    assert "symbol" in response.message  # required param surfaced


@pytest.mark.asyncio
async def test_batch_search_ordering_and_partial_failure_surfaced(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    response = await tool.execute(
        action="batch_search", queries=[{"query": "a"}, {"query": "b"}]
    )
    text = response.message
    assert text.index("[1] a") < text.index("[2] b")
    assert "Error: simulated failure" in text


@pytest.mark.asyncio
async def test_batch_search_rejects_over_limit_without_calling_client(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    too_many = [{"query": f"q{i}"} for i in range(10)]
    response = await tool.execute(action="batch_search", queries=too_many)
    assert "at most" in response.message.lower()
    assert fake_client.calls == []


@pytest.mark.asyncio
async def test_batch_search_item_without_max_results_uses_configured_default(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": 3})
    await tool.execute(action="batch_search", queries=[{"query": "a"}, {"query": "b"}])
    _, sent_queries, _ = fake_client.calls[0]
    assert [q["max_results"] for q in sent_queries] == [3, 3]


@pytest.mark.asyncio
async def test_batch_search_item_with_explicit_max_results_overrides_config(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": 3})
    await tool.execute(
        action="batch_search",
        queries=[{"query": "a", "max_results": 7}, {"query": "b"}],
    )
    _, sent_queries, _ = fake_client.calls[0]
    assert sent_queries[0]["max_results"] == 7
    assert sent_queries[1]["max_results"] == 3


@pytest.mark.asyncio
async def test_batch_search_item_with_explicit_max_results_null_uses_configured_default(monkeypatch):
    # An item with an explicit `"max_results": null` must resolve to the
    # configured default, exactly like a missing key — not fall through to
    # AnySearchClient's hardcoded default of 10.
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": 3})
    await tool.execute(
        action="batch_search",
        queries=[{"query": "a", "max_results": None}, {"query": "b"}],
    )
    _, sent_queries, _ = fake_client.calls[0]
    assert [q["max_results"] for q in sent_queries] == [3, 3]


@pytest.mark.asyncio
async def test_batch_search_non_dict_item_passed_through_untouched_to_client(monkeypatch):
    # A malformed (non-dict) item must be passed through unchanged, not
    # crash the max_results-injection step, so the client can report it as
    # an isolated per-item error while its siblings still run.
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": 3})
    await tool.execute(action="batch_search", queries=["not-a-dict", {"query": "ok"}])
    _, sent_queries, _ = fake_client.calls[0]
    assert sent_queries[0] == "not-a-dict"
    assert sent_queries[1] == {"query": "ok", "max_results": 3}


@pytest.mark.asyncio
async def test_batch_search_does_not_mutate_caller_input(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": 3})
    original_item = {"query": "a"}
    queries = [original_item]
    await tool.execute(action="batch_search", queries=queries)
    # The caller's original dict and list must be untouched: no
    # max_results key injected in place, same object identity preserved.
    assert "max_results" not in original_item
    assert queries[0] is original_item


@pytest.mark.asyncio
async def test_batch_search_batch_level_client_error_reported_without_raising(monkeypatch):
    class _RejectingClient(_FakeClient):
        async def batch_search(self, queries, **kwargs):
            self.calls.append(("batch_search", queries, kwargs))
            raise AnySearchError("queries must be a list, got dict")

    fake_client = _RejectingClient()
    tool = _make_tool(monkeypatch, fake_client)
    response = await tool.execute(action="batch_search", queries=[{"query": "x"}])
    assert "failed" in response.message.lower()
    assert "queries must be a list" in response.message
    assert response.break_loop is False


@pytest.mark.asyncio
async def test_extract_action_includes_untrusted_content_notice(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    response = await tool.execute(action="extract", url="https://example.com/page")
    assert "untrusted external page data" in response.message
    assert "not instructions" in response.message
    assert "extracted body text" in response.message


@pytest.mark.asyncio
async def test_unknown_action_returns_error_without_calling_client(monkeypatch):
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client)
    response = await tool.execute(action="delete_everything")
    assert "unknown action" in response.message.lower()
    assert fake_client.calls == []


@pytest.mark.asyncio
async def test_malformed_config_max_results_reported_as_failure_not_silent_fallback(monkeypatch):
    # A hand-edited, non-numeric plugin-config max_results must be
    # surfaced as a clear failure, consistent with how a non-numeric
    # model-supplied max_results and a malformed timeout are both handled
    # — not silently substituted with DEFAULT_MAX_RESULTS.
    fake_client = _FakeClient()
    tool = _make_tool(monkeypatch, fake_client, config={"max_results": "not-a-number"})
    response = await tool.execute(action="search", query="golang")
    assert "failed" in response.message.lower()
    assert fake_client.calls == []


@pytest.mark.asyncio
async def test_malformed_config_timeout_reported_as_failure_not_unhandled_exception(monkeypatch):
    # A hand-edited, non-numeric `timeout` in plugin config previously
    # crashed AnySearchClient's own __init__ (float(timeout)) *before*
    # execute()'s try/except was entered, producing an unhandled
    # ValueError instead of the graceful failure Response the tool's own
    # docstring promises. _build_client must now run inside the try.
    monkeypatch.setattr(
        anysearch_tool, "_plugin_config", lambda agent: {"timeout": "not-a-number"}
    )
    monkeypatch.setattr("models.get_api_key", lambda name: None)
    tool = anysearch_tool.AnySearch.__new__(anysearch_tool.AnySearch)
    tool.agent = _FakeAgent()
    tool.name = "anysearch"

    response = await tool.execute(action="search", query="golang")

    assert "failed" in response.message.lower()
    assert response.break_loop is False


@pytest.mark.asyncio
async def test_plugin_config_resolution_failure_reported_as_failure_not_unhandled_exception(monkeypatch):
    # A malformed plugin config.json/default_config.yaml, or a config-hook
    # failure, would previously crash execute() before it ever entered the
    # try (config was resolved at the top of execute(), outside the
    # try/except). _plugin_config() is now called INSIDE the try, so its
    # own failure is reported the same graceful way as any other AnySearch
    # failure.
    def _raise_config_error(agent):
        raise RuntimeError("simulated malformed plugin config.json")

    monkeypatch.setattr(anysearch_tool, "_plugin_config", _raise_config_error)
    tool = anysearch_tool.AnySearch.__new__(anysearch_tool.AnySearch)
    tool.agent = _FakeAgent()
    tool.name = "anysearch"

    response = await tool.execute(action="search", query="golang")

    assert "failed" in response.message.lower()
    assert response.break_loop is False


@pytest.mark.asyncio
async def test_config_resolved_exactly_once_and_shared_across_build_client_and_action(monkeypatch):
    # Regression guard: base_url/timeout (read by _build_client) and the
    # configured max_results default (read by _do_search via
    # _resolve_max_results) must come from the SAME resolved config object,
    # and _plugin_config must be called exactly once per execute() call —
    # not once for the client and again for the action handler.
    calls = []

    def _tracking_plugin_config(agent):
        calls.append(1)
        return {"max_results": 3}

    fake_client = _FakeClient()
    monkeypatch.setattr(anysearch_tool, "_plugin_config", _tracking_plugin_config)
    monkeypatch.setattr(anysearch_tool, "_build_client", lambda agent, config: fake_client)
    tool = anysearch_tool.AnySearch.__new__(anysearch_tool.AnySearch)
    tool.agent = _FakeAgent()
    tool.name = "anysearch"

    await tool.execute(action="search", query="golang")

    assert len(calls) == 1
    _, _, kwargs = fake_client.calls[0]
    assert kwargs["max_results"] == 3


def test_plugin_is_disabled_by_default():
    """Manifest-level check: always_enabled must be False so the plugin can
    be toggled off. See test_real_plugin_discovery_respects_toggle_state for
    the actual runtime proof that it starts inactive."""
    plugin_yaml_path = Path(__file__).resolve().parents[1] / "plugin.yaml"
    manifest = yaml_helper.loads(plugin_yaml_path.read_text())
    assert manifest.get("always_enabled", False) is False


def test_plugin_ships_disabled_toggle_marker():
    """Agent Zero plugins are ACTIVE BY DEFAULT unless a `.toggle-0` marker
    is present (confirmed by reading helpers/plugins.py:
    get_enabled_plugins() starts `enabled = True` and only a `.toggle-0`
    file flips it off). always_enabled: false alone does NOT make a plugin
    opt-in — it only means it *can* be toggled. This plugin must ship a
    `.toggle-0` file (same pattern as plugins/_infection_check) so it does
    not activate on a fresh install."""
    plugin_dir = Path(__file__).resolve().parents[1]
    assert (plugin_dir / ".toggle-0").exists()
    assert not (plugin_dir / ".toggle-1").exists()


def test_search_engine_tool_unchanged_and_independent_of_anysearch():
    # The default SearXNG-based tool must not import or depend on AnySearch,
    # and must keep its existing single-purpose searxng_search behavior.
    from tools import search_engine

    source = Path(search_engine.__file__).read_text()
    assert "anysearch" not in source.lower()
    assert hasattr(search_engine.SearchEngine, "searxng_search")


def _build_isolated_agent_zero_tree(tmp_path: Path, plugin_name: str = "_anysearch") -> None:
    """Create a minimal on-disk tree under `tmp_path` that mirrors just
    enough of the real repository layout for helpers.plugins discovery to
    operate against it entirely in isolation:

    - `plugins/<plugin_name>/` — a copy of the real plugin's `plugin.yaml`,
      `.toggle-0`, `tools/`, and `prompts/` (the only pieces discovery
      reads: metadata, the shipped toggle marker, and the tool/prompt files
      whose presence get_enabled_plugin_paths reports).
    - `usr/plugins/` — created empty. get_plugins_list() calls
      Path(root).iterdir() on BOTH plugin roots unconditionally, so this
      must exist even before any override is written into it.

    Nothing under the real repository's `usr/` is read or written by this
    helper or by tests that use it.
    """
    plugins_root = tmp_path / "plugins"
    usr_plugins_root = tmp_path / "usr" / "plugins"
    usr_plugins_root.mkdir(parents=True)

    dest = plugins_root / plugin_name
    dest.mkdir(parents=True)
    shutil.copy(PLUGIN_SRC_DIR / "plugin.yaml", dest / "plugin.yaml")
    shutil.copy(PLUGIN_SRC_DIR / ".toggle-0", dest / ".toggle-0")
    shutil.copytree(PLUGIN_SRC_DIR / "tools", dest / "tools")
    shutil.copytree(PLUGIN_SRC_DIR / "prompts", dest / "prompts")


@pytest.fixture
def isolated_plugin_env(tmp_path, monkeypatch):
    """Point helpers.files at an isolated `tmp_path` tree — following Agent
    Zero's own testing convention of monkeypatching `helpers.files._base_dir`
    (see e.g. tests/test_model_config_api_keys.py,
    tests/test_file_browser_archives.py) — containing only a copy of the
    bundled `_anysearch` plugin. Discovery tests using this fixture never
    read or write the real repository's `usr/plugins/_anysearch/` developer
    state, so a developer's own local toggle override is never at risk.

    Clears the plugin caches before and after so no cached result leaks
    between this isolated tree and the real repository tree used by other
    tests in the suite.
    """
    from helpers import cache, files

    _build_isolated_agent_zero_tree(tmp_path)
    monkeypatch.setattr(files, "_base_dir", str(tmp_path))
    cache.clear_all()
    try:
        yield tmp_path
    finally:
        cache.clear_all()


def test_isolated_discovery_bundled_toggle_0_disables_by_default(isolated_plugin_env):
    """A. With only the shipped `.toggle-0` marker present (no override),
    the `anysearch` tool and prompt are NOT discoverable via the real
    helpers.plugins.get_enabled_plugins / get_enabled_plugin_paths path."""
    from helpers import plugins as plugins_helper

    plugin_name = "_anysearch"
    enabled = plugins_helper.get_enabled_plugins(None)
    assert plugin_name not in enabled

    tool_paths = plugins_helper.get_enabled_plugin_paths(None, "tools", "*.py")
    assert not any(Path(p).name == "anysearch.py" for p in tool_paths)

    prompt_paths = plugins_helper.get_enabled_plugin_paths(
        None, "prompts", "agent.system.tool.*.md"
    )
    assert not any(p.endswith("agent.system.tool.anysearch.md") for p in prompt_paths)


def test_isolated_discovery_temporary_toggle_1_override_enables(isolated_plugin_env):
    """B. Writing the same `.toggle-1` override the Plugins panel writes,
    under the ISOLATED `usr/plugins/_anysearch/` (never the real one),
    makes the tool and prompt discoverable."""
    from helpers import cache, files, plugins as plugins_helper

    plugin_name = "_anysearch"
    override_dir = files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, plugin_name)
    enabled_marker = files.get_abs_path(override_dir, plugins_helper.ENABLED_FILE_NAME)
    files.write_file(enabled_marker, "")
    cache.clear_all()

    enabled = plugins_helper.get_enabled_plugins(None)
    assert plugin_name in enabled

    tool_paths = plugins_helper.get_enabled_plugin_paths(None, "tools", "*.py")
    assert any(Path(p).name == "anysearch.py" for p in tool_paths)

    prompt_paths = plugins_helper.get_enabled_plugin_paths(
        None, "prompts", "agent.system.tool.*.md"
    )
    assert any(p.endswith("agent.system.tool.anysearch.md") for p in prompt_paths)

    # Written into the isolated tmp tree, not the real repository's usr/.
    assert Path(enabled_marker).is_relative_to(override_dir)
    assert Path(enabled_marker).is_relative_to(str(files.get_base_dir()))


def test_isolated_discovery_disabling_again_removes_tool_and_prompt(isolated_plugin_env):
    """Enable via a `.toggle-1` user override, then disable the way the
    Plugins panel does (override replaced by `.toggle-0`): the tool and
    prompt must disappear from discovery again."""
    from helpers import cache, files, plugins as plugins_helper

    plugin_name = "_anysearch"
    override_dir = files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, plugin_name)
    enabled_marker = files.get_abs_path(override_dir, plugins_helper.ENABLED_FILE_NAME)
    disabled_marker = files.get_abs_path(override_dir, plugins_helper.DISABLED_FILE_NAME)

    files.write_file(enabled_marker, "")
    cache.clear_all()
    assert plugin_name in plugins_helper.get_enabled_plugins(None)

    files.delete_file(enabled_marker)
    files.write_file(disabled_marker, "")
    cache.clear_all()

    assert plugin_name not in plugins_helper.get_enabled_plugins(None)
    tool_paths = plugins_helper.get_enabled_plugin_paths(None, "tools", "*.py")
    assert not any(Path(p).name == "anysearch.py" for p in tool_paths)
    prompt_paths = plugins_helper.get_enabled_plugin_paths(
        None, "prompts", "agent.system.tool.*.md"
    )
    assert not any(p.endswith("agent.system.tool.anysearch.md") for p in prompt_paths)


def test_isolated_discovery_preexisting_override_content_survives_exactly(isolated_plugin_env):
    """C. A pre-existing override's exact content (not just its presence)
    round-trips untouched by running discovery — the regression Finding A
    originally guarded against, now proven without ever touching real
    developer state."""
    from helpers import cache, files, plugins as plugins_helper

    plugin_name = "_anysearch"
    override_dir = files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, plugin_name)
    enabled_marker = files.get_abs_path(override_dir, plugins_helper.ENABLED_FILE_NAME)
    sentinel_content = "developer-pre-existing-sentinel"
    files.write_file(enabled_marker, sentinel_content)
    cache.clear_all()

    enabled = plugins_helper.get_enabled_plugins(None)
    assert plugin_name in enabled

    # Discovery is read-only with respect to the override marker: content
    # must be exactly what was written, byte-for-byte.
    assert files.exists(enabled_marker)
    assert files.read_file(enabled_marker) == sentinel_content


def test_isolated_discovery_never_touches_real_repository_usr_dir(tmp_path, monkeypatch):
    """D. No path under the REAL repository's usr/ is written or deleted by
    running the isolated discovery checks above. Proven by snapshotting the
    real, unpatched path directly with plain pathlib (never through
    helpers.files, which this test also points at tmp_path) before and
    after exercising the same enable/discover flow as tests A-C."""
    real_override_dir = PROJECT_ROOT / "usr" / "plugins" / "_anysearch"

    def _snapshot_real_dir() -> dict[Path, bytes] | None:
        if not real_override_dir.exists():
            return None
        return {
            p.relative_to(real_override_dir): p.read_bytes()
            for p in real_override_dir.rglob("*")
            if p.is_file()
        }

    pre_snapshot = _snapshot_real_dir()

    from helpers import cache, files, plugins as plugins_helper

    _build_isolated_agent_zero_tree(tmp_path)
    monkeypatch.setattr(files, "_base_dir", str(tmp_path))
    cache.clear_all()
    try:
        plugin_name = "_anysearch"
        override_dir = files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, plugin_name)
        files.write_file(
            files.get_abs_path(override_dir, plugins_helper.ENABLED_FILE_NAME), ""
        )
        cache.clear_all()
        assert plugin_name in plugins_helper.get_enabled_plugins(None)
    finally:
        cache.clear_all()

    # The monkeypatch is still active here (test body, not teardown), so
    # this reads the REAL absolute path directly, bypassing the patched
    # helpers.files entirely, to prove it was never touched.
    post_snapshot = _snapshot_real_dir()
    assert post_snapshot == pre_snapshot


# --- native (Responses) and classic tool-path discovery ------------------------


class _DiscoveryAgent:
    """Minimal agent shape used by helpers.responses_tools / tool_policy:
    prompts are rendered through the real helpers.files template path."""

    def __init__(self):
        from types import SimpleNamespace

        self.config = SimpleNamespace(profile="default")
        self.context = SimpleNamespace(get_data=lambda *a, **k: None)

    def read_prompt(self, file, **kwargs):
        from helpers import files, subagents

        return files.read_prompt_file(file, _directories=subagents.get_paths(self, "prompts"), **kwargs)

    def get_data(self, key):
        return None


def _native_tools(monkeypatch):
    from helpers import responses_tools

    monkeypatch.setattr(responses_tools, "_mcp_tools", lambda agent: [])
    monkeypatch.setattr(responses_tools, "_vision_tool_prompt", lambda agent: "")
    tools, name_map = responses_tools.build_responses_function_tools(_DiscoveryAgent())
    return {tool["name"]: tool for tool in tools}, name_map


def _classic_tool_prompts(agent):
    import os

    from helpers import files, subagents, tool_policy

    tool_files = files.get_unique_filenames_in_dirs(subagents.get_paths(agent, "prompts"), "agent.system.tool.*.md")
    prompts = [(os.path.basename(f), agent.read_prompt(os.path.basename(f))) for f in tool_files]
    return [p for p in tool_policy.filter_tool_prompts(agent, prompts) if p]


def _set_toggle(enabled: bool):
    from helpers import cache, files, plugins as plugins_helper

    override_dir = files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, "_anysearch")
    on = files.get_abs_path(override_dir, plugins_helper.ENABLED_FILE_NAME)
    off = files.get_abs_path(override_dir, plugins_helper.DISABLED_FILE_NAME)
    for marker in (on, off):
        if files.exists(marker):
            files.delete_file(marker)
    files.write_file(on if enabled else off, "")
    cache.clear_all()


def test_native_responses_schema_is_structured_not_permissive(isolated_plugin_env, monkeypatch):
    from helpers import responses_tools

    _set_toggle(True)
    tools, name_map = _native_tools(monkeypatch)
    assert name_map["anysearch"] == "anysearch"
    schema = tools["anysearch"]["parameters"]
    assert schema != responses_tools._permissive_schema()
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    props = schema["properties"]
    assert props["action"]["enum"] == ["search", "batch_search", "get_sub_domains", "extract"]
    for field in ("query", "queries", "domains", "domain", "url", "tag", "sub_domain", "params", "sub_domain_params", "language"):
        assert field in props, field
    assert props["zone"]["enum"] == ["cn", "intl"]
    assert (props["max_results"]["type"], props["max_results"]["minimum"], props["max_results"]["maximum"]) == ("integer", 1, 10)
    assert (props["queries"]["minItems"], props["queries"]["maxItems"]) == (1, 5)
    item = props["queries"]["items"]
    assert item["additionalProperties"] is False and item["required"] == ["query"]
    assert {"query", "max_results", "tag", "sub_domain", "domain", "params", "sub_domain_params", "zone", "language"} <= set(item["properties"])
    domain_forms = props["domains"]["anyOf"]
    assert {"type": "string", "minLength": 1} in domain_forms
    assert any(f.get("type") == "array" and f.get("maxItems") == 5 for f in domain_forms)
    # action-specific requirements stay runtime-enforced, never global
    assert "required" not in schema
    # no credential or config fields leak into the model-facing schema
    flat = json_dumps_lower(schema)
    for forbidden in ("api_key", "apikey", "authorization", "bearer", "base_url", "timeout", "password", "token"):
        assert forbidden not in flat, forbidden


def json_dumps_lower(value):
    import json

    return json.dumps(value).lower()


def test_native_and_classic_paths_follow_plugin_toggle(isolated_plugin_env, monkeypatch):
    from helpers import subagents

    agent = _DiscoveryAgent()

    def discovered():
        tools, _ = _native_tools(monkeypatch)
        classic = any("### anysearch" in p for p in _classic_tool_prompts(agent))
        impl = bool(subagents.get_paths(agent, "tools", "anysearch.py"))
        return "anysearch" in tools, classic, impl

    assert discovered() == (False, False, False)  # shipped .toggle-0
    _set_toggle(True)
    assert discovered() == (True, True, True)
    _set_toggle(False)
    assert discovered() == (False, False, False)
    _set_toggle(True)
    assert discovered() == (True, True, True)


def test_classic_prompt_renders_with_embedded_schema(isolated_plugin_env):
    from helpers import responses_tools

    _set_toggle(True)
    prompt = next(p for p in _classic_tool_prompts(_DiscoveryAgent()) if "### anysearch" in p)
    assert "Input schema for tool_args:" in prompt
    assert "{{" not in prompt
    schema = responses_tools._schema_from_embedded_json(prompt)
    assert schema["properties"]["action"]["enum"][0] == "search"
    # the fenced JSON example still projects to a native arguments example
    assert "Arguments example" in responses_tools._native_tool_description(prompt, "anysearch")
