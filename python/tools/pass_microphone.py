from agent import Agent, UserMessage
from python.helpers.tool import Tool, Response


class PassMicrophone(Tool):
    """Tool that allows superior agents to pass the microphone to subordinate agents"""

    async def execute(self, message="", agent_profile="", **kwargs):
        """
        Pass the microphone to a subordinate agent

        Args:
            message: Message to send to the subordinate agent
            agent_profile: Optional profile for the subordinate agent
        """

        # Ensure we have a subordinate agent
        subordinate = self.agent.get_data(Agent.DATA_NAME_SUBORDINATE)
        if subordinate is None:
            # Create subordinate agent if it doesn't exist
            subordinate = Agent(self.agent.number + 1, self.agent.config, self.agent.context)
            subordinate.set_data(Agent.DATA_NAME_SUPERIOR, self.agent)
            self.agent.set_data(Agent.DATA_NAME_SUBORDINATE, subordinate)
            subordinate.config.profile = agent_profile if agent_profile else ""
        elif agent_profile:
            # Update profile if provided
            subordinate.config.profile = agent_profile

        # Set microphone state - subordinate now has the microphone
        self.agent.set_data("_microphone_holder", subordinate)
        subordinate.set_data("_microphone_holder", subordinate)

        # Initialize microphone messages queue at context level if not exists
        # This allows ALL agents in the conversation to access the messages
        # Store in agent0 (main agent) data for shared access across all agents
        if not self.agent.context.agent0.get_data("_microphone_messages"):
            self.agent.context.agent0.set_data("_microphone_messages", [])

        # Enhanced message with microphone instructions
        microphone_message = (
            f"You now have the microphone. {message}\n\n"
            "When you have completed your analysis/task, use the 'return_microphone' tool "
            "to send your response back to your superior agent. Your response will be "
            "injected into the system prompt of all agents in this conversation."
        )

        # Add user message to subordinate agent
        subordinate.hist_add_user_message(UserMessage(
            message=microphone_message,
            attachments=[]
        ))

        # Run subordinate monologue - they should use return_microphone to respond
        result = await subordinate.monologue()

        # Check if microphone was returned properly
        microphone_holder = self.agent.get_data("_microphone_holder")
        if microphone_holder is None:
            # Microphone was returned properly
            response_message = f"Microphone successfully passed to and returned from subordinate agent A{subordinate.number}."
        else:
            # Microphone was not returned (subordinate didn't use return_microphone tool)
            response_message = (
                f"Microphone passed to subordinate agent A{subordinate.number}, "
                f"but was not returned properly. Direct response: {result}"
            )
            # Reset microphone state
            self.agent.set_data("_microphone_holder", None)

        return Response(
            message=response_message,
            break_loop=False
        )

    def get_log_object(self):
        return self.agent.context.log.log(
            type="tool",
            heading=f"icon://mic {self.agent.agent_name}: Passing Microphone",
            content="",
            kvps=self.args,
        )
