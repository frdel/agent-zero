from agent import Agent
from python.helpers import files
from python.helpers.print_style import PrintStyle

from agent import Agent
from python.helpers.tool import Tool, Response
from python.helpers import files
from python.helpers.print_style import PrintStyle
from python.helpers.log import Log

class TaskDone(Tool):

    def execute(self,**kwargs):
        self.agent.set_data("timeout", 0)
        return Response(message=self.args["text"], break_loop=True)

    def before_execution(self, **kwargs):
        self.log = Log(type="response", heading=f"{self.agent.agent_name}: Task done:", content=self.args.get("text", ""))
    
    def after_execution(self, response, **kwargs):
        pass # do add anything to the history or output