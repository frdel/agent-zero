# ui_bundler.py DOX

## Purpose

- Build the versioned recursive text-asset bundle used to prepare the WebUI service-worker cache.
- Keep component and extension loaders independent from transport-level caching.

## Ownership

- `ui_bundler.py` owns generic same-origin text-asset discovery from caller-supplied entries, recursive reference scanning, safe URL-to-file resolution, asset-set versioning, and JSON serialization.
- `ui_bundler.py.dox.md` owns the durable contracts for that behavior.
- Top-level functions:
  - `get_ui_asset_bundle(entry_urls: Iterable[str], agent: Agent | None = None) -> dict`
  - `serialize_ui_asset_bundle(bundle: dict) -> str`

## Runtime Contracts

- The caller supplies one or more entry URLs. The scanner traverses their union once and adds enabled WebUI extension HTML/JavaScript entries because those paths are injected into the rendered document at runtime. It follows generic HTML links/scripts/components, CSS imports/URLs, JavaScript imports/exports/workers, and relative or root-local quoted asset URLs.
- The bundler contains no library-specific path or module-name mappings. References that cannot be derived statically, including runtime-computed URLs, use the service worker's ordinary backend fetch-and-cache fallback.
- Asset URLs resolve only inside the WebUI static root or an enabled WebUI extension/plugin root; external URLs, traversal, and symlink escapes are excluded.
- Valid UTF-8 HTML, CSS, and JavaScript files no larger than 512 KiB each are embedded. Oversized eligible text is still scanned for dependencies but its body is omitted so the browser can request it normally. Images, audio, video, fonts, manifests, and other file types remain under normal browser HTTP caching.
- Every entry carries the response content type required by browsers and native ES modules.
- Bundle versions cover the caller entries, cache policy, and HTML/CSS/JavaScript path/mtime/size inventory. Policy or eligible-file changes therefore advance the service-worker cache version; the helper cache also participates in normal extension/plugin invalidation.
- Caller entry sets have distinct helper-cache keys. Every call recomputes the asset signature and reuses the cached bundle only while the signature still matches, so patched core or plugin WebUI assets invalidate the cached bundle on the next request without a process restart; the signature stat cost runs once per page-load endpoint request.
- Serialized JSON is returned by the authenticated `/ui/asset-bundle` endpoint rather than inserted into the application document. HTTP gzip compresses the shared transfer.

## Work Guidance

- Add format-level reference extractors here; never add mappings for a particular library, component, theme, mode, or file.
- Keep API, WebSocket, navigation, authentication, and other dynamic responses outside the asset bundle.
- Preserve URL identity so native module imports, component fetches, and stylesheet resolution use normal browser semantics.

## Verification

- Run `tests/test_ui_bundler.py` and the WebUI service-worker/startup tests.
- Smoke-test a cold first load and a controlled reload; verify ordinary asset URLs remain visible while their responses come from the service-worker cache after activation.

## Child DOX Index

No child DOX files.
