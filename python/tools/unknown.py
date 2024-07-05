from python.helpers.tool import Tool, Response
from python.helpers import files

class Unknown(Tool):
    def execute(self, **kwargs):
        return Response(
                message=files.read_file("prompts/fw.tool_not_found.md",
                                        tool_name=self.name,
                                        tools_prompt=files.read_file("prompts/agent.tools.md")), 
                break_loop=False)

