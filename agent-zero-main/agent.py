from typing import Any, Callable, Coroutine
import asyncio
from initialize import AgentConfig

class Agent:
    def __init__(self):
        self.context: dict = {}
        self.agent_name: str = "Agent Zero"
        self.read_prompt: str = ""
        self.generate_response: Callable[[str], Coroutine[Any, Any, str]] = self._generate_response
        self.max_tool_response_length: int = 1000
        self.config: AgentConfig = AgentConfig()
        self.messages: list = []
        self.data: dict = {}
        self.chat_model: Any = None
        self.utility_model: Any = None
        self.embeddings_model: Any = None
        self.update_models()

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

    async def _generate_response(self, prompt: str) -> str:
        # Implementation to generate a response based on the prompt
        await asyncio.sleep(0.1)  # Simulate async processing
        return "response_text"

    def update_models(self) -> None:
        # Update the agent's models from the config
        self.chat_model = getattr(self.config, 'chat_model', None)
        self.utility_model = getattr(self.config, 'utility_model', None)
        self.embeddings_model = getattr(self.config, 'embeddings_model', None)
