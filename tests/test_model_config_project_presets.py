from __future__ import annotations

import json
import os
import sys
import threading
import types
from pathlib import Path

import pytest
import yaml
from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.setdefault("giturlparse", types.SimpleNamespace(parse=lambda *args, **kwargs: None))


class _DummyObserver:
    def __init__(self):
        self._alive = False

    def is_alive(self):
        return self._alive

    def start(self):
        self._alive = True

    def stop(self):
        self._alive = False

    def join(self, *args, **kwargs):
        return None

    def unschedule_all(self):
        return None

    def schedule(self, *args, **kwargs):
        return None


watchdog = types.ModuleType("watchdog")
watchdog.observers = types.SimpleNamespace(Observer=_DummyObserver)
watchdog.events = types.SimpleNamespace(FileSystemEventHandler=object)
sys.modules.setdefault("watchdog", watchdog)
sys.modules.setdefault("watchdog.observers", watchdog.observers)
sys.modules.setdefault("watchdog.events", watchdog.events)


def _copy_extension_fixture(plugin_dir: Path, relative_path: str) -> None:
    source = PROJECT_ROOT / "plugins" / "_model_config" / relative_path
    target = plugin_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _clear_runtime_caches():
    from helpers import cache, modules

    cache.clear("*(extensions)*")
    cache.clear("*(plugins)*")
    modules.purge_namespace("usr.plugins")


def _prepare_a0_tree(monkeypatch, tmp_path: Path):
    from helpers import files, plugins

    monkeypatch.setattr(files, "_base_dir", str(tmp_path))
    monkeypatch.setattr(
        plugins,
        "call_plugin_hook",
        lambda plugin_name, hook_name, default=None, **kwargs: default,
    )

    plugin_dir = tmp_path / "plugins" / "_model_config"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        "name: _model_config\nper_project_config: true\nper_agent_config: true\n",
        encoding="utf-8",
    )
    fallback_path = plugin_dir / "mode_presets_fallback.yaml"
    fallback_path.write_text(
        """
- name: Default
  chat:
    provider: openrouter
    name: default-chat
  utility:
    provider: openrouter
    name: default-utility
  embedding:
    provider: huggingface
    name: default-embedding
- name: Balance
  chat:
    provider: openrouter
    name: balanced-chat
""".lstrip(),
        encoding="utf-8",
    )
    (plugin_dir / "default_config.yaml").write_text(
        """
model_preset: Default
""".lstrip(),
        encoding="utf-8",
    )
    _copy_extension_fixture(
        plugin_dir,
        "extensions/python/_functions/helpers/projects/load_project_extended_data/end/_10_model_config.py",
    )
    _copy_extension_fixture(
        plugin_dir,
        "extensions/python/_functions/helpers/projects/save_project_extended_data/start/_10_model_config.py",
    )
    (tmp_path / "usr" / "plugins").mkdir(parents=True)
    (tmp_path / "usr" / "projects").mkdir(parents=True)
    _clear_runtime_caches()


def _add_project_extra_plugin(tmp_path: Path):
    plugin_dir = tmp_path / "plugins" / "_project_extra"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        "name: _project_extra\n",
        encoding="utf-8",
    )
    load_ext = (
        plugin_dir
        / "extensions"
        / "python"
        / "_functions"
        / "helpers"
        / "projects"
        / "load_project_extended_data"
        / "end"
        / "_20_project_extra.py"
    )
    load_ext.parent.mkdir(parents=True, exist_ok=True)
    load_ext.write_text(
        """
from helpers.extension import Extension


class ProjectExtraLoader(Extension):
    def execute(self, data: dict = {}, **kwargs):
        result = data.get("result")
        if not isinstance(result, dict):
            result = {}
            data["result"] = result
        args = data.get("args") or ()
        project_name = args[0] if args else data.get("kwargs", {}).get("name", "")
        result["extra"] = {"loaded_for": str(project_name or ""), "enabled": True}
""".lstrip(),
        encoding="utf-8",
    )
    save_ext = (
        plugin_dir
        / "extensions"
        / "python"
        / "_functions"
        / "helpers"
        / "projects"
        / "save_project_extended_data"
        / "start"
        / "_20_project_extra.py"
    )
    save_ext.parent.mkdir(parents=True, exist_ok=True)
    save_ext.write_text(
        """
import json
from helpers import files
from helpers.extension import Extension


class ProjectExtraSaver(Extension):
    def execute(self, data: dict = {}, **kwargs):
        args = data.get("args") or ()
        call_kwargs = data.get("kwargs") or {}
        project_name = args[0] if args else call_kwargs.get("name", "")
        project_data = args[1] if len(args) > 1 else call_kwargs.get("project_data")
        if not isinstance(project_data, dict) or "extra" not in project_data:
            return
        forbidden = {"title", "mcp_servers", "git_token"} & set(project_data)
        if forbidden:
            raise AssertionError(f"core/transient keys leaked to extension save: {sorted(forbidden)}")
        path = files.get_abs_path(
            "usr",
            "projects",
            str(project_name or ""),
            ".a0proj",
            "extra_saved.json",
        )
        files.write_file(
            path,
            json.dumps(
                {"project": str(project_name or ""), "extra": project_data["extra"]},
                sort_keys=True,
            ),
        )
""".lstrip(),
        encoding="utf-8",
    )
    _clear_runtime_caches()


