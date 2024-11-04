# D:\Dev2\agent-zero\agent\__init__.py

from .agent_types import LoopData
from .agent_context import AgentContext
from .config import AgentConfig  # Fixed import to use correct module


class Agent:
    """Base Agent class"""

    def __init__(self):
        self.loop_data = None
        self.config = {}

    def initialize(self, config=None):
        self.config = config or {}
        self.loop_data = LoopData()


# Export the classes
__all__ = ["Agent", "LoopData", "AgentContext", "AgentConfig"]
