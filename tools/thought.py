from agent import Agent
from tools.helpers.tool import Tool, Response
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

class Thought(Tool):
    def execute(self):
        return Response(message="", stop_tool_processing=False, break_loop=False)

    def before_execution(self):
        pass

    def after_execution(self, response: Response):
        pass

