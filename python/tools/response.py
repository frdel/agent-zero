from typing import Any
from agent import Agent
from python.helpers.tool import Tool, Response


class ResponseTool(Tool):
    async def execute(self, **kwargs) -> Response:
        timeout = 60  # Default timeout
        if hasattr(self.agent, "config"):
            timeout = getattr(self.agent.config, "response_timeout_seconds", timeout)

        if hasattr(self.agent, "set_data"):
            await self.agent.set_data("timeout", timeout)

        response = kwargs.get("response", "")

        if hasattr(self.agent, "store_data"):
            await self.agent.store_data("response", response)

        if hasattr(self.agent, "add_message"):
            await self.agent.add_message("user", "Response recorded.")

        print(f"Response tool executed. Stored response: {response}")

        return Response(message=f"Response recorded: {response}", break_loop=True)

    def before_execution(self, **kwargs):
        pass  # do not add anything to the history or output

    def after_execution(self, response, **kwargs):
        pass  # do not add anything to the history or output
