from __future__ import annotations

import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _TestAgentContext:
    @staticmethod
    def get(context_id):
        return None


sys.modules.setdefault("agent", SimpleNamespace(AgentContext=_TestAgentContext))

from api.load_webui_extensions import LoadWebuiExtensions
from helpers.extension import get_webui_extension_manifest


SURFACE_SCENARIOS: list[tuple[str, str]] = [
    ("sidebar-start", "webui/components/sidebar/left-sidebar.html"),
    ("sidebar-end", "webui/components/sidebar/left-sidebar.html"),
    ("sidebar-top-wrapper-start", "webui/components/sidebar/top-section/sidebar-top.html"),
    ("sidebar-top-wrapper-end", "webui/components/sidebar/top-section/sidebar-top.html"),
    ("sidebar-quick-actions-main-start", "webui/components/sidebar/top-section/quick-actions.html"),
    ("sidebar-quick-actions-main-end", "webui/components/sidebar/top-section/quick-actions.html"),
    ("sidebar-quick-actions-dropdown-start", "webui/components/sidebar/top-section/quick-actions.html"),
    ("sidebar-quick-actions-dropdown-end", "webui/components/sidebar/top-section/quick-actions.html"),
    ("sidebar-chats-list-start", "webui/components/sidebar/chats/chats-list.html"),
    ("sidebar-chats-list-view", "webui/components/sidebar/chats/chats-list.html"),
    ("sidebar-chats-list-end", "webui/components/sidebar/chats/chats-list.html"),
    ("sidebar-tasks-list-start", "plugins/_scheduler/webui/sidebar/tasks-list.html"),
    ("sidebar-tasks-list-view", "plugins/_scheduler/webui/sidebar/tasks-list.html"),
    ("sidebar-tasks-list-end", "plugins/_scheduler/webui/sidebar/tasks-list.html"),
    ("sidebar-tasks-list", "webui/components/sidebar/left-sidebar.html"),
    ("sidebar-row-actions-menu", "webui/components/sidebar/left-sidebar.html"),
    ("sidebar-bottom-wrapper-start", "webui/components/sidebar/bottom/sidebar-bottom.html"),
    ("sidebar-bottom-wrapper-end", "webui/components/sidebar/bottom/sidebar-bottom.html"),
    ("chat-input-start", "webui/components/chat/input/chat-bar.html"),
    ("chat-input-end", "webui/components/chat/input/chat-bar.html"),
    ("chat-input-progress-start", "webui/components/chat/input/progress.html"),
    ("chat-input-progress-end", "webui/components/chat/input/progress.html"),
    ("chat-input-box-start", "webui/components/chat/input/chat-bar-input.html"),
    ("chat-input-box-end", "webui/components/chat/input/chat-bar-input.html"),
    ("chat-input-bottom-actions-start", "webui/components/chat/input/bottom-actions-bar.html"),
    ("chat-input-bottom-actions-end", "webui/components/chat/input/bottom-actions-bar.html"),
    ("chat-top-start", "webui/components/chat/top-section/chat-top.html"),
    ("chat-top-end", "webui/components/chat/top-section/chat-top.html"),
    ("sync-status-end", "webui/components/sync/sync-status.html"),
    ("welcome-screen-start", "webui/components/welcome/welcome-screen.html"),
    ("welcome-screen-end", "webui/components/welcome/welcome-screen.html"),
    ("welcome-actions-start", "webui/components/welcome/welcome-screen.html"),
    ("welcome-actions-middle", "webui/components/welcome/welcome-screen.html"),
    ("welcome-actions-end", "webui/components/welcome/welcome-screen.html"),
    ("welcome-banners-start", "webui/components/welcome/welcome-screen.html"),
    ("welcome-banners-end", "webui/components/welcome/welcome-screen.html"),
    ("plugins-list-dropdown-start", "webui/components/plugins/list/plugin-list.html"),
    ("plugins-list-dropdown-end", "webui/components/plugins/list/plugin-list.html"),
    ("modal-shell-start", "webui/js/modals.js"),
    ("modal-shell-end", "webui/js/modals.js"),
    ("right-canvas-shell-start", "webui/components/canvas/right-canvas.html"),
    ("right-canvas-tabs-start", "webui/components/canvas/right-canvas.html"),
    ("right-canvas-tabs-end", "webui/components/canvas/right-canvas.html"),
    ("right-canvas-toolbar-start", "webui/components/canvas/right-canvas.html"),
    ("right-canvas-toolbar-end", "webui/components/canvas/right-canvas.html"),
    ("right-canvas-panels", "webui/components/canvas/right-canvas.html"),
    ("right-canvas-empty-state", "webui/components/canvas/right-canvas.html"),
    ("right-canvas-shell-end", "webui/components/canvas/right-canvas.html"),
]


