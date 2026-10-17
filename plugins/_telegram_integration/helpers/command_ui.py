from __future__ import annotations

import json
from dataclasses import dataclass

from agent import AgentContext
from helpers import files, projects, subagents
from helpers import integration_commands
from helpers.persist_chat import save_tmp_chat
from helpers.state_monitor_integration import mark_dirty_for_context
from plugins._model_config.helpers import model_config
from plugins._telegram_integration.helpers import telegram_client as tc
from plugins._telegram_integration.helpers.constants import (
    CTX_TG_STREAM_ENABLED,
    CTX_TG_TOOLS_ENABLED,
    CTX_TG_BOT,
    CTX_TG_CHAT_ID,
    CTX_TG_CHAT_TYPE,
    CTX_TG_USER_ID,
    CTX_TG_USERNAME,
    STATE_FILE,
)

PAGE_SIZE = 8
SESSION_PAGE_SIZE = 4
CALLBACK_PREFIX = "tg"


@dataclass(frozen=True)
class PickerItem:
    key: str
    label: str


@dataclass(frozen=True)
class SessionItem:
    context: AgentContext
    label: str
    last_message: str
    running: bool


async def handle_command(
    context: AgentContext,
    token: str,
    chat_id: int,
    reply_to_message_id: int | None,
    text: str,
) -> bool:
    parsed = integration_commands.parse_command(text or "", integration="telegram")
    if not parsed:
        return False
    command, args = parsed
    if command in {"/model", "/config", "/preset"} and not args:
        await send_model_picker(context, token, chat_id, reply_to_message_id, 0)
        return True
    if command == "/project" and not args:
        await send_project_picker(context, token, chat_id, reply_to_message_id, 0)
        return True
    if command in {"/agent", "/profile"} and not args:
        await send_agent_picker(context, token, chat_id, reply_to_message_id, 0)
        return True
    if command in {"/sessions", "/session"} and not args:
        await send_session_picker(context, token, chat_id, reply_to_message_id, 0)
        return True
    if command == "/stream":
        await send_toggle_picker(
            context,
            token,
            chat_id,
            reply_to_message_id,
            CTX_TG_STREAM_ENABLED,
            "Response streaming",
            args,
        )
        return True
    if command == "/tools":
        await send_toggle_picker(
            context,
            token,
            chat_id,
            reply_to_message_id,
            CTX_TG_TOOLS_ENABLED,
            "Tool progress",
            args,
        )
        return True
    return False


async def handle_callback(
    context: AgentContext,
    token: str,
    chat_id: int,
    message_id: int,
    data: str,
) -> bool:
    parts = (data or "").split(":")
    if len(parts) < 3 or parts[0] != CALLBACK_PREFIX:
        return False
    kind, action = parts[1], parts[2]
    value = parts[3] if len(parts) > 3 else ""
    if action == "noop":
        return True
    if action == "page":
        page = _safe_int(value)
        if kind == "model":
            await edit_model_picker(context, token, chat_id, message_id, page)
        elif kind == "project":
            await edit_project_picker(context, token, chat_id, message_id, page)
        elif kind == "agent":
            await edit_agent_picker(context, token, chat_id, message_id, page)
        elif kind == "session":
            await edit_session_picker(context, token, chat_id, message_id, page)
        return True
    if kind == "model" and action in {"set", "clear"}:
        await _select_model(context, _safe_int(value), clear=(action == "clear"))
        await edit_model_picker(context, token, chat_id, message_id, 0, selected=True)
        return True
    if kind == "project" and action in {"set", "clear"}:
        await _select_project(context, _safe_int(value), clear=(action == "clear"))
        await edit_project_picker(context, token, chat_id, message_id, 0, selected=True)
        return True
    if kind == "agent" and action == "set":
        await _select_agent(context, _safe_int(value))
        await edit_agent_picker(context, token, chat_id, message_id, 0, selected=True)
        return True
    if kind == "session" and action == "set":
        selected_context = await _select_session(context, _safe_int(value))
        await edit_session_picker(selected_context or context, token, chat_id, message_id, 0, selected=bool(selected_context))
        return True
    if kind in {"stream", "tools"} and action in {"on", "off"}:
        key = CTX_TG_STREAM_ENABLED if kind == "stream" else CTX_TG_TOOLS_ENABLED
        label = "Response streaming" if kind == "stream" else "Tool progress"
        context.set_data(key, action == "on")
        save_tmp_chat(context)
        mark_dirty_for_context(context.id, reason=f"telegram.{kind}_toggle")
        await edit_toggle_picker(context, token, chat_id, message_id, key, label)
        return True
    return True


