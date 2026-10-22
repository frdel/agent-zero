"""Explicit, source-pinned JSON state codecs; declarations never authorize effects.

Registration is trusted application code. Stored manifests select only already
registered declarations, never imports, constructors, setters or pickle codecs.
"""
from __future__ import annotations

from dataclasses import dataclass
import asyncio
import hashlib
import inspect
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 256 * 1024
MAX_FIELDS = 512
MAX_DEPTH = 24
_NAME = re.compile(r"[a-zA-Z0-9_.:-]{1,160}\Z")
SCOPES = frozenset({"context", "agent", "kvp", *(f"loop_{a}_{b}" for a in
                     ("params", "protocol", "extras") for b in ("persistent", "temporary"))})


class StateHeld(ValueError):
    """The declared state cannot be restored without a fresh adapter review."""


@dataclass(frozen=True)
class Field:
    scope: str
    key: str
    type: str = "json"


@dataclass(frozen=True)
class Hook:
    point: str
    class_name: str
    source: str
    boundary: str = "continuation"


@dataclass(frozen=True)
class StateAdapter:
    name: str
    version: int
    fields: tuple[Field, ...]
    sources: tuple[str, ...]
    hooks: tuple[Hook, ...] = ()


_REGISTRY: dict[str, StateAdapter] = {}


def _plain(value, depth=0):
    if depth > MAX_DEPTH:
        raise StateHeld("state_depth_exceeded")
    if value is None or type(value) in (str, int, float, bool):
        return value
    if type(value) is list:
        return [_plain(item, depth + 1) for item in value]
    if type(value) is dict and all(type(k) is str for k in value):
        return {key: _plain(item, depth + 1) for key, item in value.items()}
    raise StateHeld("state_requires_explicit_codec")


