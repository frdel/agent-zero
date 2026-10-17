from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Iterable
from urllib.parse import quote, unquote, urljoin, urlsplit

from helpers import cache, files

if TYPE_CHECKING:
    from agent import Agent


_CACHE_AREA = "ui_asset_bundle(extensions)(plugins)"
_CACHE_KEY_PREFIX = "webui"
_LOCAL_ORIGIN = "https://agent-zero.local"
_BUNDLE_POLICY_VERSION = "text-startup-v4-512k"
_BUNDLE_SUFFIXES = {".css", ".htm", ".html", ".js", ".mjs", ".xhtml"}
_WEBUI_EXTENSION_ENTRY_SUFFIXES = {".htm", ".html", ".js", ".mjs", ".xhtml"}
_MAX_BUNDLE_FILE_BYTES = 512 * 1024

_CSS_REFERENCE_RES = (
    re.compile(r"url\(\s*(?:[\"'])?([^\"')\s]+)", re.IGNORECASE),
    re.compile(
        r"@import\s+(?:url\(\s*)?[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    ),
)
_JS_REFERENCE_RES = (
    re.compile(
        r"(?:import|export)\s+(?:[^\"';]*?\s+from\s+)?[\"']([^\"']+)[\"']",
        re.MULTILINE,
    ),
    re.compile(r"\bimport\(\s*[\"']([^\"']+)[\"']\s*\)"),
    re.compile(r"\b(?:Worker|SharedWorker)\(\s*[\"']([^\"']+)[\"']"),
    re.compile(r"\bimportScripts\(\s*[\"']([^\"']+)[\"']"),
)
_QUOTED_ASSET_RE = re.compile(
    r'''["']((?:/|\./|\.\./)[^"'`$?]+\.[a-zA-Z0-9]{1,12}(?:\?[^"'`]*)?)["']'''
)


class _HtmlAssetReferences(HTMLParser):
    _URL_ATTRIBUTES = {
        "link": ("href",),
        "script": ("src",),
    }

    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.component_references: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        tag = tag.lower()
        if tag == "x-component":
            path = attributes.get("path")
            if path:
                self.component_references.append(path)
        for attribute in self._URL_ATTRIBUTES.get(tag, ()):
            value = attributes.get(attribute)
            if value:
                self.references.append(value)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)


class _AssetRoot:
    def __init__(self, path: Path, url_prefix: str) -> None:
        self.path = path.resolve()
        self.url_prefix = "/" + url_prefix.strip("/") if url_prefix != "/" else "/"

    def __hash__(self) -> int:
        return hash((self.path, self.url_prefix))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, _AssetRoot)
            and self.path == other.path
            and self.url_prefix == other.url_prefix
        )


def get_ui_asset_bundle(
    entry_urls: Iterable[str],
    agent: "Agent | None" = None,
) -> dict:
    """Build a versioned recursive text-asset bundle from the supplied entries."""
    entries = list(dict.fromkeys(entry_urls))
    cache_key = _cache_key(entries)

    roots, extension_roots = _get_asset_roots(agent)

    # WebUI extension paths are injected into the rendered application document
    # at runtime, so they cannot be discovered from the supplied source alone.
    # Include those actual extension entry files, then let the same recursive
    # scan discover their component, stylesheet, and module dependencies.
    # Unrelated files stay lazy and use the service worker's ordinary
    # fetch-and-cache fallback.
    for root in extension_roots:
        for path in _iter_root_files(
            root.path,
            suffixes=_WEBUI_EXTENSION_ENTRY_SUFFIXES,
        ):
            url = _url_for_path(path, roots)
            if url:
                entries.append(url)

    # Recompute the signature on every call: patched core or plugin webui
    # assets must invalidate the cached bundle without a process restart.
    # The filesystem stat cost is acceptable for a once-per-page-load
    # endpoint; the cached bundle is reused only while it still matches.
    signature = _bundle_signature(roots, entries)
    cached = cache.get(_CACHE_AREA, cache_key)
    if cached is not None and cached["signature"] == signature:
        return cached["bundle"]

    result = _build_asset_bundle(entries, roots, signature)
    cache.add(
        _CACHE_AREA,
        cache_key,
        {"signature": signature, "bundle": result},
    )
    return result


