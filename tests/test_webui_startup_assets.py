from pathlib import Path
from html.parser import HTMLParser


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str | None]] = []
        self.asset_references: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.scripts.append(dict(attrs))
        if any(name in ("src", "href") for name, _value in attrs):
            self.asset_references.append((tag, dict(attrs)))


def assert_bootstrap_assets_are_self_contained(html: str) -> None:
    parser = AssetParser()
    parser.feed(html)
    # A local tab icon does not execute or block the inline startup document.
    # Reject external scripts/styles/images while retaining the favicon.
    assert [(tag, attrs.get("rel"), attrs.get("href"))
            for tag, attrs in parser.asset_references] == [
        ("link", "icon", "/public/favicon.svg")
    ]
    assert "src" not in parser.asset_references[0][1]
    assert (PROJECT_ROOT / "webui" / "public" / "favicon.svg").is_file()


def test_bootstrap_is_local_and_deferred() -> None:
    index_html = (PROJECT_ROOT / "webui" / "index.html").read_text(encoding="utf-8")

    assert "cdn.jsdelivr.net/npm/bootstrap" not in index_html
    assert '<script defer src="vendor/bootstrap/bootstrap.bundle.min.js"></script>' in index_html
    assert (PROJECT_ROOT / "webui" / "vendor" / "bootstrap" / "bootstrap.bundle.min.js").is_file()


def test_classic_startup_scripts_are_deferred() -> None:
    index_html = (PROJECT_ROOT / "webui" / "index.html").read_text(encoding="utf-8")
    parser = AssetParser()
    parser.feed(index_html)

    blocking_scripts = [
        script["src"]
        for script in parser.scripts
        if script.get("src")
        and script.get("type") != "module"
        and "defer" not in script
        and "async" not in script
    ]

    assert blocking_scripts == []


def test_splash_prepares_worker_before_replacing_document_in_place() -> None:
    splash_html = (PROJECT_ROOT / "webui" / "splash.html").read_text(
        encoding="utf-8"
    )
    index_html = (PROJECT_ROOT / "webui" / "index.html").read_text(encoding="utf-8")
    ui_server = (PROJECT_ROOT / "helpers" / "ui_server.py").read_text(encoding="utf-8")

    assert 'fetch("/ui/asset-bundle"' in splash_html
    assert 'const APP_DOCUMENT_PATH = "/ui/index"' in splash_html
    assert "const appDocumentPromise = fetch(APP_DOCUMENT_PATH" in splash_html
    assert 'navigator.serviceWorker.register(expectedUrl' in splash_html
    assert "await sendBundle(worker, bundle, true)" in splash_html
    assert 'const overlay = document.getElementById("startup-transition")' in splash_html
    assert 'overlay.dataset.theme = "light"' in splash_html
    assert "(bodyTag) => bodyTag + overlay.outerHTML" in splash_html
    assert "document.open()" in splash_html
    assert "document.write(appWithTransition)" in splash_html
    assert "document.close()" in splash_html
    assert "location.replace" not in splash_html
    assert 'const APP_PATH = "/index.html"' not in splash_html
    assert 'fetch("/ui/asset-bundle"' not in index_html
    assert 'id="ui-asset-bundle"' not in index_html
    assert '"/index.html"' in ui_server
    assert '"/ui/index"' in ui_server
    assert '"/safe"' in ui_server
    assert "handlers.serve_splash" in ui_server
    assert "handlers.serve_safe" in ui_server
    assert "handlers.serve_index" in ui_server
    assert '"/ui/asset-bundle"' in ui_server
    assert "handlers.serve_ui_asset_bundle" in ui_server
    assert '"/ui/asset-graph"' not in ui_server
    assert "handlers.serve_ui_asset_graph" not in ui_server
    assert "GZipMiddleware(" in ui_server
    assert "minimum_size=GZIP_MINIMUM_RESPONSE_BYTES" in ui_server
    assert "compresslevel=GZIP_COMPRESSION_LEVEL" in ui_server
    assert 'response.headers["Content-Encoding"] = "gzip"' in ui_server
    assert 'request.if_none_match.contains_weak(version)' in ui_server
    assert 'response.set_etag(version, weak=True)' in ui_server


