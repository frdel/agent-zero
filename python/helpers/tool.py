from abc import abstractmethod
from typing import Any, Union
from python.helpers.print_style import PrintStyle
from python.helpers import files, messages


class Response:
    def __init__(self, message: str, break_loop: bool) -> None:
        self.message = message
        self.break_loop = break_loop


class Tool:

    def __init__(self, agent: Any):
        self.agent = agent
        self.max_output_length = getattr(agent, "max_tool_response_length", 3000)
        self.name = getattr(self, "name", self.__class__.__name__)
        self.args: dict[str, Any] = {}

    async def run(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        self.name = tool_name
        self.args = tool_args
        self.before_execution()
        response = await self.execute(**tool_args)
        self.after_execution(response)

    @abstractmethod
    async def execute(self, **kwargs) -> Response:
        pass

    def before_execution(self, **kwargs):
        handle_intervention = getattr(self.agent, "handle_intervention", None)
        if callable(handle_intervention):
            handle_intervention()
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(
            f"{getattr(self.agent, 'agent_name', 'Agent')}: Using tool '{self.name}':"
        )
        if self.args and isinstance(self.args, dict):
            for key, value in self.args.items():
                PrintStyle(font_color="#85C1E9", bold=True).stream(self.nice_key(key) + ": ")
                PrintStyle(
                    font_color="#85C1E9",
                    padding=isinstance(value, str) and "\n" in value,
                ).stream(str(value))
                PrintStyle().print()

    def after_execution(self, response: Response, **kwargs):
        text = messages.truncate_text(response.message.strip(), self.max_output_length)
        msg_response = files.read_file("./prompts/fw.tool_response.md", tool_name=self.name, tool_response=text)
        handle_intervention = getattr(self.agent, "handle_intervention", None)
        if callable(handle_intervention):
            handle_intervention()
        self.add_message_to_agent(msg_response, human=True)
        PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(
            f"{getattr(self.agent, 'agent_name', 'Agent')}: Response from tool '{self.name}':"
        )
        PrintStyle(font_color="#85C1E9").print(response.message)

    def add_message_to_agent(self, message: str, human: bool = False):
        method = getattr(self.agent, "add_message", None) or getattr(self.agent, "append_message", None)
        if callable(method):
            method(message)
        else:
            print(f"Warning: Unable to add message to agent: {message}")

    @staticmethod
    def nice_key(key: str) -> str:
        words = key.split("_")
        words = [words[0].capitalize()] + [word.lower() for word in words[1:]]
        result = " ".join(words)
        return result
