from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class LoopData:
    """Data structure for managing loop state with type hints"""

    messages: List[Any]
    state: Dict[str, Any]
    context: Dict[str, Any]
    memory: Dict[str, Any]

    def __init__(self):
        self.messages = []
        self.state = {}
        self.context = {}
        self.memory = {}


class AgentException(Exception):
    """Base exception class for Agent errors"""

    pass
