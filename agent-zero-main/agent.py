from typing import Any, Callable, Coroutine
import asyncio


class Agent:
    def __init__(self):
        self.context: dict = {}
        self.agent_name: str = "Agent Zero"
        self.get_data: Callable[[str], Any] = self.retrieve_data
        self.set_data: Callable[[str, Any], None] = self.store_data
        self.read_prompt: str = ""
        self.append_message: Callable[[str], None] = self.add_message
        self.handle_intervention: Callable[[Any], None] = self.process_intervention
        self.generate_response: Callable[[str], Coroutine[Any, Any, str]] = (
            self._generate_response
        )  # Updated type hint
        self.max_tool_response_length: int = 1000  # Added attribute

    def retrieve_data(self, key: str) -> Any:
        return self.context.get(key, None)

    def store_data(self, key: str, value: Any) -> None:
        self.context[key] = value

    def add_message(self, message: str) -> None:
        print(message)

    def process_intervention(self, intervention: Any) -> None:
        # Handle intervention logic
        pass

    async def _generate_response(self, prompt: str) -> str:
        # Implementation to generate a response based on the prompt
        await asyncio.sleep(0.1)  # Simulate async processing
        return "response_text"
