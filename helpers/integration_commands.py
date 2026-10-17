from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from helpers import message_queue as mq
from helpers import projects
from helpers.persist_chat import save_tmp_chat
from helpers.state_monitor_integration import mark_dirty_for_context
from plugins._model_config.helpers import model_config

if TYPE_CHECKING:
    from agent import AgentContext


_CLEAR_VALUES = {"", "default", "none", "clear", "off"}
_MODEL_INHERIT_VALUES = {"", "none", "clear", "off", "inherit"}


@dataclass(frozen=True)
class IntegrationCommandDef:
    name: str
    description: str
    category: str
    aliases: tuple[str, ...] = ()
    args_hint: str = ""
    menu: bool = True
    integrations: tuple[str, ...] = ()


COMMAND_REGISTRY: tuple[IntegrationCommandDef, ...] = (
    IntegrationCommandDef("commands", "Show all integration commands.", "Info", aliases=("help",)),
    IntegrationCommandDef(
        "status",
        "Show this chat's project, model, agent, and queue state.",
        "Info",
    ),
    IntegrationCommandDef("new", "Start a fresh chat context.", "Session"),
    IntegrationCommandDef(
        "sessions",
        "Show or switch recent chat sessions.",
        "Session",
        aliases=("session",),
        integrations=("telegram",),
    ),
    IntegrationCommandDef("clear", "Reset the current chat context.", "Session", aliases=("reset",)),
    IntegrationCommandDef(
        "queue",
        "Show or manage queued messages.",
        "Session",
        args_hint="[send|clear]",
    ),
    IntegrationCommandDef("send", "Send queued messages now.", "Session", aliases=("push",)),
    IntegrationCommandDef(
        "steer",
        "Intervene in the currently running task.",
        "Session",
        args_hint="<message>",
    ),
    IntegrationCommandDef("pause", "Pause the active run.", "Session"),
    IntegrationCommandDef("resume", "Resume a paused run.", "Session"),
    IntegrationCommandDef("nudge", "Nudge the active run.", "Session"),
    IntegrationCommandDef(
        "stream",
        "Enable or disable Telegram response streaming.",
        "Configuration",
        args_hint="[on|off]",
        integrations=("telegram",),
    ),
    IntegrationCommandDef(
        "tools",
        "Show or hide Telegram tool progress.",
        "Configuration",
        args_hint="[on|off]",
        integrations=("telegram",),
    ),
    IntegrationCommandDef(
        "project",
        "Show or switch the active project.",
        "Configuration",
        args_hint="[name|none]",
    ),
    IntegrationCommandDef(
        "model",
        "Show or switch the chat model preset.",
        "Configuration",
        aliases=("config", "preset"),
        args_hint="[preset|inherit]",
    ),
    IntegrationCommandDef(
        "agent",
        "Show or switch the agent profile.",
        "Configuration",
        aliases=("profile",),
        args_hint="[profile]",
    ),
)


_COMMAND_LOOKUP = {
    f"/{name}": command
    for command in COMMAND_REGISTRY
    for name in (command.name, *command.aliases)
}


def extract_command_line(text: str) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped
    return ""


def parse_command(text: str, *, integration: str | None = None) -> tuple[str, str] | None:
    line = extract_command_line(text)
    if not line.startswith("/"):
        return None

    command, _, args = line.partition(" ")
    command = _normalize_command_token(command)
    resolved = resolve_command(command, integration=integration)
    if not resolved:
        return None

    return f"/{resolved.name}", args.strip()


def resolve_command(command: str, *, integration: str | None = None) -> IntegrationCommandDef | None:
    normalized = _normalize_command_token(command)
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    command_def = _COMMAND_LOOKUP.get(normalized)
    if not command_def or not _is_command_available(command_def, integration):
        return None
    return command_def


def telegram_menu_commands() -> list[tuple[str, str]]:
    return [
        (command.name, _telegram_description(command))
        for command in COMMAND_REGISTRY
        if command.menu and _is_command_available(command, "telegram")
    ]


def command_names(include_aliases: bool = True, *, integration: str | None = None) -> list[str]:
    names: list[str] = []
    for command in COMMAND_REGISTRY:
        if not _is_command_available(command, integration):
            continue
        names.append(command.name)
        if include_aliases:
            names.extend(command.aliases)
    return names


