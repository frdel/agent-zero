from abc import abstractmethod
from typing import TypedDict
from agent import Agent
from tools.helpers.print_style import PrintStyle
from tools.helpers import files

class Response:
    def __init__(self, message: str, stop_tool_processing: bool, break_loop: bool) -> None:
        self.message = message
        self.stop_tool_processing = stop_tool_processing
        self.break_loop = break_loop
    
class Tool:

    def __init__(self, agent: Agent, name: str, content: str, args: dict, message: str, tools: list['Tool'], **kwargs) -> None:
        self.agent = agent
        self.name = name
        self.content = content
        self.args = args
        self.message = message
        self.tools = tools

    @abstractmethod
    def execute(self) -> Response:
        pass

    def before_execution(self):
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(f"{self.agent.name}: Using tool {self.name}:")
        PrintStyle(font_color="#85C1E9").print(self.args, self.content, sep="\n") if self.args else PrintStyle(font_color="#85C1E9").print(self.content)

    def after_execution(self, response: Response):
        msg_response = files.read_file("./prompts/fw.tool_response.md", tool_name=self.name, tool_response=response.message)
        self.agent.append_message(msg_response, human=True)
        PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(f"{self.agent.name}: Response from {self.name}:")
        PrintStyle(font_color="#85C1E9").print(response.message)