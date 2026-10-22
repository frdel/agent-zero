import json
import os
import tempfile
import uuid
from collections import OrderedDict
from contextlib import nullcontext
from datetime import datetime
from typing import Any

from agent import Agent, AgentConfig, AgentContext, AgentContextType
from helpers import files, history, settings
from helpers.litellm_transport import delete_stored_response_ids
from helpers.localization import Localization
from initialize import initialize_agent

from helpers.log import Log, LogItem

CHATS_FOLDER = "usr/chats"
LOG_SIZE = 1000
CHAT_FILE_NAME = "chat.json"
SAVED_CHAT_CONTEXT_DATA_KEY = "_persist_chat_saved"


def _fallback_datetime_iso() -> str:
    return datetime.fromtimestamp(0, tz=Localization.get().get_tzinfo()).isoformat()


def _parse_persisted_datetime(value: str | None) -> datetime:
    raw_value = value or _fallback_datetime_iso()
    dt = datetime.fromisoformat(raw_value)
    if dt.tzinfo is None:
        dt = Localization.get().localize_naive_datetime(dt)
    return dt


def get_chat_folder_path(ctxid: str):
    """
    Get the folder path for any context (chat or task).

    Args:
        ctxid: The context ID

    Returns:
        The absolute path to the context folder
    """
    return files.get_abs_path(CHATS_FOLDER, ctxid)

def get_chat_msg_files_folder(ctxid: str):
    return files.get_abs_path(get_chat_folder_path(ctxid), "messages")

def save_tmp_chat(context: AgentContext):
    """Save context to the chats folder"""
    # Skip saving BACKGROUND contexts as they should be ephemeral
    if context.type == AgentContextType.BACKGROUND:
        return

    path = _get_chat_file_path(context.id)
    data = _serialize_context(context)
    js = _safe_json_serialize(data, ensure_ascii=False)
    _write_atomic(path, js)
    mark_chat_saved(context)


def save_tmp_chats():
    """Save all contexts to the chats folder"""
    for context in AgentContext.all():
        # Skip BACKGROUND contexts as they should be ephemeral
        if context.type == AgentContextType.BACKGROUND:
            continue
        save_tmp_chat(context)


def load_tmp_chats():
    """Load all contexts from the chats folder"""
    _convert_v080_chats()
    folders = files.list_files(CHATS_FOLDER, "*")
    json_files = []
    for folder_name in folders:
        chat_file = _get_chat_file_path(folder_name)
        if files.exists(chat_file):
            json_files.append(chat_file)

    ctxids = []
    with settings.version_cache_scope():
        for file in json_files:
            try:
                js = files.read_file(file)
                data = json.loads(js)
                ctx = _deserialize_context(data)
                mark_chat_saved(ctx)
                ctxids.append(ctx.id)
            except Exception as e:
                print(f"Error loading chat {file}: {e}")
    return ctxids


def _get_chat_file_path(ctxid: str):
    return files.get_abs_path(CHATS_FOLDER, ctxid, CHAT_FILE_NAME)


def chat_file_exists(ctxid: str) -> bool:
    """True if this context has a persisted chat.json on disk."""
    return files.exists(_get_chat_file_path(ctxid))


def _write_atomic(path: str, content: str) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=directory
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content.encode("utf-8", "replace").decode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def mark_chat_saved(context: AgentContext) -> None:
    context.data[SAVED_CHAT_CONTEXT_DATA_KEY] = True


def saved_chat_ids() -> set[str]:
    return {
        files.basename(files.dirname(path))
        for path in files.find_existing_paths_by_pattern(
            files.get_abs_path(CHATS_FOLDER, "*", CHAT_FILE_NAME)
        )
    }


def _convert_v080_chats():
    json_files = files.list_files(CHATS_FOLDER, "*.json")
    for file in json_files:
        path = files.get_abs_path(CHATS_FOLDER, file)
        name = file.rstrip(".json")
        new = _get_chat_file_path(name)
        files.move_file(path, new)


def load_json_chats(jsons: list[str]):
    """Load contexts from JSON strings"""
    ctxids = []
    for js in jsons:
        data = json.loads(js)
        if "id" in data:
            del data["id"]  # remove id to get new
        ctx = _deserialize_context(data)
        ctxids.append(ctx.id)
    return ctxids


def export_json_chat(context: AgentContext):
    """Export context as JSON string"""
    data = _serialize_context(context)
    js = _safe_json_serialize(data, ensure_ascii=False)
    return js


def remove_chat(ctxid):
    """Remove a chat or task context"""
    if not isinstance(ctxid, str) or not ctxid.strip():
        raise ValueError("remove_chat: context id must not be empty")
    from helpers.durable.runtime import control, service
    owner = service()
    # Fence execution before reading known outcomes, but retain private ledger
    # payloads until provider cleanup has collected their normalized IDs.
    with owner.lock if owner else nullcontext():
        descendants = control(ctxid, "cancel") if owner else []
        _delete_provider_responses_for_chat(ctxid)
        for child_id in descendants:
            _delete_provider_responses_for_chat(child_id)
        control(ctxid, "delete")
    for child_id in descendants:
        AgentContext.remove(child_id)
        files.delete_dir(get_chat_folder_path(child_id))
    path = get_chat_folder_path(ctxid)
    files.delete_dir(path)


