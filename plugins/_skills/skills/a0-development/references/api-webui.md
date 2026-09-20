# API And WebUI

## Source Anchors

- HTTP handler base and route registration: `/a0/helpers/api.py`
- API DOX: `/a0/api/AGENTS.md`
- WebSocket handler base: `/a0/helpers/ws.py`
- WebUI shell DOX: `/a0/webui/AGENTS.md`
- Component and JS DOX: `/a0/webui/components/AGENTS.md`, `/a0/webui/js/AGENTS.md`
- Frontend extension loading: `/a0/webui/js/extensions.js`

## HTTP API Contract

HTTP API handlers derive from `helpers.api.ApiHandler`:

```python
from flask import Request, Response
from helpers.api import ApiHandler

class MyEndpoint(ApiHandler):
    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        return {"ok": True}
```

Defaults from `ApiHandler`:

| Method | Default |
|---|---|
| `requires_loopback()` | `False` |
| `requires_api_key()` | `False` |
| `requires_auth()` | `True` |
| `get_methods()` | `["POST"]` |
| `requires_csrf()` | `requires_auth()` |

Override these only when the endpoint contract requires it. Keep auth and CSRF protection intact for browser-facing state changes.

## API Routes

`helpers.api.register_api_route(...)` registers:

```text
/api/<path:path>
```

Resolution:

- Built-in endpoint `api/<name>.py` becomes `/api/<name>`.
- Plugin endpoint `plugins/<plugin>/api/<handler>.py` becomes `/api/plugins/<plugin>/<handler>`.

Return a Flask `Response` for files, redirects, custom status codes, and plain text. Return a dictionary for JSON success payloads.

Direct files under `api/*.py` require matching `api/*.py.dox.md`.

## Calling The WebUI API

To use existing features on the user's behalf, read [Operate Agent Zero](operate-agent-zero.md). It covers session authentication and CSRF, project/chat/task workflows, exact ID fields, and result verification. This reference covers implementing API and WebUI behavior.

## WebSocket Handlers

WebSocket handlers live in `api/ws_*.py` or plugin API folders and derive from `helpers.ws.WsHandler`:

```python
from helpers.ws import WsHandler

class MyHandler(WsHandler):
    async def process(self, event: str, data: dict, sid: str) -> dict | None:
        return {"ok": True}
```

`WsHandler` mirrors `ApiHandler` security flags: auth defaults to `True`, CSRF defaults to auth, API-key and loopback default to `False`. Handlers should validate event data before using it and avoid returning secrets or unfiltered exception details.

## WebUI Work

Follow the nearest WebUI DOX before changing frontend files:

- `webui/AGENTS.md` for the shell, CSS, assets, vendor, and extension loader.
- `webui/js/AGENTS.md` for stores, modals, API helpers, and JS infrastructure.
- `webui/components/AGENTS.md` and child docs for Alpine components.

Patterns:

- Store-dependent content should be gated by a `template x-if` guard before using `$store.<name>`.
- Stores are registered with `createStore` from `/js/AlpineStore.js`.
- Modals use `openModal(path)` and `closeModal()` from `/js/modals.js`.
- Plugin settings UIs bind persisted plugin values to `config.*` and modal-only state/actions to `context.*`.
- Plugin UI should use the A0 notification system instead of inline success/error boxes.

## Verification

- Run endpoint-specific tests or nearest API/WebSocket tests for handler behavior.
- For auth, CSRF, upload/download, tunnel, or file endpoints, run security-focused regressions.
- For WebUI changes, use targeted component/store tests or a browser smoke check when practical.
- Check file-level DOX coverage when touching direct `api/*.py` modules.
