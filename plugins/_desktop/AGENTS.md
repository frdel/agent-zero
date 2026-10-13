# Desktop Plugin DOX

## Purpose

- Own the Agent Zero Linux desktop runtime, Xpra/Xfce session integration, and live desktop surface.

## Ownership

- `helpers/` owns desktop routes, session lifecycle, state, and prompt context.
- `api/desktop_session.py` owns desktop session API behavior.
- `hooks.py` owns route registration and plugin lifecycle hooks.
- `prompts/`, `assets/`, `skills/`, `extensions/`, and `webui/` own desktop context, assets, skill guidance, hooks, and panel UI.

## Local Contracts

- Preserve session startup, cleanup, and route protection for desktop access.
- Resize the system desktop to the active canvas or modal dimensions through `virtual_desktop.resize_display`, retaining its minimum/maximum bounds. Do not replace narrow or portrait viewport sizes with a default landscape resolution.
- Apply shared `virtual_desktop.XPRA_START_ENV` defaults to Xpra launches and restarts while preserving inherited overrides. Disable local shared-memory transport for the WebSocket viewer.
- Keep the Xpra server, client modules, and GTK introspection runtime present as one compatible stack; Xpra shadow sessions import all three even when users connect only through HTML5.
- Route APT commands through `system_packages.run_runtime_apt` so existing Kali containers repair from the build's snapshot. Preserve the installed Xpra component version. If GTK needs a missing ATK typelib, align ATK's version-locked libraries and any installed optional components with the build's pinned snapshot version; do not fetch dependencies from rolling.
- `helpers/refresh_xpra_index.sh` owns the build/runtime Xpra index workaround: let APT authenticate `Packages.gz` directly, then move its cache to the standard package-index filename. Scope the refresh to the supplied signed Xpra source, preserve other cached indexes, and stop on authentication, download, or cache-move failures.
- Keep desktop state injected into prompts accurate and bounded.
- Rename open LibreOffice documents through native Save As so unsaved edits and subsequent WebUI/native saves follow the new path. `helpers/rename_office_document.py` runs with system Python/UNO, connects to the existing profile through a local named pipe, and matches the full document URL; never select a document by basename alone. Retain the document's format/filter and encryption properties, and disallow target overwrite. Closed documents retain filesystem rename behavior.
- Do not expose desktop routes without the expected auth protections.
- Keep Desktop host visibility tied to an attached modal or canvas host; modal cleanup may preserve the iframe in keepalive, but must not leave stale modal mode behind.
- Keep LibreOffice Writer as the default handler for Markdown and plain text files; keep Agent Zero Editor available as a secondary Open With target through the desktop intent bridge.
- Style the shutdown-state restart action with shared `btn btn-field`, matching Open Browser.
- Use shared `surface-workspace` and `--surface-background` for panel, body, and viewer backdrops so shutdown/loading states match the lighter Files, Editor, and Browser palette.

## Work Guidance

- Coordinate runtime and panel changes so live UI reflects actual desktop session state.

## Verification

- Smoke-test desktop startup, panel connection, route access, and session cleanup after changes.

## Child DOX Index

No child DOX files.
