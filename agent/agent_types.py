from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class LoopData:
    """Data structure for managing loop state"""
    iteration: int = -1
    message: str = ""
    history_from: int = 0
    history: List[Any] = field(default_factory=list)
    system: List[str] = field(default_factory=list)
    messages: List[Any] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)


class AgentException(Exception):
    """Base exception class for Agent errors"""
    pass


class Response:
    """Base class for tool responses"""
    def __init__(self, message: str = "", break_loop: bool = False):
        self.message = message
        self.break_loop = break_loop
