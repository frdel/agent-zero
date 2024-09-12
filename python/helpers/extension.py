from abc import abstractmethod
from typing import Any
from agent import Agent
    
class Extension:

    def __init__(self, agent: Agent, *args, **kwargs):
        self.agent = agent
        self.kwargs = kwargs

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass