from agent import Agent
from tools.helpers.tool import Tool, Response
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

class Delegation(Tool):

    def execute(self):
        # create subordinate agent using the data object on this agent and set superior agent to his data object
        if self.agent.get_data("subordinate") is None or self.args["reset"].lower().strip() == "true":
            subordinate = Agent(system_prompt=self.agent.system_prompt, tools_prompt=self.agent.tools_prompt, number=self.agent.number+1)
            subordinate.set_data("superior", self.agent)
            self.agent.set_data("subordinate", subordinate) 
        # run subordinate agent message loop
        return self.agent.get_data("subordinate").message_loop(self.args["task"])