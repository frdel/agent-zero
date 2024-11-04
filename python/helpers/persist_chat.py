from collections import OrderedDict
from dataclasses import dataclass
import json
import os
import uuid
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Protocol
from typing_extensions import TypedDict  # Or other specific types you need

from initialize import initialize
from python.helpers import files
from python.helpers.log import Log, LogItem


class BaseMessage(Protocol):
    """Protocol for message types"""

    type: str
    content: str


class HumanMessage:
    """Human message type"""

    type = "human"

    def __init__(self, content: str):
        self.content = content


class AIMessage:
    """AI message type"""

    type = "ai"

    def __init__(self, content: str):
        self.content = content


CHATS_FOLDER = "tmp/chats"
LOG_SIZE = 1000


@dataclass
class AgentContext:
    """Context for managing agent state"""

    id: str
    config: Dict[str, Any]
    name: Optional[str]
    log: Log
    paused: bool = False
    agent0: Optional["Agent"] = None
    streaming_agent: Optional["Agent"] = None


class Agent:
    """Agent class with persistence capabilities"""

    def __init__(self, number: int, config: Dict[str, Any], context: AgentContext):
        self.number = number
        self.config = config
        self.context = context
        self.data: Dict[str, Any] = {}
        self.history: List[Union[HumanMessage, AIMessage]] = []

    def set_data(self, key: str, value: Any) -> None:
        """Set data for the agent"""
        self.data[key] = value


class ChatPersistenceError(Exception):
    """Custom exception for chat persistence operations."""

    pass


def ensure_chat_directory() -> None:
    """Ensure the chats directory exists."""
    try:
        os.makedirs(CHATS_FOLDER, exist_ok=True)
    except OSError as e:
        raise ChatPersistenceError(f"Failed to create chats directory: {e}")


def save_tmp_chat(context: AgentContext) -> None:
    """
    Save a chat context to a temporary file.

    Args:
        context: The AgentContext to save

    Raises:
        ChatPersistenceError: If saving fails
    """
    try:
        ensure_chat_directory()
        relative_path = _get_file_path(context.id)
        data = _serialize_context(context)
        js = _safe_json_serialize(data, ensure_ascii=False)
        if js == "{}":
            raise ChatPersistenceError("Serialization resulted in empty JSON")
        files.write_file(relative_path, js)
    except Exception as e:
        raise ChatPersistenceError(f"Failed to save chat: {str(e)}")


def load_tmp_chats() -> List[str]:
    """
    Load all temporary chat contexts.

    Returns:
        List of context IDs

    Raises:
        ChatPersistenceError: If loading fails
    """
    try:
        ensure_chat_directory()
        json_files = files.list_files(CHATS_FOLDER, "*.json")
        ctxids = []
        for file in json_files:
            try:
                path = files.get_abs_path(CHATS_FOLDER, file)
                js = files.read_file(path)
                data = json.loads(js)
                ctx = _deserialize_context(data)
                if ctx and ctx.id:
                    ctxids.append(ctx.id)
            except Exception as e:
                Log().logs.append(
                    LogItem(
                        log=Log(),
                        no=len(Log().logs),
                        type="error",
                        heading="Load Error",
                        content=f"Failed to load chat {file}: {str(e)}",
                        temp=False,
                    )
                )
                continue
        return ctxids
    except Exception as e:
        raise ChatPersistenceError(f"Failed to load chats: {str(e)}")


def load_json_chats(jsons: List[str]) -> List[str]:
    """
    Load chat contexts from JSON strings.

    Args:
        jsons: List of JSON strings

    Returns:
        List of context IDs

    Raises:
        ChatPersistenceError: If loading fails
    """
    try:
        ctxids = []
        for js in jsons:
            try:
                data = json.loads(js)
                ctx = _deserialize_context(data)
                if ctx and ctx.id:
                    ctxids.append(ctx.id)
            except json.JSONDecodeError as e:
                Log().logs.append(
                    LogItem(
                        log=Log(),
                        no=len(Log().logs),
                        type="error",
                        heading="JSON Error",
                        content=f"Invalid JSON format: {str(e)}",
                        temp=False,
                    )
                )
            except Exception as e:
                Log().logs.append(
                    LogItem(
                        log=Log(),
                        no=len(Log().logs),
                        type="error",
                        heading="Load Error",
                        content=f"Failed to load chat: {str(e)}",
                        temp=False,
                    )
                )
        return ctxids
    except Exception as e:
        raise ChatPersistenceError(f"Failed to load JSON chats: {str(e)}")


