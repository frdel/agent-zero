from __future__ import annotations

import json
from typing import Any

from agent import Agent
from helpers import persist_chat, plugins, tokens
from helpers.state_monitor_integration import mark_dirty_all


PLUGIN_NAME = "_chat_naming"
MODE_ONCE = "once"
MODE_ALWAYS = "always"
MANUAL_NAME_KEY = "chat_naming_manual"
RECENT_USER_MESSAGES = 4
GENERATED_NAME_LIMIT = 40
UTILITY_CONTEXT_INPUT_RATIO = 0.7


def get_config(agent: Agent) -> dict[str, Any]:
    config = plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {}
    mode = str(config.get("automatic_naming_mode", MODE_ALWAYS) or MODE_ALWAYS)
    if mode not in {MODE_ONCE, MODE_ALWAYS}:
        mode = MODE_ALWAYS
    return {
        "automatic_naming": bool(config.get("automatic_naming", True)),
        "automatic_naming_mode": mode,
    }


def get_user_messages(agent: Agent, *, limit: int | None = RECENT_USER_MESSAGES) -> list[str]:
    messages: list[str] = []
    for message in agent.history.all_messages():
        if message.ai:
            continue
        text = _user_message_text(message.content)
        if text:
            messages.append(text)
    return messages[-limit:] if limit else messages


def latest_user_sequence(agent: Agent) -> int:
    for message in reversed(agent.history.all_messages()):
        if not message.ai and _user_message_text(message.content):
            return int(message.sequence or 0)
    return 0


async def generate_name(
    agent: Agent,
    *,
    user_messages: list[str] | None = None,
    current_name: str | None = None,
) -> str:
    selected_messages = user_messages or get_user_messages(agent)
    if not selected_messages:
        raise ValueError("This chat has no user messages to name yet.")

    from plugins._model_config.helpers.model_config import get_utility_model_config

    utility_config = get_utility_model_config(agent)
    context_length = int(utility_config.get("ctx_length", 128000) or 128000)
    if context_length <= 0:
        context_length = 128000
    input_budget = max(int(context_length * UTILITY_CONTEXT_INPUT_RATIO), 1)

    system_prompt = agent.read_prompt("fw.chat_naming.system.md")
    resolved_name = (
        current_name if current_name is not None else agent.context.name
    ) or "(unnamed)"
    prompt_without_messages = agent.read_prompt(
        "fw.chat_naming.message.md",
        current_name=resolved_name,
        user_messages="",
    )
    fixed_tokens = _estimated_input_tokens(system_prompt, prompt_without_messages)
    message_budget = input_budget - fixed_tokens
    if message_budget <= 0:
        raise ValueError("The Utility Model context window is too small for chat naming.")

    message_text = _fit_user_messages(selected_messages, message_budget)
    user_prompt = agent.read_prompt(
        "fw.chat_naming.message.md",
        current_name=resolved_name,
        user_messages=message_text,
    )

    estimated_tokens = _estimated_input_tokens(system_prompt, user_prompt)
    while estimated_tokens > input_budget and message_text:
        excess = estimated_tokens - input_budget
        reduced_budget = max(
            tokens.approximate_tokens(message_text) - excess - 1,
            1,
        )
        trimmed = _trim_to_estimated_tokens(message_text, reduced_budget)
        if trimmed == message_text:
            break
        message_text = trimmed
        user_prompt = agent.read_prompt(
            "fw.chat_naming.message.md",
            current_name=resolved_name,
            user_messages=message_text,
        )
        estimated_tokens = _estimated_input_tokens(system_prompt, user_prompt)

    if estimated_tokens > input_budget:
        raise ValueError("Chat naming input exceeds the Utility Model context budget.")

    response = await agent.call_utility_model(
        system=system_prompt,
        message=user_prompt,
        background=True,
    )
    name = normalize_generated_name(response)
    if not name:
        raise ValueError("The Utility Model did not return a chat name.")
    return name


def save_context_name(agent: Agent, name: str) -> str:
    normalized = normalize_manual_name(name)
    agent.context.name = normalized
    if "parent_context_label" in agent.context.output_data:
        agent.context.output_data["parent_context_label"] = normalized
    persist_chat.save_tmp_chat(agent.context)
    mark_dirty_all(reason="plugins._chat_naming.save_context_name")
    return normalized


def normalize_generated_name(value: object) -> str:
    name = " ".join(str(value or "").split()).strip(" \"'`#")
    if len(name) > GENERATED_NAME_LIMIT:
        name = name[: GENERATED_NAME_LIMIT - 3].rstrip() + "..."
    return name


def normalize_manual_name(value: object) -> str:
    name = " ".join(str(value or "").split())
    if not name:
        raise ValueError("Name is required.")
    if len(name) > 200:
        raise ValueError("Name must be 200 characters or fewer.")
    return name


def _user_message_text(content: object) -> str:
    if not isinstance(content, dict):
        return ""
    for key in ("user_message", "user_intervention"):
        value = content.get(key)
        if isinstance(value, str):
            return value.strip()
        if value:
            return json.dumps(value, ensure_ascii=False)
    return ""


def _fit_user_messages(messages: list[str], token_budget: int) -> str:
    selected: list[str] = []
    for message in reversed(messages):
        candidate = [message, *selected]
        text = _format_user_messages(candidate)
        if tokens.approximate_tokens(text) <= token_budget:
            selected = candidate
            continue
        return _trim_to_estimated_tokens(text, token_budget)
    return _format_user_messages(selected)


def _estimated_input_tokens(system_prompt: str, user_prompt: str) -> int:
    return tokens.approximate_tokens(system_prompt) + tokens.approximate_tokens(
        user_prompt
    )


def _format_user_messages(messages: list[str]) -> str:
    return "\n\n".join(
        f"{index}. {text}" for index, text in enumerate(messages, start=1)
    )


def _trim_to_estimated_tokens(text: str, token_budget: int) -> str:
    if tokens.approximate_tokens(text) <= token_budget:
        return text

    exact_budget = max(int(token_budget / tokens.APPROX_BUFFER) - 1, 1)
    trimmed = tokens.trim_to_tokens(text, exact_budget, "end")
    while tokens.approximate_tokens(trimmed) > token_budget and exact_budget > 1:
        exact_budget = max(int(exact_budget * 0.8), 1)
        trimmed = tokens.trim_to_tokens(text, exact_budget, "end")
    return trimmed