def help_text(*, full: bool = False, integration: str | None = None) -> str:
    commands = tuple(
        command
        for command in COMMAND_REGISTRY
        if _is_command_available(command, integration) and (full or command.menu)
    )
    lines = ["Available commands:"]
    for command in commands:
        args = f" {command.args_hint}" if command.args_hint else ""
        alias_text = ""
        if command.aliases:
            alias_text = f" (alias: {', '.join('/' + alias for alias in command.aliases)})"
        lines.append(f"/{command.name}{args} - {command.description}{alias_text}")
    return "\n".join(lines)


def unknown_command_text(command: str, *, integration: str | None = None) -> str:
    token = _normalize_command_token(command).split(" ", 1)[0]
    return f"Unknown command: {token}\n\n{help_text(full=True, integration=integration)}"


def try_handle_command(
    context: "AgentContext",
    text: str,
    *,
    integration: str | None = None,
) -> str | None:
    parsed = parse_command(text, integration=integration)
    if not parsed:
        return None

    command, args = parsed
    if command == "/commands":
        return help_text(full=True, integration=integration)
    if command == "/status":
        return _handle_status(context)
    if command == "/sessions":
        return _handle_sessions(context)
    if command in {"/new", "/clear"}:
        return _handle_clear(context, new_chat=(command == "/new"))
    if command == "/send":
        return _handle_queue(context, "send")
    if command == "/queue":
        return _handle_queue(context, args)
    if command == "/steer":
        return _handle_steer(context, args)
    if command == "/pause":
        return _handle_pause(context)
    if command == "/resume":
        return _handle_resume(context)
    if command == "/nudge":
        return _handle_nudge(context)
    if command == "/stream":
        return _handle_toggle(context, args, "telegram_stream_enabled", "Response streaming")
    if command == "/tools":
        return _handle_toggle(context, args, "telegram_tools_enabled", "Tool progress")
    if command == "/project":
        return _handle_project(context, args)
    if command == "/model":
        return _handle_model(context, args)
    if command == "/agent":
        return _handle_agent(context, args)
    return None


def _normalize_command_token(command: str) -> str:
    normalized = command.strip().lower()
    if not normalized:
        return ""
    token, *rest = normalized.split(" ", 1)
    if "@" in token:
        token = token.split("@", 1)[0]
    return f"{token} {rest[0]}".strip() if rest else token


def _is_command_available(command: IntegrationCommandDef, integration: str | None) -> bool:
    if not command.integrations:
        return True
    if not integration:
        return False
    return integration.lower() in command.integrations


def _handle_queue(context: "AgentContext", args: str) -> str:
    queue = mq.get_queue(context)
    count = len(queue)
    action = args.strip().lower()

    if not action:
        noun = "message" if count == 1 else "messages"
        return (
            f"Queue has {count} {noun}.\n"
            "Use /send or /queue send to send everything as one batch."
        )

    if action in {"clear", "reset"}:
        mq.remove(context)
        mark_dirty_for_context(context.id, reason="integration_commands.queue_clear")
        return "Queue cleared."

    if action not in {"send", "all"}:
        return "Unknown queue action. Use /queue send to flush or /queue clear to clear."

    if count == 0:
        return "Queue is empty."

    sent_count = mq.send_all_aggregated(context)
    mark_dirty_for_context(context.id, reason="integration_commands.queue_send")
    noun = "message" if sent_count == 1 else "messages"
    return f"Sent {sent_count} queued {noun} as one batch."


def _handle_status(context: "AgentContext") -> str:
    project_name = context.get_data("project") or "none"
    agent_profile = getattr(context.agent0.config, "profile", "default")
    running = "running" if context.is_running() else "idle"
    if getattr(context, "paused", False):
        running = "paused"
    queue_count = len(mq.get_queue(context))
    return (
        f"Status: {running}\n"
        f"Project: {project_name}\n"
        f"Model: {model_config.get_effective_preset_name(context.agent0)}\n"
        f"Agent: {agent_profile}\n"
        f"Queued messages: {queue_count}"
    )


def _handle_sessions(context: "AgentContext") -> str:
    from agent import AgentContext

    contexts = sorted(
        AgentContext.all(),
        key=lambda item: str(item.output().get("last_message") or ""),
        reverse=True,
    )
    lines = ["Recent sessions:"]
    for item in contexts[:4]:
        marker = " (current)" if item.id == context.id else ""
        running = " - running" if item.is_running() else ""
        lines.append(f"- {item.name or item.id}{marker}{running}")
    if len(contexts) > 4:
        lines.append(f"And {len(contexts) - 4} more. Use Telegram buttons to page through them.")
    return "\n".join(lines)