def export_json_chat(context: AgentContext) -> str:
    """
    Export a chat context to JSON.

    Args:
        context: The AgentContext to export

    Returns:
        JSON string representation

    Raises:
        ChatPersistenceError: If export fails
    """
    try:
        data = _serialize_context(context)
        js = _safe_json_serialize(data, ensure_ascii=False)
        if js == "{}":
            raise ChatPersistenceError("Serialization resulted in empty JSON")
        return js
    except Exception as e:
        raise ChatPersistenceError(f"Failed to export chat: {str(e)}")


def remove_chat(ctxid: str) -> None:
    """
    Remove a chat context file.

    Args:
        ctxid: The context ID to remove

    Raises:
        ChatPersistenceError: If removal fails
    """
    try:
        files.delete_file(_get_file_path(ctxid))
    except Exception as e:
        raise ChatPersistenceError(f"Failed to remove chat {ctxid}: {str(e)}")


def _get_file_path(ctxid: str) -> str:
    """Get the file path for a chat context."""
    return f"{CHATS_FOLDER}/{ctxid}.json"


def _serialize_context(context: AgentContext) -> Dict[str, Any]:
    """
    Serialize an AgentContext to a dictionary.

    Args:
        context: The AgentContext to serialize

    Returns:
        Serialized context as a dictionary
    """
    if not context:
        raise ValueError("Context cannot be None")

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


def _serialize_agent(agent: Agent) -> Dict[str, Any]:
    """
    Serialize an Agent to a dictionary.

    Args:
        agent: The Agent to serialize

    Returns:
        Serialized agent as a dictionary
    """
    if not agent:
        raise ValueError("Agent cannot be None")

    data = {k: v for k, v in agent.data.items() if k not in ["superior", "subordinate"]}

    history = []
    for msg in agent.history:
        if hasattr(msg, "type") and hasattr(msg, "content"):
            history.append({"type": msg.type, "content": msg.content})

    return {
        "number": agent.number,
        "data": data,
        "history": history,
    }


def _serialize_log(log: Log) -> Dict[str, Any]:
    """
    Serialize a Log to a dictionary.

    Args:
        log: The Log to serialize

    Returns:
        Serialized log as a dictionary
    """
    if not log:
        return {"guid": str(uuid.uuid4()), "logs": [], "progress": "", "progress_no": 0}

    return {
        "guid": log.guid,
        "logs": [
            item.output() for item in log.logs[-LOG_SIZE:] if hasattr(item, "output")
        ],
        "progress": log.progress,
        "progress_no": log.progress_no,
    }


def _deserialize_context(data: Dict[str, Any]) -> Optional[AgentContext]:
    """
    Deserialize a dictionary to an AgentContext.

    Args:
        data: The dictionary to deserialize

    Returns:
        Deserialized AgentContext or None if deserialization fails
    """
    try:
        config = initialize()
        log = _deserialize_log(data.get("log", {}))

        context = AgentContext(
            id=str(uuid.uuid4()),
            config=config,
            name=data.get("name"),
            log=log,
            paused=False,
        )

        agents = data.get("agents", [])
        agent0 = _deserialize_agents(agents, config, context)
        streaming_agent = agent0

        streaming_agent_number = data.get("streaming_agent", 0)
        while streaming_agent and streaming_agent.number != streaming_agent_number:
            streaming_agent = streaming_agent.data.get("subordinate")

        context.agent0 = agent0
        context.streaming_agent = streaming_agent

        return context
    except Exception as e:
        Log().logs.append(
            LogItem(
                log=Log(),
                no=len(Log().logs),
                type="error",
                heading="Deserialization Error",
                content=f"Context deserialization failed: {str(e)}",
                temp=False,
            )
        )
        return None


