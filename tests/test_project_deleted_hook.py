"""Tests for the project_deleted plugin hook fired by delete_project()."""

from pathlib import Path

from helpers import files, projects
from helpers import plugins as plugins_helper

HOOKS_PLUGIN = "test-project-deleted-plugin"

HOOKS_PY = '''\nfrom pathlib import Path\n\n\ndef project_deleted(project_name: str = "", **kwargs):\n    log = Path(__file__).parent / "hook.log"\n    log.write_text(project_name)\n'''

RAISING_HOOKS_PY = '''\n\ndef project_deleted(project_name: str = "", **kwargs):\n    raise RuntimeError("hook boom")\n'''


def _prepare_base(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(files, "_base_dir", str(tmp_path))
    (tmp_path / "usr" / "projects").mkdir(parents=True, exist_ok=True)
    (tmp_path / "usr" / "plugins").mkdir(parents=True, exist_ok=True)
    (tmp_path / "plugins").mkdir(parents=True, exist_ok=True)


def _clear_plugin_caches() -> None:
    plugins_helper.cache.clear(plugins_helper.PLUGINS_LIST_CACHE_AREA)
    plugins_helper.cache.clear(plugins_helper.ENABLED_PLUGINS_LIST_CACHE_AREA)
    plugins_helper.cache.clear(plugins_helper.HOOKS_CACHE_AREA)


def _create_hook_plugin(hooks_source: str, *, disabled: bool = False) -> Path:
    plugin_dir = Path(plugins_helper.get_plugin_roots(HOOKS_PLUGIN)[0])
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text("name: test-project-deleted-plugin\n")
    (plugin_dir / "hooks.py").write_text(hooks_source)
    if disabled:
        (plugin_dir / ".toggle-0").write_text("")
    _clear_plugin_caches()
    return plugin_dir


def _create_project(name: str) -> Path:
    project_dir = Path(files.get_abs_path(projects.PROJECTS_PARENT_DIR, name))
    (project_dir / projects.PROJECT_META_DIR).mkdir(parents=True, exist_ok=True)
    return project_dir


def test_delete_project_fires_project_deleted_hook(monkeypatch, tmp_path):
    _prepare_base(monkeypatch, tmp_path)
    plugin_dir = _create_hook_plugin(HOOKS_PY)
    project_dir = _create_project("hook-test-project")

    result = projects.delete_project("hook-test-project")

    assert result == "hook-test-project"
    assert not project_dir.exists()
    assert (plugin_dir / "hook.log").read_text() == "hook-test-project"


def test_hook_failure_does_not_break_project_deletion(monkeypatch, tmp_path):
    _prepare_base(monkeypatch, tmp_path)
    _create_hook_plugin(RAISING_HOOKS_PY)
    project_dir = _create_project("failing-hook-project")

    result = projects.delete_project("failing-hook-project")

    assert result == "failing-hook-project"
    assert not project_dir.exists()


def test_disabled_plugin_is_not_notified(monkeypatch, tmp_path):
    _prepare_base(monkeypatch, tmp_path)
    plugin_dir = _create_hook_plugin(HOOKS_PY, disabled=True)
    _create_project("disabled-hook-project")

    projects.delete_project("disabled-hook-project")

    assert not (plugin_dir / "hook.log").exists()


def test_plugin_without_hooks_does_not_break(monkeypatch, tmp_path):
    _prepare_base(monkeypatch, tmp_path)
    plugin_dir = Path(plugins_helper.get_plugin_roots(HOOKS_PLUGIN)[0])
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text("name: test-project-deleted-plugin\n")
    _clear_plugin_caches()
    project_dir = _create_project("no-hooks-project")

    result = projects.delete_project("no-hooks-project")

    assert result == "no-hooks-project"
    assert not project_dir.exists()