def _handle_clear(context: "AgentContext", *, new_chat: bool) -> str:
    context.reset()
    mq.remove(context)
    save_tmp_chat(context)
    reason = "integration_commands.new" if new_chat else "integration_commands.clear"
    mark_dirty_for_context(context.id, reason=reason)
    return "Started a fresh chat." if new_chat else "Chat cleared."


def _handle_steer(context: "AgentContext", args: str) -> str:
    message = args.strip()
    if not message:
        return "Usage: /steer <message>"
    from agent import UserMessage

    context.communicate(UserMessage(message=message))
    if context.is_running():
        return "Steering message sent to the active run."
    return "Message sent."


def _handle_pause(context: "AgentContext") -> str:
    if not context.is_running():
        return "No active run is currently running."
    context.paused = True
    return "Agent paused."


def _handle_resume(context: "AgentContext") -> str:
    context.paused = False
    return "Agent resumed."


def _handle_nudge(context: "AgentContext") -> str:
    context.nudge()
    return "Agent nudged."


def _handle_toggle(context: "AgentContext", args: str, key: str, label: str) -> str:
    value = _parse_toggle(args)
    current = _get_toggle(context, key)
    if value is None:
        state = "on" if current else "off"
        return f"{label}: {state}. Use /{key.split('_')[1]} on or /{key.split('_')[1]} off."
    context.set_data(key, value)
    save_tmp_chat(context)
    mark_dirty_for_context(context.id, reason=f"integration_commands.{key}")
    return f"{label} {'enabled' if value else 'disabled'}."


def _handle_project(context: "AgentContext", args: str) -> str:
    items = projects.get_active_projects_list() or []
    current_name = context.get_data("project") or ""

    if not args:
        current_label = _describe_project(items, current_name)
        available = ", ".join(_format_project_entry(item) for item in items) or "none"
        return (
            f"Current project: {current_label}\n"
            f"Available projects: {available}\n"
            "Use /project <name> to switch, or /project none to clear it."
        )

    desired = _strip_quotes(args)
    if _normalize_lookup(desired) in _CLEAR_VALUES:
        if not current_name:
            return "No project is active."
        projects.deactivate_project(context.id)
        return "Cleared the active project."

    match, ambiguous = _match_named_item(items, desired, keys=("name", "title"))
    if ambiguous:
        names = ", ".join(_format_project_entry(item) for item in ambiguous)
        return f"Project name is ambiguous. Matches: {names}"
    if not match:
        available = ", ".join(_format_project_entry(item) for item in items) or "none"
        return f"Project '{desired}' was not found. Available projects: {available}"

    if match.get("name") == current_name:
        return f"Already using project {match.get('title') or match.get('name')}."

    projects.activate_project(context.id, match["name"])
    return f"Switched project to {match.get('title') or match['name']}."


def _handle_model(context: "AgentContext", args: str) -> str:
    allowed = model_config.is_chat_override_allowed(context.agent0)
    presets = [preset for preset in model_config.get_presets() if preset.get("name")]
    current_override = context.get_data("chat_model_override")

    if not args:
        current_label = model_config.get_effective_preset_name(context.agent0)
        available = ", ".join(preset["name"] for preset in presets) or "none"
        suffix = "Use /model <name> to switch, or /model inherit to use the scoped preset."
        if not allowed:
            suffix = "Per-chat config switching is disabled in Model Configuration."
        return (
            f"Current model: {current_label}\n"
            f"Available presets: {available}\n"
            f"{suffix}"
        )

    if not allowed:
        return "Config switching is disabled in Model Configuration."

    desired = _strip_quotes(args)
    if _normalize_lookup(desired) in _MODEL_INHERIT_VALUES:
        if not current_override:
            return "Already using the scoped model preset."
        context.set_data("chat_model_override", None)
        save_tmp_chat(context)
        mark_dirty_for_context(context.id, reason="integration_commands.config_clear")
        inherited = model_config.get_effective_preset_name(context.agent0)
        return f"Switched back to the scoped model preset: {inherited}."

    match, ambiguous = _match_named_item(presets, desired, keys=("name",))
    if ambiguous:
        names = ", ".join(item["name"] for item in ambiguous)
        return f"Config name is ambiguous. Matches: {names}"
    if not match:
        available = ", ".join(preset["name"] for preset in presets) or "none"
        return f"Config '{desired}' was not found. Available configs: {available}"

    preset_name = match["name"]
    if isinstance(current_override, dict) and current_override.get("preset_name") == preset_name:
        return f"Already using config {preset_name}."

    context.set_data("chat_model_override", {"preset_name": preset_name})
    save_tmp_chat(context)
    mark_dirty_for_context(context.id, reason="integration_commands.config_set")
    return f"Switched model preset to {preset_name}."


