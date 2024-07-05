from agent import Agent
from python.helpers import files
from python.helpers.tool import Tool, Response
import memory_tool

class Memorize(Tool):
    def execute(self,**kwargs):

        memory_tool.process_query(self.agent, str(self.args), "save")
        
        return Response(
            message=files.read_file("prompts/fw.memorized.md"),
            break_loop=False,
        )