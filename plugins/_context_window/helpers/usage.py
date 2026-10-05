import hashlib
import math
from typing import Any

from helpers import files, history, skills, tokens
from helpers.llm_result import result_from_metadata


PARTS_KEY = "context_window_usage"
CACHE_KEY = "_context_window_usage_cache"
PROVIDER_USAGE_KEY = "context_window_provider_usage"
USAGE_KEYS = (
    "messages",
    "system_tools",
    "skills",
    "mcp_tools",
    "system_prompt",
    "extras",
)
MEASURED_KEYS = tuple(key for key in USAGE_KEYS if key != "system_prompt")


def reset(agent: Any) -> None:
    params = _temporary_params(agent)
    if params is not None:
        params[PARTS_KEY] = {}


def discard(agent: Any) -> None:
    params = _temporary_params(agent)
    if params is not None:
        params.pop(PARTS_KEY, None)


def record_prompt(agent: Any, key: str, prompt: Any) -> None:
    parts = _parts(agent)
    if parts is None or key not in MEASURED_KEYS:
        return
    text = files.remove_code_fences(str(prompt or ""), language="json")
    parts[key] = _cached_tokens(agent, f"prompt:{key}", text)


def capture_context(agent: Any, loop_data: Any) -> None:
    parts = _parts(agent)
    if parts is None or loop_data is None:
        return

    output = list(getattr(loop_data, "history_output", None) or [])
    parts["_history_output"] = output
    skill_output = [message for message in output if skills.skill_instruction_name(message)]
    skill_tokens = _output_tokens(agent, "history_skills", skill_output)
    parts["messages"] = max(_history_tokens(agent, output) - skill_tokens, 0)
    parts["skills"] = parts.get("skills", 0) + skill_tokens

    protocol_values = {
        **getattr(loop_data, "protocol_persistent", {}),
        **getattr(loop_data, "protocol_temporary", {}),
    }
    extras_values = {
        **getattr(loop_data, "extras_persistent", {}),
        **getattr(loop_data, "extras_temporary", {}),
    }
    protocol = agent._build_context_message(
        "agent.context.protocol.md",
        "protocol",
        protocol_values,
        include_empty=False,
    )
    extras = agent._build_context_message(
        "agent.context.extras.md",
        "extras",
        extras_values,
        include_empty=True,
    )
    parts["extras"] = _output_tokens(agent, "extras", protocol + extras)


def finalize(agent: Any) -> None:
    params = _temporary_params(agent)
    parts = params.pop(PARTS_KEY, None) if params is not None else None
    window = agent.get_data(agent.DATA_NAME_CTX_WINDOW) if agent else None
    if not isinstance(parts, dict) or not isinstance(window, dict):
        return

    history_output = parts.pop("_history_output", None)
    total = _non_negative_int(window.get("tokens"))
    usage = {key: _non_negative_int(parts.get(key)) for key in MEASURED_KEYS}
    measured_total = sum(usage.values())
    if total and measured_total >= total and isinstance(history_output, list):
        message_output = [
            message
            for message in history_output
            if not skills.skill_instruction_name(message)
        ]
        usage["messages"] = _output_tokens(
            agent, "history_messages", message_output
        )
        measured_total = sum(usage.values())
    if measured_total > total and measured_total:
        usage = _scale_to_total(usage, total, measured_total)
        measured_total = total
    usage["system_prompt"] = total - measured_total
    usage = {key: usage.get(key, 0) for key in USAGE_KEYS}

    updated = dict(window)
    updated["usage"] = usage
    agent.set_data(agent.DATA_NAME_CTX_WINDOW, updated)


