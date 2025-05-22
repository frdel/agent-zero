from agent import Agent, UserMessage
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
        subordinate.hist_add_user_message(UserMessage(message=message, attachments=[]))
        # run subordinate monologue
        result = await subordinate.monologue()
        # result
        return Response(message=result, break_loop=False)
