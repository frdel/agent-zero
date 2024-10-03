from python.helpers.tool import Tool, Response
from python.extensions.message_loop_prompts._10_system_prompt import (
    concat_tool_prompts,
)


class Unknown(Tool):
    async def execute(self, **kwargs):
        tools = concat_tool_prompts(self.agent)
        return Response(
            message=self.agent.read_prompt(
                "fw.tool_not_found.md", tool_name=self.name, tools_prompt=tools
            ),
            break_loop=False,
        )