def _new_handler() -> LoadWebuiExtensions:
    app = Flask("test_webui_extension_surfaces")
    app.secret_key = "test-secret"
    return LoadWebuiExtensions(app, threading.RLock())


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _assert_surface_anchor_in_template(surface: str, template_rel_path: str) -> None:
    template_path = PROJECT_ROOT / template_rel_path
    template_html = template_path.read_text(encoding="utf-8")
    assert f'<x-extension id="{surface}"' in template_html


@contextmanager
def _temporary_probe_plugin(surface: str) -> Iterator[tuple[str, str]]:
    plugins_root = PROJECT_ROOT / "plugins"
    with tempfile.TemporaryDirectory(
        prefix="tmp_surface_probe_",
        dir=plugins_root,
    ) as temp_plugin_dir:
        plugin_id = Path(temp_plugin_dir).name
        (Path(temp_plugin_dir) / "plugin.yaml").write_text(
            (
                f"name: {plugin_id}\n"
                f"title: {plugin_id}\n"
                "description: Temporary WebUI surface probe.\n"
                "version: 0.0.0\n"
                "always_enabled: false\n"
            ),
            encoding="utf-8",
        )
        from helpers import cache

        cache.clear("*(plugins)*")
        probe_file = (
            Path(temp_plugin_dir)
            / "extensions"
            / "webui"
            / surface
            / "surface-probe.html"
        )
        probe_file.parent.mkdir(parents=True, exist_ok=True)
        probe_file.write_text(
            (
                "<div x-data "
                f'data-surface-probe="{surface}" '
                f'data-plugin-id="{plugin_id}"></div>'
            ),
            encoding="utf-8",
        )
        try:
            yield plugin_id, probe_file.name
        finally:
            cache.clear("*(plugins)*")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("surface", "template_rel_path"),
    SURFACE_SCENARIOS,
    ids=[scenario[0] for scenario in SURFACE_SCENARIOS],
)
async def test_webui_surface_extension_point_end_to_end(
    surface: str,
    template_rel_path: str,
) -> None:
    _assert_surface_anchor_in_template(surface, template_rel_path)

    with _temporary_probe_plugin(surface) as (plugin_id, probe_file_name):
        payload = await _new_handler().process(
            {"extension_point": surface, "filters": ["*.html"]},
            None,
        )
        assert isinstance(payload, dict)
        extensions = payload.get("extensions", [])
        expected_suffix = (
            f"{plugin_id}/extensions/webui/{surface}/{probe_file_name}"
        )

        extension_paths = [
            str(
                extension.get("path", "")
                if isinstance(extension, dict)
                else extension
            ).replace("\\", "/")
            for extension in extensions
        ]

        assert any(path.endswith(expected_suffix) for path in extension_paths)


def test_webui_extension_manifest_groups_plugin_assets_by_type_and_surface() -> None:
    surface = "manifest-probe"
    with _temporary_probe_plugin(surface) as (plugin_id, probe_file_name):
        manifest = get_webui_extension_manifest(agent=None)
        expected_suffix = (
            f"/{plugin_id}/extensions/webui/{surface}/{probe_file_name}"
        )

        assert any(
            path.endswith(expected_suffix)
            for path in manifest["html"].get(surface, [])
        )
        assert surface not in manifest["js"]