def _add_project_conflict_plugin(tmp_path: Path):
    plugin_dir = tmp_path / "plugins" / "_project_conflict"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        "name: _project_conflict\n",
        encoding="utf-8",
    )
    load_ext = (
        plugin_dir
        / "extensions"
        / "python"
        / "_functions"
        / "helpers"
        / "projects"
        / "load_project_extended_data"
        / "end"
        / "_30_project_conflict.py"
    )
    load_ext.parent.mkdir(parents=True, exist_ok=True)
    load_ext.write_text(
        """
from helpers.extension import Extension


class ProjectConflictLoader(Extension):
    def execute(self, data: dict = {}, **kwargs):
        result = data.get("result")
        if not isinstance(result, dict):
            result = {}
            data["result"] = result
        result["title"] = "Plugin-owned title"
""".lstrip(),
        encoding="utf-8",
    )
    _clear_runtime_caches()


def test_global_presets_require_immutable_default_and_save_behavior(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    assert model_config.get_presets()[0]["name"] == "Default"

    model_config.save_presets(
        [
            model_config.get_presets()[0],
            {
                "name": "Global One",
                "scope": "project",
                "project_name": "ignored",
                "chat": {"provider": "openai", "name": "gpt-test", "_kwargs_text": ""},
            }
        ]
    )

    presets = model_config.get_presets()
    assert presets[0]["name"] == "Default"
    assert presets[1] == {
        "name": "Global One",
        "chat": {"provider": "openai", "name": "gpt-test"},
    }

    saved_path = tmp_path / "usr" / "plugins" / "_model_config" / "presets.yaml"
    assert "scope:" not in saved_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="cannot be deleted or renamed"):
        model_config.save_presets([])

    assert model_config.reset_presets()[0]["name"] == "Default"


