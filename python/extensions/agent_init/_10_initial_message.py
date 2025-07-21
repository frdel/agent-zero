import json
from agent import LoopData
from python.helpers.extension import Extension


class InitialMessage(Extension):

    async def execute(self, **kwargs):
        """
        Add an initial greeting message to the chat when agent is initialized.
        This happens when a new chat is created or when chat is reset.
        Only adds the message once per chat session using persisted metadata.
        """

        # Only add initial message for main agent (A0), not subordinate agents
        if self.agent.number != 0:
            return

        # Check if initial message already exists in history
        history_output = self.agent.history.output()
        for msg in history_output:
            if "content" in msg and msg["content"]:
                return  # Initial message already exists, skip

        # Construct the initial message from prompt template
        initial_message = self.agent.read_prompt("fw.initial_message.md")

        # add loop data to agent
        self.agent.loop_data = LoopData(user_message=None)

        # Add the message to history as an AI response
        self.agent.hist_add_ai_response(initial_message)

        # json parse the message, get the tool_args text
        initial_message_json = json.loads(initial_message)
        initial_message_text = initial_message_json.get("tool_args", {}).get("text", "Hello! How can I help you?")

        # Add to log (green bubble) for immediate UI display
        log_item = self.agent.context.log.log(
            type="response",
            heading=f"{self.agent.agent_name}: Welcome",
            content=initial_message_text
        )
        # Mark the log item as finished to clear from status bar
        log_item.update(finished=True)
