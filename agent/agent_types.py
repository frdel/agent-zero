from dataclasses import dataclass, field
from typing import List, Any, Dict, Protocol, runtime_checkable
from langchain_core.messages import BaseMessage


@dataclass
class LoopData:
    message: str = ""
    history_from: int = 0
    iteration: int = 0
    system: List[str] = field(default_factory=list)
    history: List[BaseMessage] = field(default_factory=list)


class AgentException(Exception):
    pass


@runtime_checkable
class BaseAgent(Protocol):
    """Protocol defining the Agent interface to avoid circular imports"""

    agent_name: str
    context: Any
    data: Dict[str, Any]
    config: Any

    def read_prompt(self, file: str, **kwargs) -> str:
        """Read a prompt file and format it with the given kwargs"""
        ...

    async def append_message(self, msg: str, human: bool = False) -> None:
        """Append a message to the agent's history"""
        ...