async def send_model_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    reply_to_message_id: int | None,
    page: int,
) -> None:
    text, markup = _model_view(context, page)
    await tc.raw_send_text(token, chat_id, text, reply_to_message_id, "HTML", markup)


async def edit_model_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    message_id: int,
    page: int,
    *,
    selected: bool = False,
) -> None:
    text, markup = _model_view(context, page, selected=selected)
    await tc.raw_edit_text(token, chat_id, message_id, text, "HTML", markup)


async def send_project_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    reply_to_message_id: int | None,
    page: int,
) -> None:
    text, markup = _project_view(context, page)
    await tc.raw_send_text(token, chat_id, text, reply_to_message_id, "HTML", markup)


async def edit_project_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    message_id: int,
    page: int,
    *,
    selected: bool = False,
) -> None:
    text, markup = _project_view(context, page, selected=selected)
    await tc.raw_edit_text(token, chat_id, message_id, text, "HTML", markup)


async def send_agent_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    reply_to_message_id: int | None,
    page: int,
) -> None:
    text, markup = _agent_view(context, page)
    await tc.raw_send_text(token, chat_id, text, reply_to_message_id, "HTML", markup)


async def edit_agent_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    message_id: int,
    page: int,
    *,
    selected: bool = False,
) -> None:
    text, markup = _agent_view(context, page, selected=selected)
    await tc.raw_edit_text(token, chat_id, message_id, text, "HTML", markup)


async def send_toggle_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    reply_to_message_id: int | None,
    key: str,
    label: str,
    args: str = "",
) -> None:
    desired = _parse_toggle(args)
    if desired is not None:
        context.set_data(key, desired)
        save_tmp_chat(context)
        mark_dirty_for_context(context.id, reason=f"telegram.{key}")
    text, markup = _toggle_view(context, key, label)
    await tc.raw_send_text(token, chat_id, text, reply_to_message_id, "HTML", markup)


async def edit_toggle_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    message_id: int,
    key: str,
    label: str,
) -> None:
    text, markup = _toggle_view(context, key, label)
    await tc.raw_edit_text(token, chat_id, message_id, text, "HTML", markup)


async def send_session_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    reply_to_message_id: int | None,
    page: int,
) -> None:
    text, markup = _session_view(context, page)
    await tc.raw_send_text(token, chat_id, text, reply_to_message_id, "HTML", markup)


async def edit_session_picker(
    context: AgentContext,
    token: str,
    chat_id: int,
    message_id: int,
    page: int,
    *,
    selected: bool = False,
) -> None:
    text, markup = _session_view(context, page, selected=selected)
    await tc.raw_edit_text(token, chat_id, message_id, text, "HTML", markup)


def _model_view(
    context: AgentContext,
    page: int,
    *,
    selected: bool = False,
) -> tuple[str, dict | None]:
    presets = [
        PickerItem(str(preset.get("name", "")), str(preset.get("name", "")))
        for preset in model_config.get_presets()
        if isinstance(preset, dict) and preset.get("name")
    ]
    current = context.get_data("chat_model_override")
    current_name = current.get("preset_name") if isinstance(current, dict) else ""
    effective_name = model_config.get_effective_preset_name(context.agent0)
    status = f"Current model: <b>{_html(effective_name)}</b>"
    if not model_config.is_chat_override_allowed(context.agent0):
        return status + "\nPer-chat model switching is disabled.", None
    if selected:
        status = "Model updated.\n" + status
    rows = _paged_buttons("model", presets, page, effective_name)
    rows.append([{"text": "Use scoped preset", "callback_data": "tg:model:clear"}])
    return status, {"inline_keyboard": rows}


def _project_view(
    context: AgentContext,
    page: int,
    *,
    selected: bool = False,
) -> tuple[str, dict | None]:
    items = [
        PickerItem(str(item.get("name", "")), str(item.get("title") or item.get("name") or ""))
        for item in projects.get_active_projects_list() or []
        if item.get("name")
    ]
    current = context.get_data("project") or ""
    status = f"Current project: <b>{_html(_label_for(items, current) or 'none')}</b>"
    if selected:
        status = "Project updated.\n" + status
    rows = _paged_buttons("project", items, page, current)
    rows.append([{"text": "No project", "callback_data": "tg:project:clear"}])
    return status, {"inline_keyboard": rows}