def test_global_presets_parse_once_until_a_source_file_changes(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    calls = []
    load = model_config._load_global_presets
    monkeypatch.setattr(
        model_config, "_load_global_presets", lambda **kwargs: calls.append(1) or load(**kwargs)
    )

    model_config.get_presets()[0]["name"] = "mutated"
    assert model_config.get_presets()[0]["name"] == "Default"
    assert len(calls) == 1

    model_config.save_presets(
        [
            model_config.get_presets()[0],
            {"name": "Added", "chat": {"provider": "openai", "name": "gpt-test"}},
        ]
    )
    assert [p["name"] for p in model_config.get_presets()] == ["Default", "Added"]
    assert len(calls) == 2

    # out-of-band edits invalidate through the file signature
    path = tmp_path / "usr" / "plugins" / "_model_config" / "presets.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("Added", "Edited"), encoding="utf-8")
    os.utime(path, ns=(1, 1))
    assert [p["name"] for p in model_config.get_presets()] == ["Default", "Edited"]
    assert len(calls) == 3


@pytest.mark.parametrize("source", ["presets", "fallback", "legacy"])
def test_global_presets_recover_after_source_read_failure(monkeypatch, tmp_path, source):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import cache, files
    from plugins._model_config.helpers import model_config

    user_dir = tmp_path / "usr" / "plugins" / "_model_config"
    user_dir.mkdir()
    paths = {
        "presets": user_dir / "presets.yaml",
        "fallback": tmp_path / "plugins" / "_model_config" / "mode_presets_fallback.yaml",
        "legacy": user_dir / "config.json",
    }
    paths["presets"].write_text(
        "- name: Default\n- name: Custom\n  chat: {provider: openai, name: custom-chat}\n",
        encoding="utf-8",
    )
    paths["legacy"].write_text(
        json.dumps({"utility_model": {"provider": "openai", "name": "legacy-utility"}}),
        encoding="utf-8",
    )
    expected = model_config.get_presets()
    assert expected[0]["chat"]["name"] == "default-chat"
    assert expected[0]["utility"]["name"] == "legacy-utility"
    assert expected[1]["name"] == "Custom"
    cache.clear(model_config.PRESETS_CACHE_AREA)

    reader_name = "read_file_json" if source == "legacy" else "read_file"
    read = getattr(files, reader_name)

    def fail_read(path, *args, **kwargs):
        if Path(path) == paths[source]:
            raise PermissionError("temporary read failure")
        return read(path, *args, **kwargs)

    with monkeypatch.context() as failing:
        failing.setattr(files, reader_name, fail_read)
        assert model_config.get_presets() != expected

    # Recovery must not require editing the files or clearing the cache.
    assert model_config.get_presets() == expected


def test_project_scope_selects_global_presets_only(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import projects, plugins
    from plugins._model_config.helpers import model_config

    projects.create_project("demo", {"title": "Demo"})
    plugins.save_plugin_config("_model_config", "demo", "", {"model_preset": "Balance"})

    assert model_config.get_configured_preset_name(project_name="demo") == "Balance"
    assert model_config.resolve_preset("Balance", scope="global")["chat"]["name"] == "balanced-chat"
    assert model_config.resolve_preset("Balance", scope="project", project_name="demo") is None
    with pytest.raises(ValueError, match="no longer supported"):
        model_config.save_presets(model_config.get_presets(), project_name="demo")


def test_selected_preset_resolves_complete_runtime_config_from_default(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import plugins
    from plugins._model_config.helpers import model_config

    plugins.save_plugin_config("_model_config", "", "", {"model_preset": "Balance"})
    config = model_config.get_config()

    assert config["model_preset"] == "Balance"
    assert config["chat_model"]["name"] == "balanced-chat"
    assert config["utility_model"]["name"] == "default-utility"
    assert config["embedding_model"]["name"] == "default-embedding"
    assert config["allow_chat_override"] is True


def test_legacy_raw_preset_is_preserved_as_canonical_chat_slot(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    cleaned = model_config.clean_presets_for_file(
        [
            {
                "name": "Legacy",
                "provider": "venice",
                "api_key": "must-not-persist",
                "kwargs": {"temperature": 0.2},
            }
        ]
    )

    assert cleaned == [
        {
            "name": "Legacy",
            "chat": {
                "provider": "venice",
                "kwargs": {"temperature": 0.2},
                "name": "Legacy",
            },
        }
    ]


def test_fallback_non_default_utility_presets_inherit_advanced_settings():
    from plugins._model_config.helpers import model_config

    presets_path = (
        PROJECT_ROOT / "plugins" / "_model_config" / "mode_presets_fallback.yaml"
    )
    presets = model_config.parse_preset_collection(
        presets_path.read_text(encoding="utf-8")
    )

    assert {
        preset["name"]: (
            preset["chat"]["name"],
            preset["utility"]["name"],
            preset["chat"]["vision"],
        )
        for preset in presets
    } == {
        "Default": (
            "openai/gpt-5.6-terra",
            "google/gemini-3.1-flash-lite",
            True,
        ),
        "Efficiency": (
            "z-ai/glm-5.2",
            "deepseek/deepseek-v4-flash",
            False,
        ),
        "Power": (
            "openai/gpt-5.6-sol",
            "openai/gpt-5.6-luna",
            True,
        ),
    }

    for preset in presets:
        if preset.get("name") == "Default":
            continue
        utility = preset.get("utility") or {}
        assert "ctx_length" not in utility
        assert "ctx_input" not in utility


@pytest.mark.asyncio
async def test_model_presets_api_returns_global_presets_for_project_scope(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import projects
    from plugins._model_config.api.model_presets import ModelPresets
    from plugins._model_config.helpers import model_config

    projects.create_project("demo", {"title": "Demo"})
    presets = model_config.get_presets()
    presets.append({"name": "Global", "chat": {"provider": "global", "name": "chat"}})
    model_config.save_presets(presets)

    handler = ModelPresets(Flask(__name__), threading.Lock())
    global_response = await handler.process({"action": "get"}, None)
    assert [preset["name"] for preset in global_response["presets"]] == [
        "Default",
        "Balance",
        "Global",
    ]

    project_response = await handler.process({"action": "get", "project_name": "demo"}, None)
    assert [p["name"] for p in project_response["presets"]] == [
        "Default",
        "Balance",
        "Global",
    ]
    assert project_response["project_presets"] == []


@pytest.mark.asyncio
async def test_model_presets_api_saves_only_scoped_selection(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import projects
    from plugins._model_config.api.model_presets import ModelPresets

    projects.create_project("demo", {"title": "Demo"})
    handler = ModelPresets(Flask(__name__), threading.Lock())

    response = await handler.process(
        {
            "action": "select",
            "name": "Balance",
            "project_name": "demo",
        },
        None,
    )

    assert response == {"ok": True, "selected_preset": "Balance"}
    config_path = (
        tmp_path
        / "usr"
        / "projects"
        / "demo"
        / ".a0proj"
        / "plugins"
        / "_model_config"
        / "config.json"
    )
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "model_preset": "Balance"
    }


def test_unified_preset_migration_preserves_global_and_scoped_configs(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import projects
    from plugins._model_config.extensions.python.startup_migration._10_migrate_model_config import (
        MigrateModelConfig,
    )

    global_dir = tmp_path / "usr" / "plugins" / "_model_config"
    global_dir.mkdir(parents=True, exist_ok=True)
    global_config = {
        "chat_model": {"provider": "openrouter", "name": "legacy-global-chat"},
        "utility_model": {"provider": "openrouter", "name": "legacy-global-utility"},
        "embedding_model": {"provider": "huggingface", "name": "legacy-global-embedding"},
    }
    (global_dir / "config.json").write_text(json.dumps(global_config), encoding="utf-8")
    (global_dir / "presets.yaml").write_text(
        "- name: Existing\n  chat:\n    provider: openrouter\n    name: existing-chat\n",
        encoding="utf-8",
    )

    projects.create_project("demo", {"title": "Demo"})
    project_config_path = (
        tmp_path
        / "usr"
        / "projects"
        / "demo"
        / ".a0proj"
        / "plugins"
        / "_model_config"
        / "config.json"
    )
    project_config_path.parent.mkdir(parents=True, exist_ok=True)
    project_config_path.write_text(
        json.dumps(
            {
                "chat_model": {"provider": "anthropic", "name": "project-chat"},
                "utility_model": {"provider": "openrouter", "name": "project-utility"},
                "embedding_model": {"provider": "openai", "name": "project-embedding"},
            }
        ),
        encoding="utf-8",
    )

    migration = MigrateModelConfig(agent=None)
    migration.execute()

    presets = yaml.safe_load((global_dir / "presets.yaml").read_text(encoding="utf-8"))
    assert [preset["name"] for preset in presets] == [
        "Default",
        "Existing",
        "Project demo",
    ]
    assert presets[0]["chat"]["name"] == "legacy-global-chat"
    assert presets[2]["embedding"]["name"] == "project-embedding"
    assert json.loads((global_dir / "config.json").read_text(encoding="utf-8")) == {
        "model_preset": "Default"
    }
    assert json.loads(project_config_path.read_text(encoding="utf-8")) == {
        "model_preset": "Project demo"
    }
    assert Path(str(project_config_path) + ".pre-unified-presets.bak").exists()

    before = (global_dir / "presets.yaml").read_text(encoding="utf-8")
    migration.execute()
    assert (global_dir / "presets.yaml").read_text(encoding="utf-8") == before


def test_unified_preset_migration_repairs_partial_legacy_default(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.extensions.python.startup_migration._10_migrate_model_config import (
        MigrateModelConfig,
    )

    global_dir = tmp_path / "usr" / "plugins" / "_model_config"
    global_dir.mkdir(parents=True, exist_ok=True)
    (global_dir / "config.json").write_text(
        json.dumps(
            {
                "chat_model": {
                    "provider": "anthropic",
                    "name": "legacy-chat",
                }
            }
        ),
        encoding="utf-8",
    )

    MigrateModelConfig(agent=None).execute()

    presets = yaml.safe_load((global_dir / "presets.yaml").read_text(encoding="utf-8"))
    default = presets[0]
    assert default["name"] == "Default"
    assert default["chat"]["name"] == "legacy-chat"
    assert default["utility"]["name"] == "default-utility"
    assert default["embedding"]["name"] == "default-embedding"


def test_unified_preset_migration_recovers_malformed_user_files(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.extensions.python.startup_migration._10_migrate_model_config import (
        MigrateModelConfig,
    )

    global_dir = tmp_path / "usr" / "plugins" / "_model_config"
    global_dir.mkdir(parents=True, exist_ok=True)
    config_path = global_dir / "config.json"
    presets_path = global_dir / "presets.yaml"
    config_path.write_text("{broken", encoding="utf-8")
    presets_path.write_text("not: [valid", encoding="utf-8")

    MigrateModelConfig(agent=None).execute()

    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "model_preset": "Default"
    }
    presets = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
    assert presets[0]["name"] == "Default"
    assert Path(str(config_path) + ".pre-unified-presets.bak").exists()
    assert Path(str(presets_path) + ".pre-unified-presets.bak").exists()


def test_new_instance_bootstraps_validated_remote_presets_once(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.extensions.python.startup_migration._10_migrate_model_config import (
        MigrateModelConfig,
    )
    from plugins._model_config.extensions.python.startup_migration import (
        _20_bootstrap_model_presets as bootstrap,
    )

    # The normal startup order runs legacy migration before initialization.
    MigrateModelConfig(agent=None).execute()

    remote_yaml = """
- name: Default
  chat:
    provider: openrouter
    name: openai/gpt-test
    api_key: must-not-persist
  utility:
    provider: openrouter
    name: openai/gpt-test-mini
  embedding:
    provider: huggingface
    name: sentence-transformers/test
- name: Efficiency
  chat:
    provider: openrouter
    name: vendor/efficient
- name: Power
  chat:
    provider: openrouter
    name: vendor/power
""".lstrip().encode()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return remote_yaml

    calls = []

    def urlopen(request, timeout):
        calls.append((request.full_url, timeout, request.headers.get("User-agent")))
        return Response()

    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", urlopen)

    result = bootstrap.BootstrapModelPresets(agent=None).execute()

    presets_path = tmp_path / "usr" / "plugins" / "_model_config" / "presets.yaml"
    presets = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
    assert result == "remote"
    assert [preset["name"] for preset in presets] == ["Default", "Efficiency", "Power"]
    assert "api_key" not in presets[0]["chat"]
    assert calls == [
        (
            bootstrap.REMOTE_PRESETS_URL,
            bootstrap.FETCH_TIMEOUT_SECONDS,
            "AgentZero-Model-Preset-Bootstrap",
        )
    ]

    monkeypatch.setattr(
        bootstrap.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("bootstrap fetched more than once")
        ),
    )
    assert bootstrap.BootstrapModelPresets(agent=None).execute() == "existing"


def test_remote_preset_failure_persists_local_fallback(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.extensions.python.startup_migration import (
        _20_bootstrap_model_presets as bootstrap,
    )

    monkeypatch.setattr(
        bootstrap.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )

    result = bootstrap.BootstrapModelPresets(agent=None).execute()

    presets_path = tmp_path / "usr" / "plugins" / "_model_config" / "presets.yaml"
    presets = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
    assert result == "fallback"
    assert [preset["name"] for preset in presets] == ["Default", "Balance"]


def test_invalid_remote_preset_collection_uses_local_fallback(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.extensions.python.startup_migration import (
        _20_bootstrap_model_presets as bootstrap,
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b"- name: Default\n  chat: invalid\n"

    monkeypatch.setattr(
        bootstrap.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(),
    )

    result = bootstrap.BootstrapModelPresets(agent=None).execute()

    presets_path = tmp_path / "usr" / "plugins" / "_model_config" / "presets.yaml"
    presets = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
    assert result == "fallback"
    assert [preset["name"] for preset in presets] == ["Default", "Balance"]


def test_remote_bootstrap_never_overwrites_existing_presets(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.extensions.python.startup_migration import (
        _20_bootstrap_model_presets as bootstrap,
    )

    presets_path = tmp_path / "usr" / "plugins" / "_model_config" / "presets.yaml"
    presets_path.parent.mkdir(parents=True, exist_ok=True)
    existing = "- name: Existing user preset\n"
    presets_path.write_text(existing, encoding="utf-8")
    monkeypatch.setattr(
        bootstrap.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("existing instances must not fetch")
        ),
    )

    result = bootstrap.BootstrapModelPresets(agent=None).execute()

    assert result == "existing"
    assert presets_path.read_text(encoding="utf-8") == existing


def test_obsolete_bootstrap_marker_does_not_block_missing_presets(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.extensions.python.startup_migration import (
        _20_bootstrap_model_presets as bootstrap,
    )
    from plugins._model_config.helpers import model_config

    marker = tmp_path / "usr" / "plugins" / "_model_config" / "preset_bootstrap.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"source":"remote"}', encoding="utf-8")
    monkeypatch.setattr(
        bootstrap.BootstrapModelPresets,
        "_download_presets",
        lambda _self: model_config._fallback_presets(),
    )

    result = bootstrap.BootstrapModelPresets(agent=None).execute()

    presets_path = marker.with_name("presets.yaml")
    assert result == "remote"
    assert presets_path.exists()
    assert [
        preset["name"]
        for preset in yaml.safe_load(presets_path.read_text(encoding="utf-8"))
    ] == ["Default", "Balance"]


def test_preset_rename_updates_scopes_and_unloaded_chats(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.api import model_presets

    global_config = tmp_path / "usr" / "plugins" / "_model_config" / "config.json"
    global_config.parent.mkdir(parents=True, exist_ok=True)
    global_config.write_text(json.dumps({"model_preset": "Research"}), encoding="utf-8")

    chat_path = tmp_path / "usr" / "chats" / "chat-1" / "chat.json"
    chat_path.parent.mkdir(parents=True, exist_ok=True)
    chat_path.write_text(
        json.dumps(
            {
                "id": "chat-1",
                "data": {"chat_model_override": {"preset_name": "Research"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(model_presets.AgentContext, "all", lambda *_args: [])

    model_presets._rename_preset_references(
        [{"from": "Research", "to": "Deep Research"}]
    )

    assert json.loads(global_config.read_text(encoding="utf-8")) == {
        "model_preset": "Deep Research"
    }
    chat = json.loads(chat_path.read_text(encoding="utf-8"))
    assert chat["data"]["chat_model_override"] == {
        "preset_name": "Deep Research"
    }


def test_project_save_persists_only_selected_preset_reference(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import projects
    from plugins._model_config.helpers import model_config

    model_config.save_presets(
        [
            model_config.get_presets()[0],
            {
                "name": "Research",
                "chat": {"provider": "anthropic", "name": "claude-research"},
                "utility": {"provider": "openai", "name": "utility-research"},
            }
        ]
    )

    projects.create_project(
        "demo",
        {
            "title": "Demo",
            "llm": {
                "selected_preset": {"scope": "global", "name": "Research"},
            },
        },
    )

    config_path = (
        tmp_path
        / "usr"
        / "projects"
        / "demo"
        / ".a0proj"
        / "plugins"
        / "_model_config"
        / "config.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config == {"model_preset": "Research"}

    project_json = (
        tmp_path / "usr" / "projects" / "demo" / ".a0proj" / "project.json"
    ).read_text(encoding="utf-8")
    assert "llm" not in project_json
    assert "_model_config" not in project_json


def test_project_save_does_not_freeze_inherited_global_model_config(
    monkeypatch,
    tmp_path,
):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import plugins, projects

    projects.create_project("demo", {"title": "Demo"})
    config_path = (
        tmp_path
        / "usr"
        / "projects"
        / "demo"
        / ".a0proj"
        / "plugins"
        / "_model_config"
        / "config.json"
    )

    project_data = projects.load_edit_project_data("demo")
    assert project_data["llm"]["has_project_config"] is False

    projects.update_project("demo", project_data)

    assert not config_path.exists()

    plugins.save_plugin_config("_model_config", "", "", {"model_preset": "Balance"})

    reloaded_data = projects.load_edit_project_data("demo")
    assert reloaded_data["llm"]["has_project_config"] is False
    assert reloaded_data["llm"]["selected_preset"]["name"] == "Balance"


def test_project_save_updates_existing_scoped_preset_selection(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import plugins, projects

    projects.create_project("demo", {"title": "Demo"})
    plugins.save_plugin_config(
        "_model_config",
        "demo",
        "",
        {"model_preset": "Default"},
    )

    project_data = projects.load_edit_project_data("demo")
    assert project_data["llm"]["has_project_config"] is True
    project_data["llm"]["selected_preset"]["name"] = "Balance"

    projects.update_project("demo", project_data)

    config_path = (
        tmp_path
        / "usr"
        / "projects"
        / "demo"
        / ".a0proj"
        / "plugins"
        / "_model_config"
        / "config.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config == {"model_preset": "Balance"}


def test_project_extended_data_supports_multiple_plugin_sections(
    monkeypatch,
    tmp_path,
):
    _prepare_a0_tree(monkeypatch, tmp_path)
    _add_project_extra_plugin(tmp_path)

    from helpers import projects

    projects.create_project(
        "demo",
        {
            "title": "Demo",
            "git_token": "secret-token",
            "extra": {"enabled": False, "note": "created"},
        },
    )

    saved_path = (
        tmp_path
        / "usr"
        / "projects"
        / "demo"
        / ".a0proj"
        / "extra_saved.json"
    )
    assert json.loads(saved_path.read_text(encoding="utf-8")) == {
        "project": "demo",
        "extra": {"enabled": False, "note": "created"},
    }

    project_data = projects.load_edit_project_data("demo")
    assert project_data["llm"]["has_project_config"] is False
    assert project_data["extra"] == {"loaded_for": "demo", "enabled": True}

    project_data["extra"] = {"enabled": True, "note": "updated"}
    projects.update_project("demo", project_data)

    assert json.loads(saved_path.read_text(encoding="utf-8")) == {
        "project": "demo",
        "extra": {"enabled": True, "note": "updated"},
    }


def test_project_extended_data_cannot_overwrite_core_fields(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)
    _add_project_conflict_plugin(tmp_path)

    from helpers import projects

    projects.create_project("demo", {"title": "Demo"})

    with pytest.raises(
        ValueError,
        match="Project extension data cannot overwrite core project fields: title",
    ):
        projects.load_edit_project_data("demo")


def test_preset_application_preserves_tuning_but_replaces_kwargs(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    base_config = {
        "allow_chat_override": True,
        "chat_model": {
            "provider": "openrouter",
            "name": "configured-chat",
            "ctx_length": 200000,
            "ctx_history": 0.5,
            "kwargs": {"temperature": 0.2, "routing": {"order": ["a", "b"]}},
        },
        "utility_model": {
            "provider": "openrouter",
            "name": "configured-utility",
            "ctx_length": 200000,
            "ctx_input": 0.4,
            "kwargs": {"temperature": 0.1, "routing": {"order": ["fast"]}},
        },
        "embedding_model": {
            "provider": "huggingface",
            "name": "configured-embedding",
            "kwargs": {"device": "cpu", "batch_size": 16},
        },
    }
    preset = {
        "name": "Research",
        "chat": {
            "provider": "anthropic",
            "name": "claude-research",
            "kwargs": {"routing": {"priority": "quality"}},
        },
        "utility": {
            "provider": "openrouter",
            "name": "utility-research",
            "kwargs": {"routing": {"timeout": 30}},
        },
        "embedding": {
            "provider": "openai",
            "name": "text-embedding-3-large",
        },
    }

    config = model_config.build_config_from_preset(preset, base_config)

    assert config["chat_model"]["name"] == "claude-research"
    assert config["chat_model"]["ctx_length"] == 200000
    assert config["chat_model"]["kwargs"] == {"routing": {"priority": "quality"}}
    assert config["utility_model"]["name"] == "utility-research"
    assert config["utility_model"]["ctx_length"] == 200000
    assert config["utility_model"]["ctx_input"] == 0.4
    assert config["utility_model"]["kwargs"] == {"routing": {"timeout": 30}}
    assert config["embedding_model"]["name"] == "text-embedding-3-large"
    assert config["embedding_model"]["kwargs"] == {}


def test_preset_application_clears_stale_kwargs_when_preset_omits_them(
    monkeypatch,
    tmp_path,
):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    base_config = {
        "chat_model": {
            "provider": "openrouter",
            "name": "openai/gpt-5.4",
            "ctx_length": 200000,
            "kwargs": {"temperature": 0, "extra_headers": {"x-old": "true"}},
        },
        "utility_model": {
            "provider": "openrouter",
            "name": "openai/gpt-5.4-mini",
            "ctx_length": 128000,
            "kwargs": {"temperature": 0},
        },
    }
    preset = {
        "name": "Codex",
        "chat": {
            "provider": "codex_oauth",
            "name": "gpt-5.1-codex",
        },
        "utility": {
            "provider": "codex_oauth",
            "name": "gpt-5.1-codex-mini",
        },
    }

    config = model_config.build_config_from_preset(preset, base_config)

    assert config["chat_model"]["name"] == "gpt-5.1-codex"
    assert config["chat_model"]["ctx_length"] == 200000
    assert config["chat_model"]["kwargs"] == {}
    assert config["utility_model"]["name"] == "gpt-5.1-codex-mini"
    assert config["utility_model"]["ctx_length"] == 128000
    assert config["utility_model"]["kwargs"] == {}


def test_preset_application_inherits_optional_slots(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    base_config = {
        "chat_model": {"provider": "openrouter", "name": "configured-chat"},
        "utility_model": {
            "provider": "openrouter",
            "name": "configured-utility",
            "ctx_length": 200000,
        },
        "embedding_model": {
            "provider": "huggingface",
            "name": "configured-embedding",
        },
    }
    preset = {
        "name": "Chat Only",
        "chat": {"provider": "anthropic", "name": "claude-research"},
        "utility": {"ctx_length": 128000},
    }

    config = model_config.build_config_from_preset(preset, base_config)

    assert config["chat_model"]["name"] == "claude-research"
    assert config["utility_model"] == base_config["utility_model"]
    assert config["embedding_model"] == base_config["embedding_model"]


def test_preset_vision_slot_is_optional_and_never_inherited(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    base_config = {
        "chat_model": {"provider": "openrouter", "name": "main", "vision": False},
        "vision_model": {
            "provider": "openrouter",
            "name": "default-vision",
            "max_embeds": 2,
        },
    }

    without_sidecar = model_config.build_config_from_preset(
        {"name": "Text only", "chat": {"provider": "openrouter", "name": "text"}},
        base_config,
    )
    with_sidecar = model_config.build_config_from_preset(
        {
            "name": "Visual",
            "chat": {"provider": "openrouter", "name": "text"},
            "vision": {
                "provider": "anthropic",
                "name": "visual",
                "max_embeds": 5,
            },
        },
        base_config,
    )

    assert without_sidecar["vision_model"] == {}
    assert with_sidecar["vision_model"]["provider"] == "anthropic"
    assert with_sidecar["vision_model"]["name"] == "visual"
    assert with_sidecar["vision_model"]["max_embeds"] == 5
    assert "default-vision" not in str(with_sidecar["vision_model"])


def test_vision_call_limits_are_preset_owned_and_default_clean(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    cleaned = model_config.clean_presets_for_file(
        [
            {
                "name": "Default limits",
                "vision": {
                    "provider": "openrouter",
                    "name": "vision-default",
                    "timeout": 300,
                    "max_tokens": 2000,
                },
            },
            {
                "name": "Tuned limits",
                "vision": {
                    "provider": "openrouter",
                    "name": "vision-tuned",
                    "timeout": 45,
                    "max_tokens": 512,
                },
            },
        ]
    )

    assert cleaned[0]["vision"] == {
        "provider": "openrouter",
        "name": "vision-default",
    }
    assert cleaned[1]["vision"]["timeout"] == 45
    assert cleaned[1]["vision"]["max_tokens"] == 512


def test_vision_model_build_applies_only_its_preset_call_limits(monkeypatch):
    from plugins._model_config.helpers import model_config

    calls = []

    def fake_get_chat_model(provider, name, **kwargs):
        calls.append((provider, name, kwargs))
        return kwargs

    monkeypatch.setattr(model_config.models, "get_chat_model", fake_get_chat_model)

    cases = [
        (
            {"provider": "openrouter", "name": "vision-default"},
            {"timeout": 300, "max_tokens": 2000},
        ),
        (
            {
                "provider": "openrouter",
                "name": "vision-legacy-kwargs",
                "kwargs": {"timeout": 90, "max_tokens": 1024},
            },
            {"timeout": 90, "max_tokens": 1024},
        ),
        (
            {
                "provider": "openrouter",
                "name": "vision-tuned",
                "timeout": "45",
                "max_tokens": "512",
                "kwargs": {
                    "timeout": 90,
                    "max_tokens": 1024,
                    "temperature": 0.1,
                },
            },
            {"timeout": 45, "max_tokens": 512},
        ),
    ]

    for config, expected in cases:
        monkeypatch.setattr(
            model_config,
            "get_vision_model_config",
            lambda _agent=None, config=config: config,
        )
        built = model_config.build_vision_model()
        assert built["timeout"] == expected["timeout"]
        assert built["max_tokens"] == expected["max_tokens"]

    assert calls[-1][2]["temperature"] == 0.1

    monkeypatch.setattr(
        model_config,
        "get_chat_model_config",
        lambda _agent=None: {"provider": "openrouter", "name": "main"},
    )
    main = model_config.build_chat_model()
    assert "timeout" not in main
    assert "max_tokens" not in main


def test_vision_model_does_not_duplicate_token_params(monkeypatch):
    from plugins._model_config.helpers import model_config

    calls = []

    def fake_get_chat_model(provider, name, **kwargs):
        calls.append((provider, name, kwargs))
        return kwargs

    monkeypatch.setattr(model_config.models, "get_chat_model", fake_get_chat_model)
    monkeypatch.setattr(
        model_config,
        "get_vision_model_config",
        lambda _agent=None: {
            "provider": "openai",
            "name": "gpt-4o-mini",
            "kwargs": {"max_completion_tokens": 32768},
        },
    )

    built = model_config.build_vision_model()
    assert built["max_completion_tokens"] == 32768
    assert "max_tokens" not in built
    assert built["timeout"] == model_config.DEFAULT_VISION_TIMEOUT_SECONDS
    assert calls[-1][0] == "openai"


def test_legacy_utility_preset_defaults_preserve_tuning_but_clear_kwargs(
    monkeypatch,
    tmp_path,
):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    base_config = {
        "utility_model": {
            "provider": "openrouter",
            "name": "configured-utility",
            "api_base": "https://custom.example/v1",
            "ctx_length": 200000,
            "ctx_input": 0.4,
            "rl_requests": 12,
            "rl_input": 34000,
            "rl_output": 56000,
            "kwargs": {"temperature": 0.1},
        },
    }
    preset = {
        "name": "Legacy Saved Preset",
        "utility": {
            "provider": "openrouter",
            "name": "preset-utility",
            "api_key": "",
            "api_base": "",
            "ctx_length": 128000,
            "ctx_input": 0.7,
            "rl_requests": 0,
            "rl_input": 0,
            "rl_output": 0,
            "kwargs": {},
        },
    }

    config = model_config.build_config_from_preset(
        preset,
        base_config,
        strip_api_key=False,
    )

    utility = config["utility_model"]
    assert utility["name"] == "preset-utility"
    assert utility["api_base"] == ""
    assert "api_key" not in utility
    assert utility["ctx_length"] == 200000
    assert utility["ctx_input"] == 0.4
    assert utility["rl_requests"] == 12
    assert utility["rl_input"] == 34000
    assert utility["rl_output"] == 56000
    assert utility["kwargs"] == {}


def test_preset_override_preserves_default_preset_utility_context(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from plugins._model_config.helpers import model_config

    base_config = {
        "allow_chat_override": True,
        "chat_model": {"provider": "openrouter", "name": "configured-chat"},
        "utility_model": {
            "provider": "openrouter",
            "name": "configured-utility",
            "ctx_length": 200000,
            "ctx_input": 0.4,
        },
    }
    preset = {
        "name": "Fast",
        "chat": {"provider": "openrouter", "name": "fast-chat"},
        "utility": {"provider": "openrouter", "name": "fast-utility"},
    }

    class FakeContext:
        def get_data(self, key):
            return {"preset_name": "Fast"} if key == "chat_model_override" else None

    class FakeAgent:
        context = FakeContext()

    monkeypatch.setattr(model_config, "get_config", lambda *args, **kwargs: base_config)
    monkeypatch.setattr(
        model_config,
        "get_preset_by_name",
        lambda name, **kwargs: preset if name == "Fast" else None,
    )
    default_preset = model_config.config_to_preset(base_config, "Default")
    monkeypatch.setattr(
        model_config,
        "resolve_preset",
        lambda name, **kwargs: preset if name == "Fast" else default_preset if name == "Default" else None,
    )

    utility = model_config.get_utility_model_config(FakeAgent())

    assert utility["name"] == "fast-utility"
    assert utility["ctx_length"] == 200000
    assert utility["ctx_input"] == 0.4


def test_missing_scoped_preset_falls_back_to_default(monkeypatch, tmp_path):
    _prepare_a0_tree(monkeypatch, tmp_path)

    from helpers import plugins, projects
    from plugins._model_config.helpers import model_config

    projects.create_project("demo", {"title": "Demo"})
    plugins.save_plugin_config(
        "_model_config",
        "demo",
        "",
        {"model_preset": "Deleted"},
    )

    assert model_config.get_configured_preset_name(project_name="demo") == "Default"
    resolved = model_config.get_config(project_name="demo")
    assert resolved["model_preset"] == "Default"
    assert resolved["chat_model"]["name"] == "default-chat"


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['save', 'reset'])
@pytest.mark.parametrize('change', ['none', 'default', 'explicit'])
async def test_collection_write_compares_embedding_snapshots_without_reloading_per_preset(monkeypatch, action, change):
    from copy import deepcopy
    from plugins._model_config.api import model_presets
    from plugins._model_config.helpers import model_config

    before = [
        {'name': 'Default', 'embedding': {'provider': 'test', 'name': 'base'}},
        {'name': 'Inherited'},
        {'name': 'Explicit', 'embedding': {'provider': 'test', 'name': 'custom'}},
    ]
    after = deepcopy(before)
    if change == 'default':
        after[0]['embedding']['name'] = 'new-base'
    elif change == 'explicit':
        after[2]['embedding']['name'] = 'new-custom'
    current = before
    reads = 0
    notifications = []

    def get_presets():
        nonlocal reads
        reads += 1
        return deepcopy(current)

    def save_presets(presets):
        nonlocal current
        assert presets == after
        current = after

    monkeypatch.setattr(model_config, 'get_presets', get_presets)
    monkeypatch.setattr(model_config, 'save_presets', save_presets)
    monkeypatch.setattr(model_config, 'reset_presets', lambda: deepcopy(after))
    monkeypatch.setattr(model_presets, '_notify_embedding_changed', lambda: notifications.append(True))
    monkeypatch.setattr(model_presets, '_rename_preset_references', lambda renames: None)
    handler = model_presets.ModelPresets(Flask(__name__), threading.Lock())
    result = await handler.process({'action': action, 'presets': after}, None)
    assert result == {'ok': True, 'presets': after}
    assert reads == (2 if action == 'save' else 1)
    assert notifications == ([] if change == 'none' else [True])
    signatures = model_presets._embedding_signatures(after)
    assert signatures['Inherited'] == signatures['Default']
    assert signatures['Explicit'] == after[2]['embedding']
    assert before[0]['embedding']['name'] == 'base'
