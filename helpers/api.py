from abc import abstractmethod
import json
import threading
from urllib.parse import urlsplit, unquote
from functools import wraps
from pathlib import Path
from typing import Union, Dict, Any
from flask import (
    Request,
    Response,
    jsonify,
    Flask,
    session,
    request,
    send_file,
    redirect,
    url_for,
)
from werkzeug.wrappers.response import Response as BaseResponse
from helpers.print_style import PrintStyle
from helpers.errors import format_error
from helpers import files, cache

ThreadLockType = Union[threading.Lock, threading.RLock]

CACHE_AREA = "api_handlers(api)"
# cache.toggle_area(CACHE_AREA, False)  # cache off for now

Input = dict
Output = Union[Dict[str, Any], Response]


class ApiHandler:
    def __init__(self, app: Flask, thread_lock: ThreadLockType):
        self.app = app
        self.thread_lock = thread_lock

    @classmethod
    def requires_loopback(cls) -> bool:
        return False

    @classmethod
    def requires_api_key(cls) -> bool:
        return False

    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    @classmethod
    def requires_csrf(cls) -> bool:
        return cls.requires_auth()

    @abstractmethod
    async def process(self, input: Input, request: Request) -> Output:
        pass

    async def handle_request(self, request: Request) -> Response:
        try:
            # input data from request based on type
            input_data: Input = {}
            if request.is_json:
                try:
                    if request.data:  # Check if there's any data
                        input_data = request.get_json()
                    # If empty or not valid JSON, use empty dict
                except Exception as e:
                    # Just log the error and continue with empty input
                    PrintStyle().print(f"Error parsing JSON: {str(e)}")
                    input_data = {}
            else:
                # input_data = {"data": request.get_data(as_text=True)}
                input_data = {}

            # process via handler
            output = await self.process(input_data, request)

            # return output based on type
            if isinstance(output, Response):
                return output
            else:
                response_json = json.dumps(output)
                return Response(
                    response=response_json, status=200, mimetype="application/json"
                )

            # return exceptions with 500
        except Exception as e:
            from helpers.durable.runtime import service
            owner = service()
            if owner and getattr(owner, "distributed", False):
                from helpers.durable.resources import ResourceHeld
                from helpers.durable.workspaces import WorkspaceHeld
                if isinstance(e, (ResourceHeld, WorkspaceHeld)):
                    return Response(json.dumps({"error": str(e), "code": "shared_resource_held"}),
                                    status=409, mimetype="application/json")
                # Database/provider errors can embed DSNs or private call data.
                # Shared-operation failures must not use the legacy traceback
                # response or print unfiltered connection diagnostics.
                return Response(json.dumps({"error": "Shared recovery operation failed safely. Refresh before retrying."}),
                                status=409 if isinstance(e, ValueError) else 503, mimetype="application/json")
            error = format_error(e)
            PrintStyle.error(f"API error: {error}")
            return Response(response=error, status=500, mimetype="text/plain")

    # get context to run agent zero in
    def use_context(self, ctxid: str, create_if_not_exists: bool = True):
        from helpers.durable.runtime import service
        owner = service()
        if owner and getattr(owner, "distributed", False):
            from agent import AgentContext
            if not ctxid:
                raise ValueError("Shared recovery requires an explicit chat identity.")
            headers = owner.sync("list_run_headers", context_id=ctxid)
            if headers or owner.sync("get_projection", "chat:" + ctxid):
                context = AgentContext.get(ctxid)
                turn = getattr(context, "_durable_turn", None) if context else None
                if not turn or not owner.sync("owns", turn.run_id):
                    raise ValueError("This chat belongs to shared recovery. Route the operation to its execution owner.")
        from helpers.context_utils import use_context as _use_context
        return _use_context(self.thread_lock, ctxid, create_if_not_exists)


from helpers.network import is_loopback_address


def is_safe_next_url(value: str | None) -> bool:
    """Return True when value is a safe same-origin redirect target."""
    if not value:
        return False
    if "\r" in value or "\n" in value:
        return False
    # Reject raw backslashes (browsers normalize `/\host` to `//host` -> external).
    if "\\" in value:
        return False

    # Decode percent-escapes so encoded backslashes (e.g. `%5C`) are caught too.
    decoded = unquote(value)
    if "\\" in decoded:
        return False

    parsed = urlsplit(decoded)
    if parsed.scheme or parsed.netloc:
        return False

    # Require an absolute path within this origin, but reject protocol-relative URLs.
    return parsed.path.startswith("/") and not parsed.path.startswith("//")


def get_safe_next_url(value: str | None, fallback: str | None = None) -> str | None:
    """Return value if it is a safe next URL, otherwise return a safe fallback."""
    if is_safe_next_url(value):
        return value
    if is_safe_next_url(fallback):
        return fallback
    return None


def get_current_request_next_url() -> str:
    """Return the current request path/query as a safe relative redirect target."""
    next_url = request.full_path if request.query_string else request.path
    return get_safe_next_url(next_url, url_for("serve_index")) or url_for("serve_index")


