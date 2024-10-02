import asyncio
from typing import Any

from initialize import AgentConfig


class Agent:
    def __init__(self, number: int, config: AgentConfig):
        self.context: dict = {}
        self.agent_name: str = f"Agent {number}"
        self.read_prompt: str = ""
        self.config: AgentConfig = config
        self.messages: list = []
        self.data: dict = {}
        self.chat_model: Any = config.chat_model
        self.utility_model: Any = config.utility_model
        self.embeddings_model: Any = config.embeddings_model

    def retrieve_data(self, key: str) -> Any:
        return self.context.get(key, None)

    def store_data(self, key: str, value: Any) -> None:
        self.context[key] = value

    def get_data(self, key: str) -> Any:
        return self.data.get(key)

    def set_data(self, key: str, value: Any) -> None:
        self.data[key] = value

    def add_message(self, message: str) -> None:
        print(message)
        self.messages.append(message)

    def append_message(self, message: str) -> None:
        self.messages.append(message)

    def process_intervention(self, intervention: Any) -> None:
        # Handle intervention logic
        pass

    def handle_intervention(self, message: Any) -> None:
        # Logic to handle intervention
        pass

    async def generate_response(self, prompt: str) -> str:
        try:
            if hasattr(self.chat_model, "agenerate"):
                response = await self.chat_model.agenerate([prompt])
                return str(response.generations[0][0].text)
            elif hasattr(self.chat_model, "generate"):
                response = self.chat_model.generate([prompt])
                return str(response.generations[0][0].text)
            else:
                raise AttributeError("Chat model does not have 'generate' or 'agenerate' method")
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return f"Error: {str(e)}"


if __name__ == "__main__":
    # This is just for testing purposes
    config = AgentConfig()
    agent = Agent(1, config)
    asyncio.run(agent.generate_response("Hello, how are you?"))
