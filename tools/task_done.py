from agent import Agent
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

from agent import Agent
from tools.helpers.tool import Tool, Response
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

class TaskDone(Tool):

    def execute(self,**kwargs):
        # superior = self.agent.get_data("superior")
        # if superior:
        self.agent.set_data("timeout", 0)
        return Response(message=self.args["text"], break_loop=True)
        # else:

    def after_execution(self, response, **kwargs):
        pass # do add anything to the history or output