def _handle_agent(context: "AgentContext", args: str) -> str:
    from helpers import subagents
    from initialize import initialize_agent

    items = subagents.get_all_agents_list()
    current = getattr(context.agent0.config, "profile", "default")
    if not args:
        available = ", ".join(_format_agent_entry(item) for item in items) or "none"
        return (
            f"Current agent: {current}\n"
            f"Available agents: {available}\n"
            "Use /agent <profile> to switch after the current run finishes."
        )

    if context.is_running():
        return "Agent profile can be changed after the current run finishes."

    desired = _strip_quotes(args)
    match, ambiguous = _match_named_item(items, desired, keys=("key", "label"))
    if ambiguous:
        names = ", ".join(_format_agent_entry(item) for item in ambiguous)
        return f"Agent profile is ambiguous. Matches: {names}"
    if not match:
        available = ", ".join(_format_agent_entry(item) for item in items) or "none"
        return f"Agent profile '{desired}' was not found. Available agents: {available}"

    profile = str(match["key"])
    if profile == current:
        return f"Already using agent {match.get('label') or profile}."

    config = initialize_agent(override_settings={"agent_profile": profile})
    context.config = config
    context.agent0.config = config
    context.set_data("agent_profile_manually_set", True)
    save_tmp_chat(context)
    mark_dirty_for_context(context.id, reason="integration_commands.agent_set")
    return f"Switched agent to {match.get('label') or profile}."


def _format_project_entry(item: dict) -> str:
    title = str(item.get("title", "") or "").strip()
    name = str(item.get("name", "") or "").strip()
    if title and title.lower() != name.lower():
        return f"{title} ({name})"
    return name or title


def _format_agent_entry(item: dict) -> str:
    key = str(item.get("key", "") or "").strip()
    label = str(item.get("label", "") or "").strip()
    if label and label.lower() != key.lower():
        return f"{label} ({key})"
    return key or label


def _telegram_description(command: IntegrationCommandDef) -> str:
    description = command.description.strip()
    return description[:255] if len(description) > 255 else description


def _describe_project(items: list[dict], current_name: str) -> str:
    if not current_name:
        return "none"
    for item in items:
        if item.get("name") == current_name:
            return item.get("title") or current_name
    return current_name


def _strip_quotes(value: str) -> str:
    trimmed = value.strip()
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {'"', "'"}:
        return trimmed[1:-1].strip()
    return trimmed


def _normalize_lookup(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[\s_\-]+", " ", lowered)
    lowered = re.sub(r"[^a-z0-9 ]+", "", lowered)
    return lowered.strip()


def _get_toggle(context: "AgentContext", key: str) -> bool:
    value = context.get_data(key)
    return True if value is None else bool(value)


def _parse_toggle(args: str) -> bool | None:
    value = _normalize_lookup(args)
    if value in {"on", "enable", "enabled", "yes", "true", "1"}:
        return True
    if value in {"off", "disable", "disabled", "no", "false", "0"}:
        return False
    return None


def _match_named_item(
    items: list[dict],
    desired: str,
    *,
    keys: tuple[str, ...],
) -> tuple[dict | None, list[dict]]:
    normalized = _normalize_lookup(desired)
    exact_matches: list[dict] = []

    for item in items:
        values = [str(item.get(key, "") or "") for key in keys]
        normalized_values = [_normalize_lookup(value) for value in values if value]
        if normalized in normalized_values:
            exact_matches.append(item)

    if len(exact_matches) == 1:
        return exact_matches[0], []
    if len(exact_matches) > 1:
        return None, exact_matches

    partial_matches: list[dict] = []
    for item in items:
        values = [str(item.get(key, "") or "") for key in keys]
        normalized_values = [_normalize_lookup(value) for value in values if value]
        if any(normalized and normalized in value for value in normalized_values):
            partial_matches.append(item)

    if len(partial_matches) == 1:
        return partial_matches[0], []
    if len(partial_matches) > 1:
        return None, partial_matches

    return None, []
