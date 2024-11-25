from agent import Agent
from python.helpers.tool import Tool, Response


class Delegation(Tool):

    async def execute(self, message="", reset="", **kwargs):
        # create subordinate agent using the data object on this agent and set superior agent to his data object
        if (
            self.agent.get_data(Agent.DATA_NAME_SUBORDINATE) is None
            or str(reset).lower().strip() == "true"
        ):
            sub = Agent(
                self.agent.number + 1, self.agent.config, self.agent.context
            )
            sub.set_data(Agent.DATA_NAME_SUPERIOR, self.agent)
            self.agent.set_data(Agent.DATA_NAME_SUBORDINATE, sub)

        # add user message to subordinate agent
        subordinate: Agent = self.agent.get_data(Agent.DATA_NAME_SUBORDINATE)
        template = self.agent.read_prompt("fw.call_subordinate.md", message=message)
        await subordinate.hist_add_user_message(template)
        # run subordinate monologue
        result = await subordinate.monologue()
        # result
        return Response(message=result, break_loop=False)