def _deserialize_agents(
    agents: List[Dict[str, Any]], config: Dict[str, Any], context: AgentContext
) -> Agent:
    """
    Deserialize a list of dictionaries to connected Agent objects.

    Args:
        agents: List of agent dictionaries
        config: Configuration dictionary
        context: AgentContext instance

    Returns:
        The first Agent in the chain
    """
    prev: Optional[Agent] = None
    zero: Optional[Agent] = None

    for ag in agents:
        try:
            current = Agent(number=ag["number"], config=config, context=context)
            current.data = ag.get("data", {})
            current.history = _deserialize_history(ag.get("history", []))

            if not zero:
                zero = current

            if prev:
                prev.set_data("subordinate", current)
                current.set_data("superior", prev)
            prev = current
        except Exception as e:
            Log().logs.append(
                LogItem(
                    log=Log(),
                    no=len(Log().logs),
                    type="error",
                    heading="Agent Error",
                    content=f"Agent deserialization failed: {str(e)}",
                    temp=False,
                )
            )
            continue

    return zero or Agent(0, config, context)


def _deserialize_history(
    history: List[Dict[str, Any]]
) -> List[Union[HumanMessage, AIMessage]]:
    """
    Deserialize a list of dictionaries to message objects.

    Args:
        history: List of message dictionaries

    Returns:
        List of deserialized messages
    """
    result = []
    for hist in history:
        try:
            content = hist.get("content", "")
            msg_type = hist.get("type")
            if msg_type == "human":
                msg = HumanMessage(content=content)
            elif msg_type == "ai":
                msg = AIMessage(content=content)
            else:
                continue
            result.append(msg)
        except Exception as e:
            Log().logs.append(
                LogItem(
                    log=Log(),
                    no=len(Log().logs),
                    type="error",
                    heading="Message Error",
                    content=f"Message deserialization failed: {str(e)}",
                    temp=False,
                )
            )
            continue
    return result


def _deserialize_log(data: Dict[str, Any]) -> Log:
    """
    Deserialize a dictionary to a Log object.

    Args:
        data: The dictionary to deserialize

    Returns:
        Deserialized Log object
    """
    log = Log()
    try:
        log.guid = data.get("guid", str(uuid.uuid4()))
        log.progress = data.get("progress", "")
        log.progress_no = data.get("progress_no", 0)

        for i, item_data in enumerate(data.get("logs", [])):
            try:
                kvps = OrderedDict(item_data["kvps"]) if item_data.get("kvps") else None
                log.logs.append(
                    LogItem(
                        log=log,
                        no=item_data["no"],
                        type=item_data["type"],
                        heading=item_data.get("heading", ""),
                        content=item_data.get("content", ""),
                        kvps=kvps,
                        temp=item_data.get("temp", False),
                    )
                )
                log.updates.append(i)
            except Exception as e:
                Log().logs.append(
                    LogItem(
                        log=Log(),
                        no=len(Log().logs),
                        type="error",
                        heading="LogItem Error",
                        content=f"LogItem deserialization failed: {str(e)}",
                        temp=False,
                    )
                )
                continue
    except Exception as e:
        Log().logs.append(
            LogItem(
                log=Log(),
                no=len(Log().logs),
                type="error",
                heading="Log Error",
                content=f"Log deserialization failed: {str(e)}",
                temp=False,
            )
        )

    return log


def _safe_json_serialize(obj: Any, **kwargs) -> str:
    """
    Safely serialize an object to JSON, handling non-serializable types.

    Args:
        obj: The object to serialize
        **kwargs: Additional arguments for json.dumps

    Returns:
        JSON string
    """

    def serializer(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: v for k, v in o.items() if is_json_serializable(v)}
        elif isinstance(o, (list, tuple)):
            return [item for item in o if is_json_serializable(item)]
        elif is_json_serializable(o):
            return o
        return None

    def is_json_serializable(item: Any) -> bool:
        try:
            json.dumps(item)
            return True
        except (TypeError, OverflowError):
            return False

    try:
        return json.dumps(obj, default=serializer, **kwargs)
    except Exception as e:
        Log().logs.append(
            LogItem(
                log=Log(),
                no=len(Log().logs),
                type="error",
                heading="JSON Error",
                content=f"JSON serialization failed: {str(e)}",
                temp=False,
            )
        )
        return "{}"
