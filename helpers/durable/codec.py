"""Versioned, masked recovery projections; never pickle runtime objects."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from helpers.llm_result import LLMResult

VERSION = 1
LOOP_FIELDS = ("iteration", "last_response", "protocol_persistent", "extras_persistent", "params_persistent")
AGENT_FIELDS = ("responses_state", "responses_tool_name_map", "last_tool_call")
CONTEXT_FIELDS = ("project", "chat_model_override", "scheduler_task_uuid")
CHILD_OUTPUT_FIELDS = ("parent_context_id", "parent_agent_number", "parent_context_kind",
                       "parent_context_label", "subordinate_slot", "parallel_job_id", "parallel_tool_name")
PUBLIC_AGENT_FIELDS = (*AGENT_FIELDS, "iteration_no", "responses_delete_on_chat_delete")
LOOP_PARAM_FIELDS = ("_unusable_response_failures",)
MODEL_OPTIONS = ("temperature", "max_tokens", "max_output_tokens", "a0_api_mode", "responses_state", "a0_retry_attempts")
CAPABILITY_FIELDS = ("mode", "state", "history_prefix_hash", "builtin_tool_downgrades")
HOOK_POINTS = (
    "monologue_start", "monologue_end", "message_loop_start", "message_loop_end",
    "before_main_llm_call", "chat_model_call_before", "chat_model_call_after",
    "reasoning_stream_end", "response_stream_end", "message_loop_result",
    "tool_execute_before", "tool_execute_after", "hist_add_before", "hist_add_tool_result",
)


def identity(obj):
    """Identity includes source content, so code drift does not inherit old grants."""
    cls = obj if inspect.isclass(obj) else type(obj)
    try:
        path = inspect.getsourcefile(cls)
    except TypeError:
        path = None
    if not path:
        raise ValueError("Recovery requires inspectable implementation source")
    return {"class": cls.__module__ + "." + cls.__qualname__,
            "source": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def masked(agent, value):
    from helpers.secrets import get_secrets_manager
    manager = get_secrets_manager(agent.context)

    def visit(item):
        if isinstance(item, str):
            return manager.mask_values(item)
        if item is None or type(item) in (int, float, bool):
            return item
        if type(item) is list:
            return [visit(child) for child in item]
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            return {key: visit(child) for key, child in item.items()}
        raise ValueError("Unsupported recovery state; a checkpoint adapter is required")

    result = visit(value)
    json.dumps(result, allow_nan=False)  # Fail closed, including NaN/Infinity.
    return result


def result_payload(agent, result):
    # .raw may contain arbitrary SDK/provider data. All retained fields are explicit.
    data = result.to_dict()
    data.pop("raw", None)
    data["capability"] = {key: data["capability"][key] for key in CAPABILITY_FIELDS if key in data["capability"]}
    opaque = []
    for index, item in enumerate(data.get("output_items", [])):
        if item.get("type") == "reasoning" and "encrypted_content" in item:
            opaque.append((index, item["encrypted_content"]))
    data = masked(agent, data)
    for index, content in opaque:
        if not isinstance(content, str):
            raise ValueError("Invalid opaque provider continuity item")
        data["output_items"][index]["encrypted_content"] = content
    return data


def environment(agent):
    from helpers import extension
    model = agent.get_chat_model()
    kwargs = getattr(model, "kwargs", {}) or {}
    manifest = {
        "agent": identity(agent),
        "profile": agent.config.profile,
        "model": str(getattr(model, "model_name", "")),
        "model_implementation": identity(model),
        "provider": str(getattr(model, "provider", "")),
        "endpoint_digest": hashlib.sha256(masked(agent, str(kwargs.get("api_base", ""))).encode()).hexdigest(),
        "options": {key: kwargs[key] for key in MODEL_OPTIONS if key in kwargs},
        "hooks": {point: [identity(cls) for cls in extension._get_extension_classes(point, agent=agent)]
                  for point in HOOK_POINTS},
    }
    root = Path(__file__).resolve().parents[2]
    manifest["runtime_sources"] = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ("helpers/durable/codec.py", "helpers/durable/runtime.py", "helpers/durable/store.py",
                     "helpers/durable/replay.py", "helpers/tool_execution.py", "helpers/history.py",
                     "helpers/responses_history.py", "helpers/llm_result.py", "helpers/durable/workflows.py",
                     "helpers/durable/scheduler.py", "helpers/task_scheduler.py", "helpers/parallel_tools.py",
                     "tools/call_subordinate.py", "tools/parallel.py", "helpers/tool.py",
                     "helpers/extension.py", "helpers/tool_policy.py", "helpers/defer.py", "models.py",
                     "helpers/durable/documents.py", "helpers/durable/review.py", "helpers/durable/retry.py")
    }
    # Include function-extension discovery at the boundaries used by the runner.
    for name in ("hist_add_ai_response", "hist_add_tool_result", "monologue", "prepare_prompt", "call_chat_model_turn"):
        for when in ("start", "end"):
            point = f"_functions/agent/Agent/{name}/{when}"
            manifest["hooks"][point] = [identity(cls) for cls in extension._get_extension_classes(point, agent=agent)]
    return masked(agent, manifest)


def checkpoint(agent, *, result=None, terminal=None):
    from helpers import persist_chat
    from helpers.log import LogItem
    loop = getattr(agent, "loop_data", None)
    temporary = {}
    if loop:
        for key, value in loop.params_temporary.items():
            if isinstance(value, LogItem):
                temporary[key] = value.id
    snapshot = persist_chat._serialize_context(agent.context)
    unsupported = bool(set(snapshot["data"]) - set(CONTEXT_FIELDS))
    snapshot["data"] = {key: snapshot["data"][key] for key in CONTEXT_FIELDS if key in snapshot["data"]}
    override = snapshot["data"].get("chat_model_override")
    if override is not None and (not isinstance(override, dict) or set(override) != {"preset_name"}
                                 or not isinstance(override["preset_name"], str)):
        unsupported = True
        snapshot["data"].pop("chat_model_override", None)
    snapshot["output_data"] = {key: snapshot["output_data"][key] for key in CHILD_OUTPUT_FIELDS
                               if key in snapshot["output_data"]}
    for stored_agent in snapshot["agents"]:
        unsupported |= bool(set(stored_agent["data"]) - set(PUBLIC_AGENT_FIELDS) - {"ctx_window"})
        stored_agent["data"] = {key: stored_agent["data"][key] for key in PUBLIC_AGENT_FIELDS if key in stored_agent["data"]}
        history = json.loads(stored_agent["history"])
        def prune_capabilities(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "capability" and isinstance(child, dict):
                        value[key] = {name: child[name] for name in CAPABILITY_FIELDS if name in child}
                    else:
                        prune_capabilities(child)
            elif isinstance(value, list):
                for child in value:
                    prune_capabilities(child)
        prune_capabilities(history)
        stored_agent["history"] = json.dumps(history, ensure_ascii=False)
    loop_state = {key: getattr(loop, key) for key in LOOP_FIELDS} if loop else {}
    if loop:
        unsupported |= bool(set(loop.params_persistent) - set(LOOP_PARAM_FIELDS))
        loop_state["params_persistent"] = {key: loop.params_persistent[key] for key in LOOP_PARAM_FIELDS if key in loop.params_persistent}
    value = {
        "version": VERSION,
        "context": snapshot,
        "requires_state_adapter": unsupported,
        "paused": agent.context.paused,
        "agent_state": {key: agent.data[key] for key in AGENT_FIELDS if key in agent.data},
        "loop": loop_state,
        "temporary_log_ids": temporary,
        "environment": environment(agent),
        "intervention": message_payload(agent.intervention) if agent.intervention else None,
        "last_user_message_id": getattr(agent.last_user_message, "id", None),
        "terminal": terminal,
        "origin": getattr(agent.context, "_durable_origin", None),
        "workflow_state": getattr(agent.context, "_durable_workflow_state", {}),
    }
    value = masked(agent, value)
    if result is not None:
        value["result"] = result_payload(agent, result)
    return value


def message_payload(message):
    return {"message": message.message, "system_message": list(message.system_message),
            "attachments": list(message.attachments), "id": message.id}


def function_resume_supported(data, phase):
    """Function wrappers sit outside the runner's committed hook boundaries."""
    hooks = data.get("environment", {}).get("hooks", {})
    origin = data.get("origin") or {}
    tool_child = origin.get("kind") == "child" and origin.get("mode") == "tool"
    if not tool_child and any(hooks.get(f"_functions/agent/Agent/monologue/{when}") for when in ("start", "end")):
        return False
    if phase == "model_result" and hooks.get("_functions/agent/Agent/call_chat_model_turn/end"):
        return False
    return True


