"""Source-audited explicit retry descriptors; no automatic effect reconciliation."""
from __future__ import annotations

from helpers.durable import codec

REQUEST_VERSION = 2
TRANSPORT_KEYS = ("a0_responses_function_tools", "responses_input_items", "responses_local_input_items", "previous_response_id", "responses_prompt_replacements", "responses_history_context")
CALL_KEYS = frozenset((*codec.MODEL_OPTIONS, *TRANSPORT_KEYS))
# Credentials are obtained from the current configured model, never persisted.
# Everything else must have a captured, understood request meaning.
MODEL_KEYS = frozenset((*codec.MODEL_OPTIONS, "api_key", "api_base"))
INPUT_ITEM_TYPES = frozenset(("message", "function_call", "function_call_output", "reasoning", "item_reference"))


def describe_model(agent, model, messages, kwargs, *, explicit_caching, background, stream_response, stream_reasoning):
    projected = []
    for message in messages:
        item = {"type": message.type, "content": message.content}
        if message.type == "ai":
            item["tool_calls"] = getattr(message, "tool_calls", [])
        if message.type == "tool":
            item["tool_call_id"] = getattr(message, "tool_call_id", None)
        projected.append(item)
    model_kwargs = getattr(model, "kwargs", {}) or {}
    request = {
        "request_version": REQUEST_VERSION, "model": str(getattr(model, "model_name", "")),
        "model_implementation": codec.identity(model), "messages": projected,
        "unsupported_message_metadata": any(bool(getattr(message, key, None)) for message in messages
                                            for key in ("additional_kwargs", "response_metadata", "name", "id")),
        "options": {key: kwargs[key] for key in codec.MODEL_OPTIONS if key in kwargs},
        "model_options": {key: model_kwargs[key] for key in codec.MODEL_OPTIONS if key in model_kwargs},
        "transport": {key: kwargs[key] for key in TRANSPORT_KEYS if key in kwargs},
        "explicit_caching": bool(explicit_caching), "background": bool(background),
        "stream_response": bool(stream_response), "stream_reasoning": bool(stream_reasoning),
        "unknown_call_options": sorted(set(kwargs) - CALL_KEYS),
        "unknown_model_options": sorted(set(model_kwargs) - MODEL_KEYS),
    }
    masked = codec.masked(agent, request)
    # Secret replacement is not a reversible request codec. An original prompt
    # containing resolved secrets cannot be certified as the same inference.
    masked["request_masked"] = masked != request
    eligible, reason = model_eligibility(agent, masked)
    masked["retry_eligible"] = eligible
    masked["retry_reason"] = reason
    return masked


