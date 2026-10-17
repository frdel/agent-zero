from pathlib import Path
import sys
from types import ModuleType

import helpers
from helpers import cache, files, ui_bundler


def configure_roots(
    tmp_path: Path,
    monkeypatch,
    extension_root: Path,
    plugin_root: Path,
) -> None:
    stored: dict[tuple[str, str], dict] = {}
    monkeypatch.setattr(cache, "get", lambda area, key: stored.get((area, key)))
    monkeypatch.setattr(
        cache,
        "add",
        lambda area, key, value: stored.__setitem__((area, key), value),
    )
    monkeypatch.setattr(cache, "clear", lambda *_args, **_kwargs: stored.clear())
    monkeypatch.setattr(
        files,
        "get_abs_path",
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    monkeypatch.setattr(
        files,
        "is_in_base_dir",
        lambda path: Path(path).resolve().is_relative_to(tmp_path),
    )
    monkeypatch.setattr(
        files,
        "deabsolute_path",
        lambda path: Path(path).resolve().relative_to(tmp_path).as_posix(),
    )
    subagents_module = ModuleType("helpers.subagents")
    subagents_module.get_paths = lambda *_args, **_kwargs: [str(extension_root)]
    plugins_module = ModuleType("helpers.plugins")
    plugins_module.get_enabled_plugin_paths = lambda *_args, **_kwargs: [str(plugin_root)]
    monkeypatch.setitem(sys.modules, "helpers.subagents", subagents_module)
    monkeypatch.setitem(sys.modules, "helpers.plugins", plugins_module)
    monkeypatch.setattr(helpers, "subagents", subagents_module, raising=False)
    monkeypatch.setattr(helpers, "plugins", plugins_module, raising=False)


def test_bundle_discovers_assets_without_changing_frontend_loaders(
    tmp_path: Path, monkeypatch
) -> None:
    webui = tmp_path / "webui"
    components = webui / "components"
    extension_root = tmp_path / "extensions" / "webui"
    plugin_root = tmp_path / "plugins" / "example" / "webui"

    assets = {
        webui / "index.html": (
            '<link rel="stylesheet" href="/index.css">'
            '<script type="module" src="/index.js"></script>'
            '<script type="module" src="/large.js"></script>'
        ).encode(),
        webui / "index.css": (
            b'@import url("./theme.css");'
            b'@font-face { src: url("/public/font.bin"); }'
        ),
        webui / "theme.css": b"body { color: black; }",
        webui / "index.js": b'import "./js/module.js";',
        webui / "large.js": (
            b'import "./js/large-child.js";' + b" " * (512 * 1024)
        ),
        webui / "js" / "large-child.js": b"export const child = true;",
        webui / "js" / "module.js": b'export { value } from "./value.js";',
        webui / "js" / "value.js": b"export const value = 1;",
        webui / "public" / "font.bin": b"\xff\x00\x81",
        components / "root.html": (
            '<x-component path="nested/child.html"></x-component>'
            '<img src="/public/image.png">'
            '<audio src="/public/audio.mp3"></audio>'
            '<video src="/public/video.mp4"></video>'
        ).encode(),
        components / "nested" / "child.html": b"<div>child</div>",
        webui / "public" / "image.png": b"image",
        webui / "public" / "audio.mp3": b"audio",
        webui / "public" / "video.mp4": b"video",
        extension_root / "sidebar" / "entry.html": (
            '<script type="module" src="/plugins/example/webui/feature.js"></script>'
        ).encode(),
        extension_root / "sidebar" / "entry.css": (
            b'@import "/plugins/example/webui/feature.css";'
        ),
        plugin_root / "main.html": (
            '<x-component path="/plugins/example/webui/nested/modal.html"></x-component>'
        ).encode(),
        plugin_root / "feature.js": b'import "./nested/helper.js";',
        plugin_root / "feature.css": b'body { background: url("./icon.svg"); }',
        plugin_root / "icon.svg": b"<svg></svg>",
        plugin_root / "nested" / "helper.js": b"export default true;",
        plugin_root / "nested" / "modal.html": b"<dialog>plugin</dialog>",
        plugin_root / "nested" / "runtime-only.css": b"runtime-one",
    }
    for path, content in assets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    configure_roots(tmp_path, monkeypatch, extension_root, plugin_root)
    bundle = ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None)

    assert bundle["version"]
    assert set(bundle["files"]) == {
        "/extensions/webui/sidebar/entry.html",
        "/index.css",
        "/index.html",
        "/index.js",
        "/js/large-child.js",
        "/js/module.js",
        "/js/value.js",
        "/plugins/example/webui/feature.js",
        "/plugins/example/webui/nested/helper.js",
        "/theme.css",
    }
    assert bundle["files"]["/index.js"][:2] == [
        "text/javascript; charset=utf-8",
        "text",
    ]
    assert "/large.js" not in bundle["files"]
    assert "/js/large-child.js" in bundle["files"]
    assert "/components/root.html" not in bundle["files"]
    assert "/plugins/example/webui/main.html" not in bundle["files"]
    assert "/public/font.bin" not in bundle["files"]
    assert "/public/image.png" not in bundle["files"]
    assert "/public/audio.mp3" not in bundle["files"]
    assert "/public/video.mp4" not in bundle["files"]
    assert "/plugins/example/webui/icon.svg" not in bundle["files"]
    assert all(entry[1] == "text" for entry in bundle["files"].values())
    assert all(
        len(entry[2].encode("utf-8")) <= 512 * 1024
        for entry in bundle["files"].values()
    )

    previous_version = bundle["version"]
    assets[webui / "js" / "value.js"] = b"export const value = 22;"
    (webui / "js" / "value.js").write_bytes(assets[webui / "js" / "value.js"])
    cache.clear("ui_asset_bundle")
    rebuilt = ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None)
    assert rebuilt["version"] != previous_version
    assert rebuilt["files"]["/js/value.js"][2] == "export const value = 22;"

    selected_version = rebuilt["version"]
    runtime_only = plugin_root / "nested" / "runtime-only.css"
    runtime_only.write_bytes(b"runtime-two-is-newer")
    cache.clear("ui_asset_bundle")
    runtime_rebuilt = ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None)
    assert runtime_rebuilt["version"] != selected_version
    assert "/plugins/example/webui/nested/runtime-only.css" not in runtime_rebuilt["files"]


