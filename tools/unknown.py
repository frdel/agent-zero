from helpers.tool import Tool, Response
from extensions.python.system_prompt._11_tools_prompt import (
    build_prompt as build_tools_prompt
)


class Unknown(Tool):

    async def execute(self, **kwargs):
        tools = await build_tools_prompt(self.agent)
        return Response(
            message=self.agent.read_prompt(
                "fw.tool_not_found.md", tool_name=self.name, tools_prompt=tools
            ),
            break_loop=False,
        )