def test_safe_mode_disables_workers_before_rendering_index_directly() -> None:
    safe_html = (PROJECT_ROOT / "webui" / "safe.html").read_text(encoding="utf-8")
    index_html = (PROJECT_ROOT / "webui" / "index.html").read_text(encoding="utf-8")
    ui_server = (PROJECT_ROOT / "helpers" / "ui_server.py").read_text(encoding="utf-8")

    assert "navigator.serviceWorker.getRegistrations()" in safe_html
    assert "registration.unregister()" in safe_html
    assert 'const DIRECT_PARAMETER = "__direct"' in safe_html
    assert "location.replace(target.href)" in safe_html
    assert 'fetch("/ui/asset-bundle"' not in safe_html
    assert "navigator.serviceWorker.register" not in safe_html
    assert_bootstrap_assets_are_self_contained(safe_html)
    assert 'request.args.get("__direct") == "1"' in ui_server
    assert "return await self.serve_index()" in ui_server
    assert 'files.read_file("webui/safe.html")' in ui_server
    assert 'safeUrl.searchParams.delete("__direct")' in index_html
    assert "navigator.serviceWorker.getRegistrations()" in index_html
    assert "registration.unregister()" in index_html
    assert "navigator.serviceWorker.register" not in index_html


def test_only_the_icon_guard_stylesheet_blocks_application_paint() -> None:
    index_html = (PROJECT_ROOT / "webui" / "index.html").read_text(encoding="utf-8")

    assert index_html.count('<link rel="stylesheet"') == 0
    assert '<link rel="stylesheet" href="vendor/google/google-icons.css">' not in index_html
    assert "font-family: 'Material Symbols Outlined'" in index_html
    assert "html:not(.material-icons-ready) x-icon" in index_html
    assert '<script type="module" src="/js/icons.js"></script>' in index_html
    assert index_html.count('rel="preload" as="style"') == 20
    assert index_html.count("onload=\"this.onload=null;this.rel='stylesheet'\"") == 20
    assert 'id="startup-splash"' not in index_html
    assert 'document.addEventListener("webui-bundle-loaded"' not in index_html


def test_startup_splash_is_handed_to_the_index_and_fades_when_ready() -> None:
    splash_html = (PROJECT_ROOT / "webui" / "splash.html").read_text(
        encoding="utf-8"
    )
    index_html = (PROJECT_ROOT / "webui" / "index.html").read_text(encoding="utf-8")
    extensions_js = (PROJECT_ROOT / "webui" / "js" / "extensions.js").read_text(
        encoding="utf-8"
    )

    assert 'id="startup-splash"' not in index_html
    assert 'data-splash-theme="dark"' not in index_html
    assert '<main id="startup-transition"' not in index_html
    assert 'id="startup-transition-critical"' in index_html
    assert 'document.addEventListener("webui-extensions-loaded"' in index_html
    assert 'overlay.classList.add("startup-transition-leaving")' in index_html
    assert 'document.fonts.load(\'24px "Material Symbols Outlined"\')' in index_html
    assert (
        'document.addEventListener("DOMContentLoaded", loadMaterialIcons, { once: true })'
        in index_html
    )
    assert 'localStorage.getItem("darkMode") === "false"' in index_html
    assert "webuiExtensions: {{webui_extension_manifest}}" in index_html
    assert 'manifestExtensionPaths("html", extensionPoint)' in extensions_js
    assert 'manifestExtensionPaths("js", extensionPoint)' in extensions_js
    assert 'export let initialHtmlExtensionsLoaded = false' in extensions_js
    assert 'const LOADING_SELECTOR = "x-component > .loading:empty, x-extension.loading"' in extensions_js
    assert 'targetElement.classList.add("loading")' in extensions_js
    assert 'targetElement.classList.remove("loading")' in extensions_js
    assert 'document.dispatchEvent(new Event("webui-extensions-loaded"))' in extensions_js
    assert "globalThis.Alpine.nextTick" in extensions_js
    assert "pendingHtmlImports" not in extensions_js
    assert "data-extension-loaded" not in extensions_js
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in splash_html
    assert '<main id="startup-transition"' in splash_html
    assert 'localStorage.getItem("darkMode") === "false"' in splash_html
    assert_bootstrap_assets_are_self_contained(splash_html)


def test_generic_loading_indicator_has_a_shared_default_delay() -> None:
    modals_css = (PROJECT_ROOT / "webui" / "css" / "modals.css").read_text(
        encoding="utf-8"
    )

    assert "--loading-delay: 500ms" in modals_css
    assert "fadeIn 500ms ease-out var(--loading-delay) forwards" in modals_css
    assert "fadeIn 0s linear var(--loading-delay) forwards" in modals_css