def test_bundle_excludes_symlink_escapes_and_serializes_json(
    tmp_path: Path, monkeypatch
) -> None:
    webui = tmp_path / "webui"
    component_root = webui / "components"
    extension_root = tmp_path / "extensions" / "webui"
    plugin_root = tmp_path / "plugins" / "example" / "webui"
    for root in (component_root, extension_root, plugin_root):
        root.mkdir(parents=True)
    (webui / "index.html").write_text(
        '<x-component path="safe.html"></x-component>'
        '<x-component path="escape.html"></x-component>',
        encoding="utf-8",
    )
    (component_root / "safe.html").write_text("</script>&", encoding="utf-8")
    outside = tmp_path / "outside.html"
    outside.write_text("outside", encoding="utf-8")
    (component_root / "escape.html").symlink_to(outside)

    configure_roots(tmp_path, monkeypatch, extension_root, plugin_root)
    bundle = ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None)
    payload = ui_bundler.serialize_ui_asset_bundle(bundle)

    assert "/components/safe.html" in payload
    assert "/components/escape.html" not in payload
    assert "</script>&" in payload


def test_bundle_recursively_scans_a_caller_supplied_entry(
    tmp_path: Path, monkeypatch
) -> None:
    webui = tmp_path / "webui"
    extension_root = tmp_path / "extensions" / "webui"
    plugin_root = tmp_path / "plugins" / "example" / "webui"
    assets = {
        webui / "index.html": b"<main></main>",
        webui / "components" / "ad-hoc.html": (
            b'<script type="module" src="./ad-hoc.js"></script>'
            b'<link rel="stylesheet" href="/css/ad-hoc.css">'
        ),
        webui / "components" / "ad-hoc.js": b'import "../js/shared.js";',
        webui / "js" / "shared.js": b"export const shared = true;",
        webui / "css" / "ad-hoc.css": b'@import "./shared.css";',
        webui / "css" / "shared.css": b"body { color: black; }",
    }
    for path, content in assets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    extension_root.mkdir(parents=True)
    plugin_root.mkdir(parents=True)

    configure_roots(tmp_path, monkeypatch, extension_root, plugin_root)
    bundle = ui_bundler.get_ui_asset_bundle(
        [
            "/components/ad-hoc.html",
            "/css/ad-hoc.css",
            "/components/ad-hoc.html",
            "https://example.com/remote.js",
        ],
        agent=None,
    )

    assert bundle["version"]
    assert set(bundle["files"]) == {
        "/components/ad-hoc.html",
        "/components/ad-hoc.js",
        "/css/ad-hoc.css",
        "/css/shared.css",
        "/js/shared.js",
    }

    index_bundle = ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None)
    assert set(index_bundle["files"]) == {"/index.html"}
    assert index_bundle["version"] != bundle["version"]


def test_bundle_cache_invalidates_when_plugin_asset_changes(
    tmp_path: Path, monkeypatch
) -> None:
    webui = tmp_path / "webui"
    extension_root = tmp_path / "extensions" / "webui"
    plugin_root = tmp_path / "plugins" / "example" / "webui"
    assets = {
        webui / "index.html": (
            '<script type="module" src="/plugins/example/webui/store.js"></script>'
        ).encode(),
        plugin_root / "store.js": b"export const slot = 'none';",
    }
    for path, content in assets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    configure_roots(tmp_path, monkeypatch, extension_root, plugin_root)
    bundle = ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None)
    assert (
        bundle["files"]["/plugins/example/webui/store.js"][2]
        == "export const slot = 'none';"
    )

    # Unchanged assets keep serving the cached bundle without a rebuild.
    cached_bundle = ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None)
    assert cached_bundle is bundle

    # Patching a plugin webui asset must invalidate the in-memory bundle on
    # the next call without cache.clear() or a process restart, so the served
    # version advances and clients re-register the service worker
    # (dev-ticket-2026-08-24). Different content length guarantees the
    # signature changes even when mtime granularity is coarse.
    (plugin_root / "store.js").write_bytes(b"export const slot = 'vision';")
    rebuilt = ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None)
    assert rebuilt is not bundle
    assert rebuilt["version"] != bundle["version"]
    assert (
        rebuilt["files"]["/plugins/example/webui/store.js"][2]
        == "export const slot = 'vision';"
    )

    # The rebuilt bundle is cached again under the new signature.
    assert ui_bundler.get_ui_asset_bundle(["/index.html"], agent=None) is rebuilt