def _agent_view(
    context: AgentContext,
    page: int,
    *,
    selected: bool = False,
) -> tuple[str, dict | None]:
    items = [
        PickerItem(str(item.get("key", "")), str(item.get("label") or item.get("key") or ""))
        for item in subagents.get_all_agents_list()
        if item.get("key")
    ]
    current = getattr(context.agent0.config, "profile", "") or "agent0"
    status = f"Current agent: <b>{_html(_label_for(items, current) or current)}</b>"
    if context.is_running():
        status += "\nAgent profile can be changed after the current run finishes."
    elif selected:
        status = "Agent updated.\n" + status
    rows = _paged_buttons("agent", items, page, current, disabled=context.is_running())
    if not rows:
        return status + "\nNo agent profiles were found.", None
    return status, {"inline_keyboard": rows}


def _toggle_view(context: AgentContext, key: str, label: str) -> tuple[str, dict]:
    enabled = _toggle_enabled(context, key)
    kind = "stream" if key == CTX_TG_STREAM_ENABLED else "tools"
    state = "enabled" if enabled else "disabled"
    text = f"{_html(label)}: <b>{state}</b>"
    rows = [[
        {"text": ("On" if enabled else "Turn on"), "callback_data": f"tg:{kind}:on"},
        {"text": ("Off" if not enabled else "Turn off"), "callback_data": f"tg:{kind}:off"},
    ]]
    return text, {"inline_keyboard": rows}


def _session_view(
    context: AgentContext,
    page: int,
    *,
    selected: bool = False,
) -> tuple[str, dict | None]:
    items = _session_items()
    current_label = _session_label(context)
    status = f"Current session: <b>{_html(current_label)}</b>"
    if context.is_running():
        status += "\nSession switching is available after the current run finishes."
    elif selected:
        status = "Session switched.\n" + status
    if not items:
        return status + "\nNo sessions were found.", None

    total = len(items)
    page = _clamp_page(page, total, SESSION_PAGE_SIZE)
    start = page * SESSION_PAGE_SIZE
    end = min(start + SESSION_PAGE_SIZE, total)
    rows: list[list[dict[str, str]]] = []
    for index, item in enumerate(items[start:end], start=start):
        marker = "• " if item.context.id == context.id else ""
        suffix = " (running)" if item.running else ""
        action = "noop" if context.is_running() or item.running else "set"
        rows.append([{
            "text": f"{marker}{item.label}{suffix}"[:64],
            "callback_data": f"tg:session:{action}:{index}",
        }])

    nav: list[dict[str, str]] = []
    if page > 0:
        nav.append({"text": "Prev", "callback_data": f"tg:session:page:{page - 1}"})
    if end < total:
        nav.append({"text": "Next", "callback_data": f"tg:session:page:{page + 1}"})
    if nav:
        rows.append(nav)

    range_text = f"\nShowing {start + 1}-{end} of {total}."
    return status + range_text, {"inline_keyboard": rows}


async def _select_model(context: AgentContext, index: int, *, clear: bool = False) -> None:
    if not model_config.is_chat_override_allowed(context.agent0):
        return
    if clear:
        context.set_data("chat_model_override", None)
    else:
        presets = [preset for preset in model_config.get_presets() if preset.get("name")]
        if index < 0 or index >= len(presets):
            return
        context.set_data("chat_model_override", {"preset_name": presets[index]["name"]})
    save_tmp_chat(context)
    mark_dirty_for_context(context.id, reason="telegram.model_select")


async def _select_project(context: AgentContext, index: int, *, clear: bool = False) -> None:
    if clear:
        projects.deactivate_project(context.id)
        return
    items = [item for item in projects.get_active_projects_list() or [] if item.get("name")]
    if index < 0 or index >= len(items):
        return
    projects.activate_project(context.id, str(items[index]["name"]))


