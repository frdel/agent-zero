from agent import Agent
from python.helpers.tool import Tool, Response


class CallSubordinate(Tool):
    def __init__(self, agent: Agent, name: str, args: dict, message: str):
        super().__init__(agent, name, args, message)
        self.context = agent.context  # Add this line

    async def execute(self, **kwargs):
        subordinate = self.context.agent0  # Ensure agent0 exists
        msg = self.args.get("message", "")
        await subordinate.communicate(msg)
        return "Task completed."
