"""
Extension that injects microphone messages from subordinate agents into ALL agents' context.
This runs during message_loop_prompts_before to ensure microphone messages are included in the system prompt
for any agent in the conversation.
"""

from python.helpers.extension import Extension
from agent import LoopData


class MicrophoneInjection(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """
        Inject microphone messages from subordinate agents into extras_temporary for ALL agents

        Args:
            loop_data: The loop data containing extras_temporary
            **kwargs: Additional extension arguments
        """

        # Check if there are any microphone messages waiting in the shared context
        # Messages are stored in agent0 (main agent) for shared access across all agents
        microphone_messages = self.agent.context.agent0.get_data("_microphone_messages")

        # Debug logging to show extension is running
        message_count = len(microphone_messages) if microphone_messages else 0
        self.agent.context.log.log(
            type="util",
            heading="icon://mic Debug: Microphone Extension Called",
            content=f"Microphone injection extension called for {self.agent.agent_name}. Found {message_count} messages.",
            kvps={
                "agent": self.agent.agent_name,
                "message_count": message_count,
                "messages_exist": bool(microphone_messages and len(microphone_messages) > 0)
            }
        )

        if microphone_messages and len(microphone_messages) > 0:
            # Build the microphone content
            microphone_content = "## Microphone Messages from Subordinate Agents\n\n"

            for msg in microphone_messages:
                microphone_content += f"**From Agent {msg['from_agent']}** (at {msg['timestamp']}):\n"
                microphone_content += f"{msg['message']}\n\n"

            microphone_content += "---\n"
            microphone_content += "Note: These are direct communications from subordinate agents who had the microphone. "
            microphone_content += "All agents in this conversation can see these messages. "
            microphone_content += "Consider their input as you formulate your response."

            # Add to extras_temporary so it gets injected into the system prompt
            loop_data.extras_temporary["microphone_messages"] = microphone_content

            # Clear the microphone messages queue after injection (only for agent0 to avoid duplicates)
            if self.agent == self.agent.context.agent0:
                self.agent.context.agent0.set_data("_microphone_messages", [])

            # Log the microphone injection
            self.agent.context.log.log(
                type="util",
                heading=f"icon://mic Microphone Messages Injected for {self.agent.agent_name}",
                content=f"Injected {len(microphone_messages)} microphone messages from subordinate agents",
                kvps={
                    "message_count": len(microphone_messages),
                    "injected_for_agent": self.agent.agent_name
                }
            )