def restore(context, data):
    from agent import LoopData, UserMessage
    if data.get("version") != VERSION:
        raise ValueError("Unsupported recovery checkpoint version")
    if data.get("requires_state_adapter"):
        raise ValueError("Recovery requires a plugin state adapter")
    agent = context.agent0
    if environment(agent) != data["environment"]:
        raise ValueError("Recovery configuration or implementation changed")
    agent.data.update(data["agent_state"])
    agent.loop_data = LoopData(**data["loop"])
    agent.last_user_message = next((message for message in agent.history.all_messages()
                                    if message.id == data.get("last_user_message_id")), None)
    agent.loop_data.user_message = agent.last_user_message
    by_id = {(item.type, item.id): item for item in context.log.logs}
    for key, identifier in data["temporary_log_ids"].items():
        kind = "response" if key == "log_item_response" else "agent"
        if (kind, identifier) not in by_id:
            raise ValueError("Recovery log projection is incomplete")
        agent.loop_data.params_temporary[key] = by_id[(kind, identifier)]
    context.paused = data["paused"]
    context._durable_origin = data.get("origin")
    context._durable_workflow_state = data.get("workflow_state", {})
    if context._durable_origin and context._durable_origin.get("kind") == "child":
        from helpers.durable.workflows import restore_context
        restore_context(context, context._durable_origin)
    agent.intervention = UserMessage(**data["intervention"]) if data.get("intervention") else None
    return agent