def model_eligibility(agent, payload):
    if not isinstance(payload, dict) or payload.get("request_version") != REQUEST_VERSION:
        return False, "This request predates the complete inference retry descriptor."
    if payload.get("request_masked"):
        return False, "The original request contained private values that cannot be reconstructed safely."
    if payload.get("unknown_call_options") or payload.get("unknown_model_options"):
        return False, "This request uses options without an explicit retry adapter."
    if payload.get("unsupported_message_metadata"):
        return False, "Message metadata needs an explicit request retry codec."
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return False, "The complete prepared model input is unavailable."
    for item in messages:
        if not isinstance(item, dict) or item.get("type") not in ("human", "system", "ai", "tool") or not isinstance(item.get("content"), str):
            return False, "This input needs a multimodal or message retry adapter."
        if item["type"] == "tool" and not isinstance(item.get("tool_call_id"), str):
            return False, "A tool-result message is missing its original identity."
    options, transport = payload.get("options"), payload.get("transport")
    if not isinstance(options, dict) or set(options) - set(codec.MODEL_OPTIONS):
        return False, "The recorded generation options are unsupported."
    if not isinstance(transport, dict) or set(transport) - set(TRANSPORT_KEYS):
        return False, "Provider-hosted tools and raw tool configuration require reconciliation."
    tools = transport.get("a0_responses_function_tools") or []
    if not isinstance(tools, list) or any(not isinstance(tool, dict) or tool.get("type") != "function" for tool in tools):
        return False, "Only client-dispatched native function schemas support this retry."
    for key in ("responses_input_items", "responses_local_input_items"):
        items = transport.get(key)
        if items is not None:
            if not isinstance(items, list):
                return False, "The retained provider input is not a supported item list."
            for item in items:
                if not isinstance(item, dict):
                    return False, "Provider-hosted actions in retained input require an adapter."
                if item.get("type") not in INPUT_ITEM_TYPES:
                    if item.get("role") not in ("user", "assistant", "system", "developer"):
                        return False, "Provider-hosted actions in retained input require an adapter."
                    content = item.get("content")
                    if not isinstance(content, str) and (not isinstance(content, list) or any(
                            not isinstance(block, dict) or block.get("type") not in ("input_text", "output_text") for block in content)):
                        return False, "Retained multimodal provider input requires an adapter."
    for key in ("explicit_caching", "background", "stream_response", "stream_reasoning"):
        if type(payload.get(key)) is not bool:
            return False, "The original invocation controls are incomplete."
    model = agent.get_chat_model()
    if str(getattr(model, "model_name", "")) != payload.get("model") or codec.identity(model) != payload.get("model_implementation"):
        return False, "The configured model implementation changed."
    current = getattr(model, "kwargs", {}) or {}
    if not isinstance(current, dict) or set(current) - MODEL_KEYS:
        return False, "Current provider configuration needs a retry adapter."
    if codec.masked(agent, {key: current[key] for key in codec.MODEL_OPTIONS if key in current}) != payload.get("model_options"):
        return False, "The configured generation options changed."
    return True, "A new inference may repeat provider charges; the original outcome remains unknown."


def retry_eligibility(agent, call, prepared=None, tool=None):
    """Read-only eligibility used by review and rechecked at consumption."""
    if not call or call.get("status") != "intent" or call.get("payloads_pruned") or call.get("logical_call_id"):
        return False, "Only a retained unresolved original invocation can receive a new attempt."
    if call.get("kind") == "model":
        eligible, reason = model_eligibility(agent, call.get("payload"))
        return (eligible and call["payload"].get("retry_eligible") is True), reason
    if call.get("kind") != "tool":
        return False, "This invocation kind has no explicit retry adapter."
    if not prepared or prepared.get("status") != "completed" or prepared.get("payloads_pruned"):
        return False, "The committed effective arguments are unavailable."
    from tools.response import ResponseTool
    from tools.durable_plan import DurablePlan
    from helpers.durable.replay import AUDITED_TOOLS
    allowed = (ResponseTool, DurablePlan)
    identity = call["payload"].get("tool")
    declared = next((cls for cls in allowed if codec.identity(cls) == identity), None)
    if declared is None or (tool is not None and type(tool) is not declared):
        return False, "This target has no source-audited explicit retry adapter."
    if (declared.__name__, identity["source"]) not in AUDITED_TOOLS:
        return False, "This tool implementation has not passed its source audit."
    from helpers.tool_policy import ensure_tool_allowed
    try:
        ensure_tool_allowed(agent, call["payload"].get("name", ""))
    except Exception:
        return False, "The current tool access policy does not authorize this target."
    from helpers.durable.runtime import _audited_hooks
    if not all(_audited_hooks(agent, point) for point in ("tool_execute_before", "tool_execute_after")):
        return False, "The tool lifecycle contains hooks without a retry audit."
    return True, "Only the recorded effective arguments and audited lifecycle may be retried."


def restore_messages(payload):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    classes = {"ai": AIMessage, "human": HumanMessage, "system": SystemMessage, "tool": ToolMessage}
    messages = []
    for item in payload["messages"]:
        kwargs = {"content": item["content"]}
        if item["type"] == "ai":
            kwargs["tool_calls"] = item.get("tool_calls", [])
        if item["type"] == "tool":
            kwargs["tool_call_id"] = item["tool_call_id"]
        messages.append(classes[item["type"]](**kwargs))
    return messages
