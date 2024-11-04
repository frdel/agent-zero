from python.helpers.tool import Tool, Response
from python.extensions.message_loop_prompts._10_system_prompt import (
    get_tools_prompt,
)


class Unknown(Tool):
    async def execute(self, **kwargs):
        prompt = self.agent.read_prompt("unknown_tool.md")
        await self.agent.append_message(prompt, human=True)
        return "Unknown tool executed."
