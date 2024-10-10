from agent import Agent
from python.helpers.tool import Tool, Response

class Delegation(Tool):

    async def execute(self, message="", reset="", **kwargs):
        # create subordinate agent using the data object on this agent and set superior agent to his data object
        if self.agent.get_data("subordinate") is None or str(reset).lower().strip() == "true":
            subordinate = Agent(self.agent.number+1, self.agent.config, self.agent.context)
            subordinate.set_data("superior", self.agent)
            self.agent.set_data("subordinate", subordinate) 
        # run subordinate agent message loop
        subordinate: Agent = self.agent.get_data("subordinate")
        return Response( message= await subordinate.monologue(message), break_loop=False)