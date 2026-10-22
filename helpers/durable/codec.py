"""Versioned, masked recovery projections; never pickle runtime objects."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from helpers.llm_result import LLMResult

VERSION = 1
LOOP_FIELDS = ("iteration", "last_response", "protocol_persistent", "extras_persistent", "params_persistent")
AGENT_FIELDS = ("responses_state", "responses_tool_name_map", "last_tool_call", "responses_computer_session_id")
CONTEXT_FIELDS = ("project", "chat_model_override", "scheduler_task_uuid", "responses_delete_on_chat_delete")
CHILD_OUTPUT_FIELDS = ("parent_context_id", "parent_agent_number", "parent_context_kind",
                       "parent_context_label", "subordinate_slot", "parallel_job_id", "parallel_tool_name")
PUBLIC_AGENT_FIELDS = (*AGENT_FIELDS, "iteration_no", "responses_delete_on_chat_delete")
LOOP_PARAM_FIELDS = ("_unusable_response_failures",)
MODEL_OPTIONS = ("temperature", "max_tokens", "max_output_tokens", "a0_api_mode", "responses_state", "a0_retry_attempts")
CAPABILITY_FIELDS = ("mode", "state", "history_prefix_hash", "builtin_tool_downgrades")
HOOK_POINTS = (
    "agent_init",
    "monologue_start", "monologue_end", "message_loop_start", "message_loop_end",
    "before_main_llm_call", "chat_model_call_before", "chat_model_call_after",
    "reasoning_stream_end", "response_stream_end", "message_loop_result",
    "tool_execute_before", "tool_execute_after", "hist_add_before", "hist_add_tool_result", "user_message_ui",
    "message_loop_prompts_before", "message_loop_prompts_after", "system_prompt",
    "util_model_call_before", "util_model_call_after", "tool_output_update",
)


def identity(obj):
    """Identity includes source content, so code drift does not inherit old grants."""
    cls = obj if inspect.isclass(obj) else type(obj)
    try:
        path = inspect.getsourcefile(cls)
    except TypeError:
        path = None
    if not path:
        # Plugin tools are loaded with exec under their file stem without a
        # sys.modules entry. Their defining function retains its real source.
        method = cls.__dict__.get("execute")
        code = getattr(method, "__code__", None)
        if code and code.co_qualname == cls.__qualname__ + ".execute":
            candidate = Path(code.co_filename)
            if candidate.is_file() and candidate.suffix == ".py":
                path = str(candidate)
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
    from helpers.durable.maintenance import provider_descriptor
    model = agent.get_chat_model()
    kwargs = getattr(model, "kwargs", {}) or {}
    manifest = {
        "agent": identity(agent),
        "profile": agent.config.profile,
        "model": str(getattr(model, "model_name", "")),
        "model_implementation": identity(model),
        "provider": str(getattr(model, "provider", "")),
        "provider_cleanup": getattr(agent.context, "_durable_provider_descriptor", None) or provider_descriptor(agent, model=model),
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
                     "helpers/durable/documents.py", "helpers/durable/review.py", "helpers/durable/retry.py",
                     "helpers/durable/postgres.py", "helpers/durable/cluster.py",
                     "helpers/durable/resources.py", "helpers/durable/resource_store.py",
                     "helpers/durable/adapters.py",
                     "helpers/durable/inputs.py", "helpers/durable/state_adapters.py", "helpers/kvp.py",
                     "helpers/durable/hosted.py",
                     "helpers/durable/interactive.py", "helpers/durable/mcp_broker.py",
                     "helpers/durable/background.py", "helpers/durable/history.py", "helpers/durable/memorization.py",
                     "helpers/faiss_monkey_patch.py", "plugins/_infection_check/helpers/checker.py",
                     "helpers/durable/computer.py", "helpers/durable/memory.py", "helpers/durable/maintenance.py",
                     "helpers/durable/workspaces.py", "helpers/durable/execution.py", "helpers/durable/sessions.py",
                     "helpers/projects.py", "helpers/mcp_handler.py",
                     "plugins/_browser/tools/browser.py", "plugins/_browser/helpers/runtime.py",
                     "plugins/_browser/helpers/profile_checkpoint.py", "plugins/_browser/helpers/session_broker.py",
                     "plugins/_browser/helpers/durable_connector.py",
                     "plugins/_a0_connector/helpers/ws_runtime.py", "plugins/_a0_connector/tools/computer_use_remote.py",
                     "plugins/_memory/helpers/memory.py", "plugins/_memory/helpers/durable_memory.py",
                     "plugins/_code_execution/helpers/durable_pty.py", "plugins/_code_execution/tools/input.py",
                     "plugins/_code_execution/tools/code_execution_tool.py")
    }
    # Include function-extension discovery at the boundaries used by the runner.
    for name in ("hist_add_ai_response", "hist_add_tool_result", "monologue", "prepare_prompt", "call_chat_model_turn"):
        for when in ("start", "end"):
            point = f"_functions/agent/Agent/{name}/{when}"
            manifest["hooks"][point] = [identity(cls) for cls in extension._get_extension_classes(point, agent=agent)]
    return masked(agent, manifest)


def compatible_environment(agent, expected):
    """Cleanup account custody is checked at deletion, separately from execution."""
    current = environment(agent)
    current.pop("provider_cleanup", None)
    return current == {key: value for key, value in expected.items() if key != "provider_cleanup"}


def construction_sources():
    root = Path(__file__).resolve().parents[2]
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in (
        "agent.py", "initialize.py", "helpers/persist_chat.py", "helpers/durable/codec.py",
        "helpers/durable/cluster.py", "helpers/durable/scheduler.py")}


def context_seed(context_id, name, *, profile="", data=None):
    """A pure descriptor; no initializer, model, agent or extension is invoked."""
    return {"version": VERSION, "construction_sources": construction_sources(),
            "context": {"id": context_id, "name": name, "agent_profile": profile,
                "type": "user", "data": data or {}, "output_data": {},
                "agents": [{"number": 0, "agent_profile": profile, "data": {}, "history": ""}],
                "log": {"guid": "", "logs": []}},
            "resources": {"version": 1}, "requires_state_adapter": False}


def checkpoint(agent, *, result=None, terminal=None):
    from helpers import persist_chat
    from helpers.durable import state_adapters
    from helpers.durable.resources import checkpoint_state
    turn = getattr(agent.context, "_durable_turn", None)
    if turn and getattr(turn.owner, "distributed", False):
        from helpers.durable.resources import snapshot_context
        snapshot_context(turn.owner, agent.context, turn.run_id)
    from helpers.log import LogItem
    loop = getattr(agent, "loop_data", None)
    temporary = {}
    if loop:
        for key, value in loop.params_temporary.items():
            if isinstance(value, LogItem):
                temporary[key] = value.id
    snapshot = persist_chat._serialize_context(agent.context)
    plugin_state = state_adapters.capture(agent, kvp=getattr(agent.context, "_durable_kvp", {}))
    unsupported = bool(set(snapshot["data"]) - set(CONTEXT_FIELDS) - state_adapters.handled_keys("context"))
    snapshot["data"] = {key: snapshot["data"][key] for key in CONTEXT_FIELDS if key in snapshot["data"]}
    if "responses_delete_on_chat_delete" in snapshot["data"] and type(snapshot["data"]["responses_delete_on_chat_delete"]) is not bool:
        raise ValueError("Invalid provider cleanup opt-out")
    override = snapshot["data"].get("chat_model_override")
    if override is not None and (not isinstance(override, dict) or set(override) != {"preset_name"}
                                 or not isinstance(override["preset_name"], str)):
        unsupported = True
        snapshot["data"].pop("chat_model_override", None)
    snapshot["output_data"] = {key: snapshot["output_data"][key] for key in CHILD_OUTPUT_FIELDS
                               if key in snapshot["output_data"]}
    for stored_agent in snapshot["agents"]:
        unsupported |= bool(set(stored_agent["data"]) - set(PUBLIC_AGENT_FIELDS) - state_adapters.handled_keys("agent"))
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
        unsupported |= bool(set(loop.params_persistent) - set(LOOP_PARAM_FIELDS) - state_adapters.handled_keys("loop_params_persistent"))
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
        "ui_input_pending": bool(getattr(agent.context, "_durable_ui_input_pending", False)),
        "resources": checkpoint_state(agent.context),
        "plugin_state": plugin_state,
        "provider_cleanup_targets": getattr(agent.context, "_durable_provider_cleanup_targets", {}),
    }
    value = masked(agent, value)
    if result is not None:
        value["result"] = result_payload(agent, result)
    from helpers.durable.resources import canonical_value
    value = canonical_value(agent.context, value)
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
    from helpers.durable import state_adapters
    plugin_state = data.get("plugin_state", {"version": 1, "entries": []})
    state_adapters.validate(plugin_state)
    agent = context.agent0
    if not compatible_environment(agent, data["environment"]):
        raise ValueError("Recovery configuration or implementation changed")
    from helpers.durable.resources import local_value
    data = local_value(context, data)
    agent.data.update(data["agent_state"])
    agent.loop_data = LoopData(**data["loop"])
    if plugin_state["entries"]:
        values = getattr(context, "_durable_kvp", None)
        if values is None:
            values = context._durable_kvp = {}
        state_adapters.restore(agent, plugin_state, guard=lambda: state_guard(context), kvp=values)
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
    context._durable_provider_descriptor = data.get("environment", {}).get("provider_cleanup")
    context._durable_provider_cleanup_targets = dict(data.get("provider_cleanup_targets", {}))
    context._durable_workflow_state = data.get("workflow_state", {})
    from helpers.durable.resources import restore_state
    restore_state(context, data.get("resources"))
    if context._durable_origin and context._durable_origin.get("kind") == "child":
        from helpers.durable.workflows import restore_context
        restore_context(context, context._durable_origin)
    agent.intervention = UserMessage(**data["intervention"]) if data.get("intervention") else None
    return agent


def state_guard(context):
    """Reconstruction and context-local writes require the current ledger owner."""
    turn = getattr(context, "_durable_turn", None)
    owner = getattr(turn, "owner", None) or getattr(context, "_durable_recovery_owner", None)
    run_id = getattr(turn, "run_id", None) or getattr(context, "_durable_recovery_run_id", None)
    if owner is None or run_id is None:
        raise ValueError("State reconstruction requires its recovery owner")
    return owner.sync("assert_owner" if getattr(owner, "distributed", False) else "_writable", run_id)