async def _select_agent(context: AgentContext, index: int) -> None:
    if context.is_running():
        return
    from initialize import initialize_agent

    items = [item for item in subagents.get_all_agents_list() if item.get("key")]
    if index < 0 or index >= len(items):
        return
    profile = str(items[index]["key"])
    config = initialize_agent(override_settings={"agent_profile": profile})
    context.config = config
    context.agent0.config = config
    context.set_data("agent_profile_manually_set", True)
    save_tmp_chat(context)
    mark_dirty_for_context(context.id, reason="telegram.agent_select")


async def _select_session(context: AgentContext, index: int) -> AgentContext | None:
    if context.is_running():
        return None
    items = _session_items()
    if index < 0 or index >= len(items):
        return None
    target = items[index].context
    if target.is_running():
        return None

    _copy_telegram_binding(context, target)
    _set_session_mapping(target)
    save_tmp_chat(target)
    mark_dirty_for_context(context.id, reason="telegram.session_unselect")
    mark_dirty_for_context(target.id, reason="telegram.session_select")
    return target


def _session_items() -> list[SessionItem]:
    contexts = sorted(
        AgentContext.all(),
        key=lambda item: str(item.output().get("last_message") or ""),
        reverse=True,
    )
    return [
        SessionItem(
            context=item,
            label=_session_label(item),
            last_message=str(item.output().get("last_message") or ""),
            running=item.is_running(),
        )
        for item in contexts
    ]


def _session_label(context: AgentContext) -> str:
    return str(context.name or context.id or "Session")


def _copy_telegram_binding(source: AgentContext, target: AgentContext) -> None:
    for key in (
        CTX_TG_BOT,
        CTX_TG_CHAT_ID,
        CTX_TG_CHAT_TYPE,
        CTX_TG_USER_ID,
        CTX_TG_USERNAME,
    ):
        if key in source.data:
            target.data[key] = source.data[key]


def _set_session_mapping(context: AgentContext) -> None:
    bot_name = str(context.data.get(CTX_TG_BOT) or "")
    user_id = context.data.get(CTX_TG_USER_ID)
    chat_id = context.data.get(CTX_TG_CHAT_ID)
    if not bot_name or user_id is None or chat_id is None:
        return
    key = f"{bot_name}:{int(user_id)}:{int(chat_id)}"
    state = _load_telegram_state()
    chats = state.setdefault("chats", {})
    chats[key] = context.id
    _save_telegram_state(state)


def _load_telegram_state() -> dict:
    path = files.get_abs_path(STATE_FILE)
    if not files.exists(path):
        return {}
    try:
        return json.loads(files.read_file(path))
    except Exception:
        return {}


def _save_telegram_state(state: dict) -> None:
    path = files.get_abs_path(STATE_FILE)
    files.make_dirs(path)
    files.write_file(path, json.dumps(state))


def _paged_buttons(
    kind: str,
    items: list[PickerItem],
    page: int,
    current: str,
    *,
    disabled: bool = False,
) -> list[list[dict[str, str]]]:
    page = max(0, page)
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages - 1)
    start = page * PAGE_SIZE
    rows: list[list[dict[str, str]]] = []
    for offset, item in enumerate(items[start:start + PAGE_SIZE], start=start):
        marker = "• " if item.key == current else ""
        action = "noop" if disabled else "set"
        rows.append([{
            "text": f"{marker}{item.label}"[:64],
            "callback_data": f"tg:{kind}:{action}:{offset}",
        }])
    nav: list[dict[str, str]] = []
    if page > 0:
        nav.append({"text": "Prev", "callback_data": f"tg:{kind}:page:{page - 1}"})
    if page < total_pages - 1:
        nav.append({"text": "Next", "callback_data": f"tg:{kind}:page:{page + 1}"})
    if nav:
        rows.append(nav)
    return rows


def _toggle_enabled(context: AgentContext, key: str) -> bool:
    value = context.get_data(key)
    return True if value is None else bool(value)


def _parse_toggle(args: str) -> bool | None:
    value = (args or "").strip().lower()
    if value in {"on", "enable", "enabled", "yes", "true", "1"}:
        return True
    if value in {"off", "disable", "disabled", "no", "false", "0"}:
        return False
    return None


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clamp_page(page: int, total_items: int, page_size: int) -> int:
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    return min(max(0, page), total_pages - 1)


def _label_for(items: list[PickerItem], key: str) -> str:
    for item in items:
        if item.key == key:
            return item.label
    return key


def _html(value: str) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
