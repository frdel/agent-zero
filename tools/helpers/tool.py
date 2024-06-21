from abc import abstractmethod
from typing import TypedDict
from agent import Agent
from tools.helpers.print_style import PrintStyle
from tools.helpers import files

class Response:
    def __init__(self, message: str, break_loop: bool) -> None:
        self.message = message
        self.break_loop = break_loop
    
class Tool:

    def __init__(self, agent: Agent, name: str, args: dict, message: str, **kwargs) -> None:
        self.agent = agent
        self.name = name
        self.args = args
        self.message = message

    @abstractmethod
    def execute(self) -> Response:
        pass

    def before_execution(self):
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(f"{self.agent.name}: Using tool {self.name}:")
        PrintStyle(font_color="#85C1E9").print(self.args)

    def after_execution(self, response: Response):
        msg_response = files.read_file("./prompts/fw.tool_response.md", tool_name=self.name, tool_response=response.message)
        self.agent.append_message(msg_response, human=True)
        PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(f"{self.agent.name}: Response from {self.name}:")
        PrintStyle(font_color="#85C1E9").print(response.message)