def _cache_key(entry_urls: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for entry_url in sorted(set(entry_urls)):
        digest.update(entry_url.encode("utf-8"))
        digest.update(b"\0")
    return f"{_CACHE_KEY_PREFIX}:{digest.hexdigest()[:20]}"


def _build_asset_bundle(
    entry_urls: Iterable[str],
    roots: list[_AssetRoot],
    signature: str,
) -> dict:
    pending: list[str] = []
    queued: set[str] = set()
    entries: dict[str, list[str]] = {}

    def enqueue(url: str) -> None:
        normalized = _normalize_url(url)
        suffix = Path(unquote(urlsplit(normalized).path)).suffix.lower() if normalized else ""
        if normalized and suffix in _BUNDLE_SUFFIXES:
            if normalized not in queued:
                queued.add(normalized)
                pending.append(normalized)

    for entry_url in entry_urls:
        enqueue(entry_url)

    while pending:
        url = pending.pop()
        path = _path_for_url(url, roots)
        if path is None:
            continue
        try:
            content = path.read_bytes()
        except OSError:
            continue

        text = _decode_text(content)
        if text is None:
            continue
        if len(content) <= _MAX_BUNDLE_FILE_BYTES:
            entries[url] = [_content_type(path), "text", text]
        for reference in _extract_references(text, url, path.suffix.lower()):
            enqueue(reference)

    return {
        "version": signature[:20],
        "files": {url: entries[url] for url in sorted(entries)},
    }


def serialize_ui_asset_bundle(bundle: dict) -> str:
    """Serialize a UI asset bundle for its JSON endpoint."""
    return json.dumps(
        bundle,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _get_asset_roots(
    agent: "Agent | None",
) -> tuple[list[_AssetRoot], list[_AssetRoot]]:
    from helpers import plugins, subagents

    webui_root = _AssetRoot(Path(files.get_abs_path("webui")), "/")
    extension_roots: list[_AssetRoot] = []
    plugin_webui_roots: list[_AssetRoot] = []

    for path in subagents.get_paths(agent, "extensions/webui"):
        root_path = Path(path).resolve()
        if not root_path.is_dir() or not files.is_in_base_dir(str(root_path)):
            continue
        relative = files.deabsolute_path(str(root_path)).replace("\\", "/")
        extension_roots.append(_AssetRoot(root_path, f"/{relative}"))

    for path in plugins.get_enabled_plugin_paths(agent, "webui"):
        root_path = Path(path).resolve()
        if not root_path.is_dir() or not files.is_in_base_dir(str(root_path)):
            continue
        relative = files.deabsolute_path(str(root_path)).replace("\\", "/")
        plugin_webui_roots.append(_AssetRoot(root_path, f"/{relative}"))

    extension_roots = list(dict.fromkeys(extension_roots))
    plugin_webui_roots = list(dict.fromkeys(plugin_webui_roots))
    roots = list(dict.fromkeys([*extension_roots, *plugin_webui_roots, webui_root]))
    roots.sort(key=lambda root: len(root.url_prefix), reverse=True)
    return roots, extension_roots


def _iter_root_files(
    root: Path,
    suffixes: set[str] | None = None,
    recursive: bool = True,
) -> Iterable[Path]:
    if not root.is_dir():
        return
    candidates = root.rglob("*") if recursive else root.glob("*")
    for path in sorted(candidates, key=lambda item: item.as_posix()):
        if not path.is_file() or (suffixes and path.suffix.lower() not in suffixes):
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        yield resolved


def _bundle_signature(roots: list[_AssetRoot], entry_urls: Iterable[str]) -> str:
    digest = hashlib.sha256()
    digest.update(_BUNDLE_POLICY_VERSION.encode("ascii"))
    digest.update(b"\0")
    for entry_url in sorted(set(entry_urls)):
        digest.update(entry_url.encode("utf-8"))
        digest.update(b"\0")
    for root in roots:
        digest.update(root.url_prefix.encode("utf-8"))
        digest.update(b"\0")
        for path in _iter_root_files(root.path, suffixes=_BUNDLE_SUFFIXES):
            try:
                stat = path.stat()
                relative = path.relative_to(root.path).as_posix()
            except (OSError, ValueError):
                continue
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
            digest.update(b":")
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()


def _url_for_path(path: Path, roots: list[_AssetRoot]) -> str | None:
    resolved = path.resolve()
    for root in roots:
        try:
            relative = resolved.relative_to(root.path).as_posix()
        except ValueError:
            continue
        prefix = "" if root.url_prefix == "/" else root.url_prefix
        return f"{prefix}/{quote(relative, safe='/-._~')}"
    return None


def _path_for_url(url: str, roots: list[_AssetRoot]) -> Path | None:
    url_path = unquote(urlsplit(url).path)
    for root in roots:
        prefix = root.url_prefix
        if prefix == "/":
            relative = url_path.lstrip("/")
        elif url_path.startswith(prefix + "/"):
            relative = url_path[len(prefix) + 1 :]
        else:
            continue
        candidate = (root.path / relative).resolve()
        try:
            candidate.relative_to(root.path)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def _extract_references(text: str, base_url: str, suffix: str) -> list[str]:
    references: list[str] = []
    suffix = suffix.lower()

    if suffix in {".html", ".htm", ".xhtml"}:
        parser = _HtmlAssetReferences()
        parser.feed(text)
        references.extend(
            resolved
            for reference in parser.references
            if (resolved := _resolve_reference(reference, base_url))
        )
        references.extend(
            resolved
            for reference in parser.component_references
            if (resolved := _resolve_component_reference(reference))
        )
        references.extend(_extract_css_references(text, base_url))
        references.extend(_extract_js_references(text, base_url))
    elif suffix == ".css":
        references.extend(_extract_css_references(text, base_url))
    elif suffix in {".js", ".mjs"}:
        references.extend(_extract_js_references(text, base_url))
    if suffix in {".html", ".htm", ".xhtml", ".js", ".mjs"}:
        references.extend(
            resolved
            for reference in _QUOTED_ASSET_RE.findall(text)
            if (resolved := _resolve_reference(reference, base_url))
        )

    return references


def _extract_css_references(text: str, base_url: str) -> list[str]:
    references: list[str] = []
    for pattern in _CSS_REFERENCE_RES:
        references.extend(
            resolved
            for reference in pattern.findall(text)
            if (resolved := _resolve_reference(reference, base_url))
        )
    return references


def _extract_js_references(text: str, base_url: str) -> list[str]:
    references: list[str] = []
    for pattern in _JS_REFERENCE_RES:
        references.extend(
            resolved
            for reference in pattern.findall(text)
            if (resolved := _resolve_reference(reference, base_url))
        )
    return references


def _resolve_component_reference(reference: str) -> str | None:
    if reference.startswith("/"):
        return _normalize_url(reference)
    if reference.startswith("components/"):
        return _normalize_url(f"/{reference}")
    return _normalize_url(f"/components/{reference}")


def _resolve_reference(reference: str, base_url: str) -> str | None:
    reference = reference.strip()
    if not reference or reference.startswith(("#", "data:", "blob:", "javascript:")):
        return None
    absolute = urljoin(f"{_LOCAL_ORIGIN}{base_url}", reference)
    parsed = urlsplit(absolute)
    if f"{parsed.scheme}://{parsed.netloc}" != _LOCAL_ORIGIN:
        return None
    query = f"?{parsed.query}" if parsed.query else ""
    return _normalize_url(f"{parsed.path}{query}")


def _normalize_url(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return None
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{quote(unquote(parsed.path), safe='/-._~')}{query}"


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix in {".js", ".mjs"}:
        return "text/javascript; charset=utf-8"
    return "text/html; charset=utf-8"


def _decode_text(content: bytes) -> str | None:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None