def requires_api_key(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        from helpers.settings import get_settings

        valid_api_key = get_settings()["mcp_server_token"]

        if api_key := request.headers.get("X-API-KEY"):
            if api_key != valid_api_key:
                return Response("Invalid API key", 401)
        elif request.json and request.json.get("api_key"):
            api_key = request.json.get("api_key")
            if api_key != valid_api_key:
                return Response("Invalid API key", 401)
        else:
            return Response("API key required", 401)
        return await f(*args, **kwargs)

    return decorated


def requires_loopback(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        if not is_loopback_address(str(request.remote_addr)):
            return Response("Access denied.", 403, {})
        return await f(*args, **kwargs)

    return decorated


def requires_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        from helpers import login

        user_pass_hash = login.get_credentials_hash()
        if not user_pass_hash:
            return await f(*args, **kwargs)
        if session.get("authentication") != user_pass_hash:
            return redirect(url_for("login_handler", next=get_current_request_next_url()))
        return await f(*args, **kwargs)

    return decorated


def csrf_protect(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        from helpers import runtime

        token = session.get("csrf_token")
        header = request.headers.get("X-CSRF-Token")
        cookie = request.cookies.get("csrf_token_" + runtime.get_runtime_id())
        sent = header or cookie
        if not token or not sent or token != sent:
            return Response("CSRF token missing or invalid", 403)
        return await f(*args, **kwargs)

    return decorated


def register_api_route(app: Flask, lock: ThreadLockType) -> None:
    from helpers.modules import load_classes_from_file
    from helpers import plugins

    async def _dispatch(path: str) -> BaseResponse:
        # Return cached wrapped handler if available
        cached = cache.get(CACHE_AREA, path)
        if cached is not None:
            return await cached()

        # Resolve file path for the handler
        # Try built-in and plugin api folders before the user fallback
        handler_cls: type[ApiHandler] | None = None

        # Check built-in python/api/<path>.py
        builtin_file = files.get_abs_path(f"api/{path}.py")
        if files.is_in_dir(builtin_file, files.get_abs_path("api")) and files.exists(
            builtin_file
        ):
            classes = load_classes_from_file(builtin_file, ApiHandler)
            if classes:
                handler_cls = classes[0]

        # Check plugin api folders: path format plugins/<plugin_name>/<handler>
        if handler_cls is None and path.startswith("plugins/"):
            parts = path.split("/", 2)
            if len(parts) == 3:
                _, plugin_name, handler_name = parts
                plugin_dir = plugins.find_plugin_dir(plugin_name)
                if plugin_dir:
                    plugin_file = Path(plugin_dir) / "api" / f"{handler_name}.py"
                    if plugin_file.is_file():
                        classes = load_classes_from_file(str(plugin_file), ApiHandler)
                        if classes:
                            handler_cls = classes[0]

        # Check user api/<path>.py
        if handler_cls is None:
            user_api_dir = files.get_abs_path(files.USER_DIR, files.API_DIR)
            user_file = files.get_abs_path(user_api_dir, f"{path}.py")
            if files.is_in_dir(user_file, user_api_dir) and files.exists(user_file):
                classes = load_classes_from_file(user_file, ApiHandler)
                if classes:
                    handler_cls = classes[0]

        if handler_cls is None:
            return Response(f"API endpoint not found: {path}", 404)

        # Check method is allowed
        if request.method not in handler_cls.get_methods():
            return Response(f"Method {request.method} not allowed for: {path}", 405)

        # Build handler call, wrapping with security decorators as required
        async def call_handler() -> BaseResponse:
            instance = handler_cls(app, lock)
            return await instance.handle_request(request=request)

        handler_fn = call_handler
        if handler_cls.requires_csrf():
            handler_fn = csrf_protect(handler_fn)
        if handler_cls.requires_api_key():
            handler_fn = requires_api_key(handler_fn)
        if handler_cls.requires_auth():
            handler_fn = requires_auth(handler_fn)
        if handler_cls.requires_loopback():
            handler_fn = requires_loopback(handler_fn)

        cache.add(CACHE_AREA, path, handler_fn)
        return await handler_fn()

    app.add_url_rule(
        "/api/<path:path>",
        "api_dispatch",
        _dispatch,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )


def register_watchdogs():
    from helpers import watchdog
    from helpers.ws import CACHE_AREA as WS_CACHE_AREA


    def on_api_change(items: list[watchdog.WatchItem]):
        PrintStyle.debug("API endpoint watchdog triggered:", items)
        cache.clear(CACHE_AREA)
        cache.clear(WS_CACHE_AREA)

    watchdog.add_watchdog(
        "api_handlers",
        roots=[
            files.get_abs_path(files.API_DIR),
            files.get_abs_path(files.USER_DIR, files.API_DIR),
        ],
        patterns=["*.py"],
        handler=on_api_change,
    )
