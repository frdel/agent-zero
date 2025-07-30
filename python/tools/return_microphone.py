from agent import Agent
from python.helpers.tool import Tool, Response
from datetime import datetime, timezone


class ReturnMicrophone(Tool):
    """Tool that allows subordinate agents to return the microphone to superior agents with a message"""

    async def execute(self, message="", **kwargs):
        """
        Return the microphone to the superior agent with a message

        Args:
            message: Message to send back to the superior agent
        """

        # Get superior agent
        superior = self.agent.get_data(Agent.DATA_NAME_SUPERIOR)
        if superior is None:
            return Response(
                message="Error: No superior agent found. Cannot return microphone.",
                break_loop=False
            )

        # Check if this agent currently has the microphone
        microphone_holder = self.agent.get_data("_microphone_holder")
        if microphone_holder != self.agent:
            return Response(
                message="Error: This agent does not currently have the microphone.",
                break_loop=False
            )

        # Clear microphone state - superior gets it back
        self.agent.set_data("_microphone_holder", None)
        superior.set_data("_microphone_holder", None)

        # Add message to shared microphone messages queue (stored in agent0)
        # This allows ALL agents in the conversation to access the messages
        microphone_messages = self.agent.context.agent0.get_data("_microphone_messages") or []
        microphone_messages.append({
            "from_agent": f"A{self.agent.number}",
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self.agent.context.agent0.set_data("_microphone_messages", microphone_messages)

        # Debug logging to verify message storage
        self.agent.context.log.log(
            type="util",
            heading="icon://mic_off Debug: Microphone Message Stored",
            content=f"Stored message from A{self.agent.number}. Total messages in queue: {len(microphone_messages)}",
            kvps={
                "stored_message": message[:100] + ("..." if len(message) > 100 else ""),
                "total_messages": len(microphone_messages)
            }
        )

        return Response(
            message=f"Microphone returned to superior agent A{superior.number} with message: {message}",
            break_loop=True  # End the subordinate's message loop
        )

    def get_log_object(self):
        return self.agent.context.log.log(
            type="tool",
            heading=f"icon://mic_off {self.agent.agent_name}: Returning Microphone",
            content="",
            kvps=self.args,
        )