def remove_msg_files(ctxid):
    """Remove all message files for a chat or task context"""
    if not isinstance(ctxid, str) or not ctxid.strip():
        raise ValueError("remove_msg_files: context id must not be empty")
    path = get_chat_msg_files_folder(ctxid)
    files.delete_dir(path)


def _serialize_context(context: AgentContext):
    profile = str(
        getattr(context.agent0.config, "profile", None)
        or getattr(context.config, "profile", None)
        or ""
    )

    # serialize agents
    agents = []
    agent = context.agent0
    while agent:
        agents.append(_serialize_agent(agent))
        agent = agent.data.get(Agent.DATA_NAME_SUBORDINATE, None)


    data = {k: v for k, v in context.data.items() if not k.startswith("_")}
    output_data = {k: v for k, v in context.output_data.items() if not k.startswith("_")}

    return {
        "id": context.id,
        "name": context.name,
        "created_at": (
            Localization.get().serialize_datetime(context.created_at)
            if context.created_at
            else _fallback_datetime_iso()
        ),
        "type": context.type.value,
        "last_message": (
            Localization.get().serialize_datetime(context.last_message)
            if context.last_message
            else _fallback_datetime_iso()
        ),
        "agents": agents,
        "streaming_agent": (
            context.streaming_agent.number if context.streaming_agent else 0
        ),
        "agent_profile": profile,
        "log": _serialize_log(context.log),
        "data": data,
        "output_data": output_data,
    }


def _serialize_agent(agent: Agent):
    data = {k: v for k, v in agent.data.items() if not k.startswith("_")}

    history = agent.history.serialize()

    return {
        "number": agent.number,
        "agent_profile": str(getattr(agent.config, "profile", "") or ""),
        "data": data,
        "history": history,
    }


def _serialize_log(log: Log):
    # Guard against concurrent log mutations while serializing.
    with log._lock:
        logs = [item.output() for item in log.logs[-LOG_SIZE:]]  # serialize LogItem objects
        guid = log.guid
        progress = log.progress
        progress_no = log.progress_no
    return {
        "guid": guid,
        "logs": logs,
        "progress": progress,
        "progress_no": progress_no,
    }


def _deserialize_context(data):
    profile = data.get("agent_profile")
    override_settings = {"agent_profile": profile} if profile else None
    config = initialize_agent(override_settings=override_settings)
    log = _deserialize_log(data.get("log", None))

    context = AgentContext(
        config=config,
        id=data.get("id", None),  # get new id
        name=data.get("name", None),
        created_at=(
            _parse_persisted_datetime(data.get("created_at"))
        ),
        type=AgentContextType(data.get("type", AgentContextType.USER.value)),
        last_message=(
            _parse_persisted_datetime(data.get("last_message"))
        ),
        log=log,
        paused=False,
        data=data.get("data", {}),
        output_data=data.get("output_data", {}),
        # agent0=agent0,
        # streaming_agent=straming_agent,
    )

    agents = data.get("agents", [])
    agent0 = _deserialize_agents(agents, config, context)
    streaming_agent = agent0
    while streaming_agent and streaming_agent.number != data.get("streaming_agent", 0):
        streaming_agent = streaming_agent.data.get(Agent.DATA_NAME_SUBORDINATE, None)

    context.agent0 = agent0
    context.config = agent0.config
    context.streaming_agent = streaming_agent

    return context


def _deserialize_agent_config(
    agent_data: dict[str, Any], fallback_config: AgentConfig
) -> AgentConfig:
    fallback_profile = str(getattr(fallback_config, "profile", "") or "")
    profile = str(agent_data.get("agent_profile") or fallback_profile).strip()
    if profile == fallback_profile:
        return fallback_config
    override_settings = {"agent_profile": profile} if profile else None
    return initialize_agent(override_settings=override_settings)


def _deserialize_agents(
    agents: list[dict[str, Any]], config: AgentConfig, context: AgentContext
) -> Agent:
    prev: Agent | None = None
    zero: Agent | None = None

    for ag in agents:
        current = Agent(
            number=ag["number"],
            config=_deserialize_agent_config(ag, config),
            context=context,
        )
        current.data = ag.get("data", {})
        current.history = history.deserialize_history(
            ag.get("history", ""), agent=current
        )
        if not zero:
            zero = current

        if prev:
            prev.set_data(Agent.DATA_NAME_SUBORDINATE, current)
            current.set_data(Agent.DATA_NAME_SUPERIOR, prev)
        prev = current

    return zero or Agent(0, config, context)


# def _deserialize_history(history: list[dict[str, Any]]):
#     result = []
#     for hist in history:
#         content = hist.get("content", "")
#         msg = (
#             HumanMessage(content=content)
#             if hist.get("type") == "human"
#             else AIMessage(content=content)
#         )
#         result.append(msg)
#     return result


