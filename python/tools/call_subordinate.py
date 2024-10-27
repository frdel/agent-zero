from agent import Agent
from python.helpers.tool import Tool, Response

class Delegation(Tool):
    async def execute(self, message="", reset="", role="", **kwargs):
        # create subordinate agent using the data object on this agent and set superior agent to his data object
        if self.agent.get_data("subordinate") is None or str(reset).lower().strip() == "true":
            # Create new subordinate with specified role
            subordinate = Agent(
                number=self.agent.number + 1,
                config=self.agent.config,
                context=self.agent.context,
                role=role  # Pass through the role argument
            )
            subordinate.set_data("superior", self.agent)
            self.agent.set_data("subordinate", subordinate)

        # run subordinate agent message loop
        subordinate: Agent = self.agent.get_data("subordinate")
        return Response(message=await subordinate.monologue(message), break_loop=False)