def usage_snapshot(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {key: _non_negative_int(value.get(key)) for key in USAGE_KEYS}


def capture_provider_usage(agent: Any, result: Any) -> None:
    if agent is None or result is None or not hasattr(result, "usage"):
        return

    snapshot = provider_usage_snapshot(getattr(result, "usage", None))
    agent.set_data(
        PROVIDER_USAGE_KEY,
        snapshot if snapshot else {"available": False},
    )


def latest_provider_usage(agent: Any) -> dict[str, int | float]:
    data = getattr(agent, "data", None)
    if isinstance(data, dict) and PROVIDER_USAGE_KEY in data:
        stored = data.get(PROVIDER_USAGE_KEY)
        if isinstance(stored, dict) and stored.get("available") is False:
            return {}
        snapshot = provider_usage_snapshot(stored)
        speed = (
            _optional_non_negative_float(stored.get("output_tokens_per_second"))
            if isinstance(stored, dict)
            else None
        )
        if snapshot and speed:
            snapshot["output_tokens_per_second"] = speed
        return snapshot

    all_messages = getattr(getattr(agent, "history", None), "all_messages", None)
    if not callable(all_messages):
        return {}
    for message in reversed(all_messages()):
        if not getattr(message, "ai", False):
            continue
        result = result_from_metadata(getattr(message, "metadata", None))
        if result:
            return provider_usage_snapshot(result.usage)
    return {}


def provider_usage_snapshot(value: Any) -> dict[str, int | float]:
    if not isinstance(value, dict):
        return {}

    input_details = {
        **_mapping(value.get("prompt_tokens_details")),
        **_mapping(value.get("input_tokens_details")),
    }
    result: dict[str, int | float] = {}
    fields = {
        "input_tokens": (value.get("input_tokens"), value.get("prompt_tokens")),
        "cached_tokens": (
            input_details.get("cached_tokens"),
            input_details.get("cache_read_tokens"),
            value.get("cache_read_input_tokens"),
            value.get("cached_tokens"),
        ),
        "output_tokens": (
            value.get("output_tokens"),
            value.get("completion_tokens"),
        ),
    }
    for key, values in fields.items():
        number = _optional_non_negative_int(*values)
        if number is not None:
            result[key] = number

    cost = _optional_non_negative_float(
        value.get("cost"), value.get("response_cost")
    )
    if cost is not None:
        result["cost"] = cost
    return result


def _parts(agent: Any) -> dict[str, Any] | None:
    params = _temporary_params(agent)
    value = params.get(PARTS_KEY) if params is not None else None
    return value if isinstance(value, dict) else None


def _temporary_params(agent: Any) -> dict[str, Any] | None:
    loop_data = getattr(agent, "loop_data", None)
    params = getattr(loop_data, "params_temporary", None)
    return params if isinstance(params, dict) else None


def _history_tokens(agent: Any, output: list[history.OutputMessage]) -> int:
    get_tokens = getattr(getattr(agent, "history", None), "get_tokens", None)
    if callable(get_tokens):
        return _non_negative_int(get_tokens())
    return _count_output_tokens(output)


def _output_tokens(
    agent: Any, cache_key: str, output: list[history.OutputMessage]
) -> int:
    text = history.output_text(output, ai_label="assistant", human_label="user")
    return _cached_tokens(agent, cache_key, text)


def _count_output_tokens(output: list[history.OutputMessage]) -> int:
    text = history.output_text(output, ai_label="assistant", human_label="user")
    return tokens.approximate_prompt_tokens(text)


def _cached_tokens(agent: Any, key: str, text: str) -> int:
    cache = _cache(agent)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cached = cache.get(key) if cache is not None else None
    if isinstance(cached, tuple) and len(cached) == 2 and cached[0] == digest:
        return _non_negative_int(cached[1])

    count = tokens.approximate_prompt_tokens(text)
    if cache is not None:
        cache[key] = (digest, count)
    return count


def _cache(agent: Any) -> dict[str, tuple[str, int]] | None:
    data = getattr(agent, "data", None)
    if not isinstance(data, dict):
        return None
    cache = data.get(CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        data[CACHE_KEY] = cache
    return cache


def _non_negative_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_non_negative_int(*values: Any) -> int | None:
    for value in values:
        if value is None:
            continue
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            continue
    return None


def _optional_non_negative_float(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return max(number, 0)
    return None


def _scale_to_total(values: dict[str, int], total: int, current: int) -> dict[str, int]:
    scaled = {key: value * total // current for key, value in values.items()}
    remainder = total - sum(scaled.values())
    order = sorted(values, key=lambda key: values[key] * total % current, reverse=True)
    for key in order[:remainder]:
        scaled[key] += 1
    return scaled
