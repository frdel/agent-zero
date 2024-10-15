from collections import OrderedDict
from typing import Any
import uuid
from agent import Agent, AgentConfig, AgentContext, HumanMessage, AIMessage
from python.helpers import files
import json
from initialize import initialize

from python.helpers.log import Log, LogItem

CHATS_FOLDER = "tmp/chats"
LOG_SIZE = 1000


def save_tmp_chat(context: AgentContext):
    relative_path = _get_file_path(context.id)
    data = _serialize_context(context)
    js = _safe_json_serialize(data, ensure_ascii=False)
    files.write_file(relative_path, js)

def load_tmp_chats():
    json_files = files.list_files("tmp/chats", "*.json")
    ctxids = []
    for file in json_files:
        path = files.get_abs_path(CHATS_FOLDER, file)
        js = files.read_file(path)
        data = json.loads(js)
        ctx = _deserialize_context(data)
        ctxids.append(ctx.id)
    return ctxids

def load_json_chats(jsons: list[str]):
    ctxids = []
    for js in jsons:
        data = json.loads(js)
        ctx = _deserialize_context(data)
        ctxids.append(ctx.id)
    return ctxids

def export_json_chat(context: AgentContext):
    data = _serialize_context(context)
    js = _safe_json_serialize(data, ensure_ascii=False)
    return js

def remove_chat(ctxid):
    files.delete_file(_get_file_path(ctxid))


def _get_file_path(ctxid: str):
    return f"{CHATS_FOLDER}/{ctxid}.json"


def _serialize_context(context: AgentContext):
    # serialize agents
    agents = []
    agent = context.agent0
    while agent:
        agents.append(_serialize_agent(agent))
        agent = agent.data.get("subordinate", None)

    return {
        "id": context.id,
        "agents": agents,
        "streaming_agent": (
            context.streaming_agent.number if context.streaming_agent else 0
        ),
        "log": _serialize_log(context.log),
    }


def _serialize_agent(agent: Agent):
    data = {**agent.data}
    if "superior" in data:
        del data["superior"]
    if "subordinate" in data:
        del data["subordinate"]

    history = []
    for msg in agent.history:
        history.append({"type": msg.type, "content": msg.content})

    return {
        "number": agent.number,
        "data": data,
        "history": history,
    }


def _serialize_log(log: Log):
    return {
        "guid": log.guid,
        "logs": [item.output() for item in log.logs[-LOG_SIZE:]]
,  # serialize LogItem objects
        "progress": log.progress,
        "progress_no": log.progress_no,
    }


def _deserialize_context(data):
    config = initialize()
    log = _deserialize_log(data.get("log", None))

    context = AgentContext(
        config=config,
        # id=data.get("id", None), #get new id
        name=data.get("name", None),
        log=log,
        paused=False,
        # agent0=agent0,
        # streaming_agent=straming_agent,
    )

    agents = data.get("agents", [])
    agent0 = _deserialize_agents(agents, config, context)
    streaming_agent = agent0
    while streaming_agent.number != data.get("streaming_agent", 0):
        streaming_agent = streaming_agent.data.get("subordinate", None)
        
    context.agent0 = agent0
    context.streaming_agent = streaming_agent

    return context


def _deserialize_agents(
    agents: list[dict[str, Any]], config: AgentConfig, context: AgentContext
) -> Agent:
    prev: Agent | None = None
    zero: Agent | None = None

    for ag in agents:
        current = Agent(
            number=ag["number"],
            config=config,
            context=context,
        )
        current.data = ag.get("data", {})
        current.history = _deserialize_history(ag.get("history", []))

        if not zero:
            zero = current

        if prev:
            prev.set_data("subordinate", current)
            current.set_data("superior", prev)
        prev = current

    return zero or Agent(0, config, context)


def _deserialize_history(history: list[dict[str, Any]]):
    result = []
    for hist in history:
        content = hist.get("content", "")
        msg = (
            HumanMessage(content=content)
            if hist.get("type") == "human"
            else AIMessage(content=content)
        )
        result.append(msg)
    return result


def _deserialize_log(data: dict[str, Any]) -> "Log":
    log = Log()
    log.guid = data.get("guid", str(uuid.uuid4()))
    log.progress = data.get("progress", "")
    log.progress_no = data.get("progress_no", 0)

    # Deserialize the list of LogItem objects
    i = 0
    for item_data in data.get("logs", []):
        log.logs.append(LogItem(
            log=log,  # restore the log reference
            no=item_data["no"],
            type=item_data["type"],
            heading=item_data.get("heading", ""),
            content=item_data.get("content", ""),
            kvps=OrderedDict(item_data["kvps"]) if item_data["kvps"] else None,
            temp=item_data.get("temp", False),
        ))
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