def _deserialize_log(data: dict[str, Any]) -> "Log":
    log = Log()
    log.guid = data.get("guid", str(uuid.uuid4()))
    log.set_initial_progress()

    # Deserialize the list of LogItem objects
    i = 0
    for item_data in data.get("logs", []):
        agentno = item_data.get("agentno")
        if agentno is None:
            agentno = item_data.get("agent_number", 0)
        log.logs.append(
            LogItem(
                log=log,  # restore the log reference
                no=i,  # item_data["no"],
                type=item_data["type"],
                heading=item_data.get("heading", ""),
                content=item_data.get("content", ""),
                kvps=OrderedDict(item_data["kvps"]) if item_data["kvps"] else None,
                timestamp=item_data.get("timestamp", 0.0),
                agentno=agentno,
                id=item_data.get("id"),
            )
        )
        log.updates.append(i)
        i += 1

    return log


def _safe_json_serialize(obj, **kwargs):
    def serializer(o):
        if isinstance(o, dict):
            return {k: v for k, v in o.items() if is_json_serializable(v)}
        elif isinstance(o, (list, tuple)):
            return [item for item in o if is_json_serializable(item)]
        elif is_json_serializable(o):
            return o
        else:
            return None  # Skip this property

    def is_json_serializable(item):
        try:
            json.dumps(item)
            return True
        except (TypeError, OverflowError):
            return False

    return json.dumps(obj, default=serializer, **kwargs)


def _delete_provider_responses_for_chat(ctxid: str) -> None:
    projections = []
    try:
        projections.append(json.loads(files.read_file(_get_chat_file_path(ctxid))))
    except Exception:
        pass
    # Live state can carry an opt-out newer than either saved projection.
    context = AgentContext.get(ctxid)
    if context and context.data.get("responses_delete_on_chat_delete") is False:
        return
    agent = context.agent0 if context else None
    while agent:
        if agent.data.get("responses_delete_on_chat_delete") is False:
            return
        agent = agent.data.get(Agent.DATA_NAME_SUBORDINATE)

    from helpers.durable.runtime import service
    owner = service()
    normalized_results = []
    if owner:
        try:
            for header in owner.sync("list_run_headers", context_id=ctxid):
                if header["payloads_pruned"]:
                    continue
                run = owner.sync("get_run", header["run_id"])
                checkpoint = run["checkpoint"]
                if not isinstance(checkpoint, dict):
                    continue
                projections.append(checkpoint.get("context") or {})
                normalized_results.append(checkpoint.get("result"))
                normalized_results.extend(call["result"] for call in owner.sync("calls", header["run_id"])
                                          if call["kind"] == "model" and call["status"] == "completed"
                                          and not call["payloads_pruned"])
        except Exception:
            # Unverified recovery state may contain an opt-out. Local deletion
            # still proceeds, without issuing provider calls under that doubt.
            print("Warning: provider response cleanup skipped because recovery data could not be verified.")
            return
    if any(_responses_delete_disabled(data) for data in projections):
        return
    response_ids = list(dict.fromkeys(response_id for data in projections for response_id in _collect_response_ids(data)))
    for result in normalized_results:
        # Only the normalized LLMResult identity is authoritative here. Never
        # search arbitrary provider raw metadata or reinterpret call arguments.
        if isinstance(result, dict) and result.get("mode") == "responses":
            response_id = result.get("response_id")
            if isinstance(response_id, str) and response_id.strip() and response_id not in response_ids:
                response_ids.append(response_id)
    if not response_ids:
        return
    try:
        failures = delete_stored_response_ids(response_ids)
        count = len(failures or [])
    except Exception:
        count = len(response_ids)
    if count:
        print(f"Warning: provider response cleanup failed for {count} stored responses.")


def _responses_delete_disabled(data: dict[str, Any]) -> bool:
    if data.get("responses_delete_on_chat_delete") is False:
        return True
    context_data = data.get("data")
    if isinstance(context_data, dict) and context_data.get("responses_delete_on_chat_delete") is False:
        return True
    for agent_data in data.get("agents", []) or []:
        if not isinstance(agent_data, dict):
            continue
        state = agent_data.get("data")
        if isinstance(state, dict) and state.get("responses_delete_on_chat_delete") is False:
            return True
    return False


def _collect_response_ids(data: Any) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        response_id = str(value or "").strip()
        if response_id and response_id not in seen:
            seen.add(response_id)
            found.append(response_id)

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            state = obj.get(Agent.DATA_NAME_RESPONSES_STATE)
            if isinstance(state, dict):
                add(state.get("response_id"))
                for response_id in state.get("response_ids") or []:
                    add(response_id)

            metadata = obj.get("metadata")
            if isinstance(metadata, dict):
                responses = metadata.get("responses")
                if isinstance(responses, dict):
                    add(responses.get("response_id"))

            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
        elif isinstance(obj, str) and '"response_id"' in obj:
            try:
                walk(json.loads(obj))
            except Exception:
                return

    walk(data)
    return found
