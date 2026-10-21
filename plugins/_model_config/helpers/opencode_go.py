from helpers import files, plugins
from helpers import yaml as yaml_helper

OPENCODE_PROVIDER = "opencode"
OPENCODE_GO_MESSAGES_BASE = "https://opencode.ai/zen/go"
_CATALOG_FILE = "opencode_go_models.yaml"
_ROUTES = ("responses", "messages", "chat")
_CATALOG: dict | None = None


def classify_opencode_go_model(model_name: str) -> str:
    """Return chat, responses, or messages for an OpenCode Go model id."""
    name = str(model_name or "").strip().lower()
    catalog = _catalog()
    for route in _ROUTES:
        if name in catalog["ids"].get(route, ()):
            return route
    for route in ("messages", "chat"):
        for prefix in catalog["prefixes"].get(route, ()):
            if prefix and name.startswith(prefix):
                return route
    return "chat"


def apply_opencode_go_route(provider: str, model_name: str, kwargs: dict, agent=None) -> dict:
    """Select the Go transport and client headers for one built chat model."""
    if str(provider or "").strip().lower() != OPENCODE_PROVIDER:
        return kwargs

    routed = dict(kwargs or {})
    route = classify_opencode_go_model(model_name)
    if route == "responses":
        routed.setdefault("a0_api_mode", "responses")
        routed.setdefault("a0_responses_fallback", False)
    elif route == "messages":
        routed.setdefault("a0_litellm_provider", "anthropic")
        if not str(routed.get("api_base") or "").strip():
            routed["api_base"] = OPENCODE_GO_MESSAGES_BASE

    headers = dict(routed.get("extra_headers") or {})
    headers.setdefault("User-Agent", agent_zero_user_agent())
    session_id = opencode_session_id(agent)
    if session_id:
        headers.setdefault("x-opencode-session", session_id)
    routed["extra_headers"] = headers
    return routed


def agent_zero_user_agent() -> str:
    try:
        from helpers import git

        version = str(git.get_version() or "").strip() or "unknown"
    except Exception:
        version = "unknown"
    return f"agent-zero/{version}"


def opencode_session_id(agent) -> str:
    context = getattr(agent, "context", None)
    context_id = str(getattr(context, "id", "") or "").strip()
    if not context_id:
        return ""
    return f"agent-zero-{context_id}"


def _catalog() -> dict:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = _read_catalog()
    return _CATALOG


def _read_catalog() -> dict:
    ids = {route: frozenset() for route in _ROUTES}
    prefixes = {"messages": (), "chat": ()}
    plugin_dir = plugins.find_plugin_dir("_model_config")
    path = files.get_abs_path(plugin_dir, _CATALOG_FILE) if plugin_dir else ""
    if not path or not files.exists(path):
        return {"ids": ids, "prefixes": prefixes}

    data = yaml_helper.loads(files.read_file(path))
    if not isinstance(data, dict):
        return {"ids": ids, "prefixes": prefixes}

    for route in _ROUTES:
        values = data.get(route) or []
        if isinstance(values, list):
            ids[route] = frozenset(
                str(item).strip().lower() for item in values if str(item).strip()
            )

    raw_prefixes = data.get("prefixes") if isinstance(data.get("prefixes"), dict) else {}
    for route in ("messages", "chat"):
        values = raw_prefixes.get(route) or []
        if isinstance(values, list):
            prefixes[route] = tuple(
                str(item).strip().lower() for item in values if str(item).strip()
            )
    return {"ids": ids, "prefixes": prefixes}