def _json(value):
    try:
        encoded = json.dumps(_plain(value), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode()
    except (ValueError, TypeError, OverflowError):
        raise StateHeld("invalid_state_json") from None
    if len(encoded) > MAX_BYTES:
        raise StateHeld("state_size_exceeded")
    return encoded


def _source(name):
    if not isinstance(name, str):
        raise StateHeld("state_source_unavailable")
    path = ROOT / name
    if (not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts
            or not path.is_file() or path.is_symlink() or ROOT not in path.resolve().parents):
        raise StateHeld("state_source_unavailable")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register(adapter):
    """Register an immutable declaration in trusted startup code, without importing producers."""
    if (type(adapter) is not StateAdapter or not _NAME.fullmatch(adapter.name)
            or type(adapter.version) is not int or adapter.version < 1
            or type(adapter.fields) is not tuple or type(adapter.sources) is not tuple
            or type(adapter.hooks) is not tuple or not adapter.sources):
        raise ValueError("Invalid state adapter declaration")
    for field in adapter.fields:
        if (type(field) is not Field or field.scope not in SCOPES or not _NAME.fullmatch(field.key)
                or field.type not in {"json", "bool", "int", "text", "token_cache", "null", "tuple",
                                     "completed_task", "loop_ref", "monologue_ref", "infection_checker"}):
            raise ValueError("Invalid state field")
        if any(field.scope == prior.scope and field.key == prior.key
               for current in _REGISTRY.values() if current.name != adapter.name for prior in current.fields):
            raise ValueError("State field already owned")
    if len({(field.scope, field.key) for field in adapter.fields}) != len(adapter.fields):
        raise ValueError("Duplicate state field")
    for hook in adapter.hooks:
        if (type(hook) is not Hook or hook.source not in adapter.sources
                or hook.boundary not in {"constructor", "continuation"}
                or not hook.point or not hook.class_name):
            raise ValueError("Invalid hook declaration")
    for source in adapter.sources:
        _source(source)
    existing = _REGISTRY.get(adapter.name)
    if existing is not None and existing != adapter:
        raise ValueError("State adapter already registered")
    _REGISTRY[adapter.name] = adapter
    return adapter


def _identity(adapter):
    return {"name": adapter.name, "version": adapter.version,
            "sources": {name: _source(name) for name in adapter.sources},
            "codec": _source("helpers/durable/state_adapters.py"),
            "fields": [{"scope": f.scope, "key": f.key, "type": f.type} for f in adapter.fields],
            "hooks": [{"point": h.point, "class_name": h.class_name,
                       "source": h.source, "boundary": h.boundary} for h in adapter.hooks]}


def handled_keys(scope):
    return frozenset(field.key for adapter in _REGISTRY.values()
                     for field in adapter.fields if field.scope == scope)


class CompletedTask:
    """An inert known receipt implementing the memory/checker task read interface."""
    def __init__(self, result):
        self._result = result

    def done(self):
        return True

    def cancel(self):
        return False

    def result(self):
        return self._result

    def __await__(self):
        async def known():
            return self._result
        return known().__await__()


def _completed(value, *, decode):
    if value is None:
        return None
    if decode:
        if type(value) is dict and set(value) == {"background"}:
            from helpers.durable.background import validate_reference
            validate_reference(value["background"])
            return value
        if type(value) is not dict or set(value) != {"result"}:
            raise StateHeld("invalid_completed_task_receipt")
        _json(value["result"])
        return value
    from helpers.durable.background import TaskHandle
    if type(value) is TaskHandle:
        return {"background": value.reference}
    if type(value) is CompletedTask:
        result = value.result()
    elif type(value) is asyncio.Task:
        if not value.done() or value.cancelled():
            raise StateHeld("background_outcome_unknown")
        try:
            result = value.result()
        except BaseException:
            raise StateHeld("background_outcome_unknown") from None
    else:
        raise StateHeld("background_requires_explicit_adapter")
    return {"result": json.loads(_json(result))}


def _checker(value, *, decode):
    if value is None:
        return None
    scalar_fields = {"mode", "model_choice", "prompt", "history_size", "max_clarifications",
                     "iteration", "reasoning_log", "response_log"}
    if not decode:
        from plugins._infection_check.helpers.checker import InfectionChecker
        if type(value) is not InfectionChecker:
            raise StateHeld("unknown_infection_checker")
        result = {key: getattr(value, key) for key in scalar_fields}
        task = value._task
        from helpers.durable.background import TaskHandle
        # The safety model result is a 3-string tuple; preserve it explicitly.
        if task is not None:
            if type(task) is TaskHandle:
                result["background"] = task.reference
                receipt = None
            elif type(task) is CompletedTask:
                receipt = task.result()
            elif type(task) is asyncio.Task and task.done() and not task.cancelled():
                try:
                    receipt = task.result()
                except BaseException:
                    raise StateHeld("infection_check_outcome_unknown") from None
            else:
                raise StateHeld("infection_check_outcome_unknown")
            if receipt is not None and (type(receipt) is not tuple or len(receipt) != 3 or any(type(v) is not str for v in receipt)):
                raise StateHeld("invalid_infection_check_receipt")
            result["result"] = list(receipt) if receipt is not None else None
        else:
            result["result"] = None
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        roles = {SystemMessage: "system", HumanMessage: "human", AIMessage: "ai"}
        result["messages"] = []
        for message in value._check_msgs:
            if (type(message) not in roles or type(message.content) is not str
                    or message.additional_kwargs or message.response_metadata):
                raise StateHeld("infection_check_message_adapter_required")
            result["messages"].append({"role": roles[type(message)], "content": message.content})
        result["tool_name"] = getattr(value, "_tool_name", "")
        result["tool_args"] = getattr(value, "_tool_args", {})
        result["clarification"] = getattr(value, "_durable_clarification", None)
        value = result
    if type(value) is not dict or set(value) - {"background", "clarification"} != scalar_fields | {"result", "messages", "tool_name", "tool_args"}:
        raise StateHeld("invalid_infection_checker_state")
    if value.get("background") is not None:
        from helpers.durable.background import validate_reference
        validate_reference(value["background"])
    _json(value.get("clarification"))
    for key in ("mode", "model_choice", "prompt", "reasoning_log", "response_log", "tool_name"):
        if type(value[key]) is not str:
            raise StateHeld("invalid_infection_checker_state")
    if any(type(value[key]) is not int for key in ("history_size", "max_clarifications", "iteration")):
        raise StateHeld("invalid_infection_checker_state")
    if value["result"] is not None and (type(value["result"]) is not list or len(value["result"]) != 3
                                         or any(type(v) is not str for v in value["result"])):
        raise StateHeld("invalid_infection_check_receipt")
    if type(value["messages"]) is not list or type(value["tool_args"]) is not dict:
        raise StateHeld("invalid_infection_checker_state")
    for message in value["messages"]:
        if (type(message) is not dict or set(message) != {"role", "content"}
                or message["role"] not in {"system", "human", "ai"} or type(message["content"]) is not str):
            raise StateHeld("invalid_infection_check_message")
    return json.loads(_json(value))


def _materialize(field, value, agent):
    value = json.loads(_json(value))
    if field.type == "completed_task":
        if value is not None and "background" in value:
            from helpers.durable.background import TaskHandle
            return TaskHandle(agent, value["background"])
        return CompletedTask(value["result"]) if value is not None else None
    if field.type == "monologue_ref":
        return id(agent.loop_data) if value is not None else None
    if field.type == "loop_ref":
        return agent.loop_data if value is not None else None
    if field.type == "infection_checker" and value is not None:
        from plugins._infection_check.helpers.checker import InfectionChecker
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        checker = InfectionChecker(config={"mode": value["mode"], "model": value["model_choice"],
            "prompt": value["prompt"], "history_size": value["history_size"],
            "max_clarifications": value["max_clarifications"]}, iteration=value["iteration"])
        checker.reasoning_log, checker.response_log = value["reasoning_log"], value["response_log"]
        checker._tool_name, checker._tool_args = value["tool_name"], value["tool_args"]
        checker._task = CompletedTask(tuple(value["result"])) if value["result"] is not None else None
        if value.get("background"):
            from helpers.durable.background import TaskHandle
            checker._task = TaskHandle(agent, value["background"])
        checker._durable_clarification = value.get("clarification")
        roles = {"system": SystemMessage, "human": HumanMessage, "ai": AIMessage}
        checker._check_msgs = [roles[v["role"]](content=v["content"]) for v in value["messages"]]
        return checker
    return _typed(field, value, decode=True)


def _typed(field, value, *, decode=False):
    if field.type == "infection_checker":
        return _checker(value, decode=decode)
    if field.type == "completed_task":
        return _completed(value, decode=decode)
    if field.type in {"loop_ref", "monologue_ref"}:
        if value is not None and value != "current":
            raise StateHeld("invalid_loop_reference")
        return value
    if field.type == "tuple":
        if value is None:
            return None
        if type(value) is not (list if decode else tuple):
            raise StateHeld("invalid_tuple_state")
        result = json.loads(_json(list(value)))
        return tuple(result) if decode else result
    if field.type == "token_cache":
        if type(value) is not dict:
            raise StateHeld("invalid_token_cache")
        result = {}
        for key, pair in value.items():
            expected = list if decode else tuple
            if (type(key) is not str or type(pair) is not expected or len(pair) != 2
                    or not isinstance(pair[0], str) or not re.fullmatch(r"[a-f0-9]{64}", pair[0])
                    or type(pair[1]) is not int or pair[1] < 0):
                raise StateHeld("invalid_token_cache")
            result[key] = tuple(pair) if decode else list(pair)
        return result
    if (field.type == "bool" and type(value) is not bool
            or field.type == "int" and (type(value) is not int or value < 0)
            or field.type == "text" and type(value) is not str
            or field.type == "null" and value is not None):
        raise StateHeld("invalid_typed_state")
    # Return a detached copy; restore never aliases caller-owned manifest objects.
    return json.loads(_json(value))


def _agents(agent):
    context = agent.context
    current = getattr(context, "agent0", agent)
    result = {}
    while current is not None:
        number = getattr(current, "number", None)
        if type(number) is not int or number < 0 or number in result or len(result) >= 64:
            raise StateHeld("invalid_agent_state_chain")
        result[number] = current
        current = current.data.get(getattr(current, "DATA_NAME_SUBORDINATE", "_subordinate"))
    return result


def _mapping(agent, scope, kvp):
    if scope == "context":
        return agent.context.data
    if scope == "agent":
        return agent.data
    if scope == "kvp":
        return kvp
    loop = getattr(agent, "loop_data", None)
    return getattr(loop, scope.removeprefix("loop_"), None) if loop else None


def capture(agent, *, mask=None, kvp=None):
    """Capture actual declared fields only; no hidden I/O/publication or unknown-state erasure.

    ``kvp`` must be a context-local mapping (never the global helper store).
    The caller keeps its existing unknown-field gate using ``handled_keys``.
    """
    if mask is None:
        from helpers.durable.codec import masked
        mask = lambda value: masked(agent, value)
    entries = []
    for number, current in _agents(agent).items():
        for adapter in _REGISTRY.values():
            values = []
            for field in adapter.fields:
                if field.scope in {"context", "kvp"} and current is not agent.context.agent0:
                    continue
                mapping = _mapping(current, field.scope, kvp)
                if mapping is not None and field.key in mapping:
                    raw = mapping[field.key]
                    if field.type in {"loop_ref", "monologue_ref"} and raw is not None:
                        matching = raw is getattr(current, "loop_data", None) if field.type == "loop_ref" else raw == id(getattr(current, "loop_data", None))
                        if not matching:
                            raise StateHeld("stale_loop_reference")
                        raw = "current"
                    value = _typed(field, raw)
                    value = mask(value)
                    _typed(field, value, decode=True)  # Masking cannot violate the schema.
                    values.append({"scope": field.scope, "key": field.key, "value": value})
            if values:
                entries.append({"agent": number, "adapter": _identity(adapter), "values": values})
    manifest = {"version": 1, "entries": entries}
    _json(manifest)
    if sum(len(entry["values"]) for entry in entries) > MAX_FIELDS:
        raise StateHeld("state_field_limit_exceeded")
    return manifest


def validate(manifest):
    """Pre-construction source/schema validation; returns no executable objects."""
    _json(manifest)
    if (type(manifest) is not dict or set(manifest) != {"version", "entries"}
            or manifest["version"] != 1 or type(manifest["entries"]) is not list):
        raise StateHeld("invalid_state_manifest")
    seen, count = set(), 0
    for entry in manifest["entries"]:
        if (type(entry) is not dict or set(entry) != {"agent", "adapter", "values"}
                or type(entry["agent"]) is not int or entry["agent"] < 0
                or type(entry["adapter"]) is not dict or type(entry["values"]) is not list):
            raise StateHeld("invalid_state_entry")
        adapter = _REGISTRY.get(entry["adapter"].get("name"))
        if adapter is None or entry["adapter"] != _identity(adapter):
            raise StateHeld("state_adapter_missing_or_changed")
        for value in entry["values"]:
            if type(value) is not dict or set(value) != {"scope", "key", "value"}:
                raise StateHeld("invalid_state_field")
            field = next((f for f in adapter.fields
                          if f.scope == value["scope"] and f.key == value["key"]), None)
            token = (entry["agent"], value["scope"], value["key"])
            if field is None or token in seen:
                raise StateHeld("undeclared_or_duplicate_state_field")
            seen.add(token)
            count += 1
            if count > MAX_FIELDS:
                raise StateHeld("state_field_limit_exceeded")
            _typed(field, value["value"], decode=True)


def restore(agent, manifest, *, guard, kvp=None):
    """Validate before guarded in-memory assignment and audited local reconstructors.

    guard must assert the current run claim AND generation. No global persistent
    KVP file is changed; that projection must be committed by the caller.
    """
    validate(manifest)
    agents = _agents(agent)
    changes = []
    for entry in manifest["entries"]:
        current = agents.get(entry["agent"])
        if current is None:
            raise StateHeld("state_agent_missing")
        adapter = _REGISTRY[entry["adapter"]["name"]]
        for value in entry["values"]:
            field = next(f for f in adapter.fields if f.scope == value["scope"] and f.key == value["key"])
            if field.scope in {"context", "kvp"} and current is not agent.context.agent0:
                raise StateHeld("state_context_owner_mismatch")
            mapping = _mapping(current, field.scope, kvp)
            if not isinstance(mapping, dict):
                raise StateHeld("state_target_unavailable")
            changes.append((mapping, field, value["value"], current))
    guard()
    # Only audited local reconstructors run after the ownership check.
    prepared = [(mapping, field.key, _materialize(field, value, current))
                for mapping, field, value, current in changes]
    guard()
    for mapping, key, value in prepared:
        mapping[key] = value
    # Infection checker monologue identity is process-local; bind after loop restore.
    for current in agents.values():
        if "_plugin._infection_check" in current.data:
            current.data["_plugin._infection_check.mono"] = id(getattr(current, "loop_data", None))


def capture_hooks(hooks, *, boundary="continuation"):
    """Certify explicit declared hook identities; never execute or authorize replay.

    ``hooks`` is {point: [codec.identity(class), ...]}. The caller may pass only
    its additional hooks after checking its existing audited core allowlist.
    """
    if boundary not in {"constructor", "continuation"}:
        raise ValueError("Unknown hook boundary")
    declarations = []
    for point, implementations in hooks.items():
        for implementation in implementations:
            found = None
            for adapter in _REGISTRY.values():
                for hook in adapter.hooks:
                    if (hook.point == point and hook.boundary == boundary
                            and implementation == {"class": hook.class_name, "source": _source(hook.source)}):
                        found = {"point": point, "implementation": implementation, "adapter": _identity(adapter)}
            if found is None:
                raise StateHeld("state_hook_adapter_required")
            declarations.append(found)
    value = {"version": 1, "boundary": boundary, "hooks": declarations}
    _json(value)
    return value


def validate_hooks(manifest, hooks, *, boundary="continuation"):
    if manifest != capture_hooks(hooks, boundary=boundary):
        raise StateHeld("state_hook_adapter_missing_or_changed")


def reconcile_callback(owner, run_id, call_id, query, *, implementation, mask):
    """Query one unresolved callback receipt; unknown outcome never runs the callback.

    Trusted ``query(payload)`` is strictly a read/query adapter and returns
    {"known": bool, "result": JSON}. Its identity must match committed intent.
    The runner still owns eligibility and post-result projections.
    """
    call = owner.sync("get_call", run_id, call_id)
    if call is None or call["kind"] != "scheduler_callback":
        raise StateHeld("callback_intent_missing")
    if call["status"] == "completed":
        return call
    payload = call["payload"]
    if not isinstance(payload, dict) or payload.get("query_implementation") != implementation:
        raise StateHeld("callback_query_adapter_changed")
    path = inspect.getsourcefile(query)
    if (not path or implementation != {"name": query.__module__ + "." + query.__qualname__,
                                      "source": hashlib.sha256(Path(path).read_bytes()).hexdigest()}):
        raise StateHeld("callback_query_adapter_changed")
    owner.sync("assert_owner", run_id)
    outcome = query(payload)
    if type(outcome) is not dict or outcome.get("known") is not True or set(outcome) != {"known", "result"}:
        raise StateHeld("callback_outcome_unknown")
    outcome["result"] = mask(outcome["result"])
    _json(outcome["result"])
    owner.sync("assert_owner", run_id)
    return owner.sync("finish_call", run_id, call_id, outcome["result"])


# Real bundled producers, deliberately imported by source path rather than execution.
register(StateAdapter("chat_naming", 1, (Field("context", "chat_naming_manual", "bool"),),
    ("plugins/_chat_naming/helpers/naming.py", "plugins/_chat_naming/api/chat_name.py",
     "plugins/_chat_naming/commands/rename_command.py")))
register(StateAdapter("error_retry", 1,
    (Field("agent", "_plugin.error_retry.critical_exception_counter", "int"),),
    ("plugins/_error_retry/extensions/python/_functions/agent/Agent/monologue/start/_10_reset_critical_exception_counter.py",
     "plugins/_error_retry/extensions/python/_functions/agent/Agent/handle_exception/end/_80_retry_critical_exception.py")))
register(StateAdapter("context_window", 1,
    (Field("agent", "ctx_window"), Field("agent", "_context_window_usage_cache", "token_cache"),
     Field("agent", "context_window_provider_usage"), Field("loop_params_temporary", "context_window_usage")),
    ("plugins/_context_window/helpers/usage.py",)))
register(StateAdapter("browser_model", 1, (Field("agent", "_browser_model_active", "text"),),
    ("plugins/_browser/helpers/config.py",)))

register(StateAdapter("memory_recall", 1,
    (Field("agent", "_recall_memories_task", "completed_task"),
     Field("agent", "_recall_memories_iter", "int"), Field("agent", "_recall_memories_loop", "loop_ref"),
     Field("agent", "_recall_memories_result"), Field("agent", "_recall_memories_result_scope", "tuple"),
     Field("loop_extras_persistent", "memories"), Field("loop_extras_persistent", "solutions"),
     Field("loop_extras_temporary", "memory_recall_delayed")),
    ("plugins/_memory/extensions/python/message_loop_prompts_after/_50_recall_memories.py",
     "plugins/_memory/extensions/python/message_loop_prompts_after/_91_recall_wait.py",
     "helpers/cache.py", "helpers/durable/background.py")))
register(StateAdapter("memory_outbox", 1, (Field("agent", "_durable_memory_outbox"),),
    ("helpers/durable/background.py", "helpers/durable/memorization.py",
     "plugins/_memory/extensions/python/monologue_end/_50_memorize_fragments.py",
     "plugins/_memory/extensions/python/monologue_end/_51_memorize_solutions.py")))
register(StateAdapter("history_compression", 1, (Field("agent", "_organize_history_task", "completed_task"),),
    ("helpers/durable/background.py", "helpers/durable/history.py",
     "extensions/python/message_loop_end/_10_organize_history.py",
     "extensions/python/message_loop_prompts_before/_90_organize_history_wait.py")))
register(StateAdapter("infection_check", 1,
    (Field("agent", "_plugin._infection_check", "infection_checker"),
     Field("agent", "_plugin._infection_check.passed", "bool"),
     Field("agent", "_plugin._infection_check.mono", "monologue_ref")),
    ("plugins/_infection_check/helpers/checker.py", "helpers/durable/background.py")))

register(StateAdapter("core_constructor", 1, (),
    ("extensions/python/agent_init/_10_initial_message.py", "extensions/python/agent_init/_15_load_profile_settings.py"),
    (Hook("agent_init", "_10_initial_message.InitialMessage", "extensions/python/agent_init/_10_initial_message.py", "constructor"),
     Hook("agent_init", "_15_load_profile_settings.LoadProfileSettings", "extensions/python/agent_init/_15_load_profile_settings.py", "constructor"))))
