from abc import abstractmethod
from dataclasses import dataclass

from agent import Agent, LoopData
from python.helpers.print_style import PrintStyle
from python.helpers.strings import sanitize_string
from python.helpers.secrets import SecretsManager

@dataclass
class Response:
    message:str
    break_loop: bool

class Tool:

    def __init__(self, agent: Agent, name: str, method: str | None, args: dict[str,str], message: str, loop_data: LoopData | None, **kwargs) -> None:
        self.agent = agent
        self.name = name
        self.method = method
        self.args = args
        self.loop_data = loop_data
        self.message = message

    @abstractmethod
    async def execute(self,**kwargs) -> Response:
        pass

    async def before_execution(self, **kwargs):
        # Replace secret placeholders in args
        self.replace_secrets_in_args()

        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(f"{self.agent.agent_name}: Using tool '{self.name}'")
        self.log = self.get_log_object()
        if self.args and isinstance(self.args, dict):
            for key, value in self.args.items():
                PrintStyle(font_color="#85C1E9", bold=True).stream(self.nice_key(key)+": ")
                # Mask secrets in displayed value
                display_value = SecretsManager.get_instance().mask_values(str(value))
                PrintStyle(font_color="#85C1E9", padding=isinstance(value,str) and "\n" in value).stream(display_value)
                PrintStyle().print()

    async def after_execution(self, response: Response, **kwargs):
        text = sanitize_string(response.message.strip())
        # Mask secrets in response before adding to history
        masked_text = SecretsManager.get_instance().mask_values(text)
        self.agent.hist_add_tool_result(self.name, masked_text)
        PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(f"{self.agent.agent_name}: Response from tool '{self.name}'")
        PrintStyle(font_color="#85C1E9").print(masked_text)
        self.log.update(content=masked_text)

    def get_log_object(self):
        if self.method:
            heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}:{self.method}'"
        else:
            heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}'"
        return self.agent.context.log.log(type="tool", heading=heading, content="", kvps=self.args)

    def nice_key(self, key:str):
        words = key.split('_')
        words = [words[0].capitalize()] + [word.lower() for word in words[1:]]
        result = ' '.join(words)
        return result


    def replace_secrets_in_args(self):
        """Replace secret placeholders in tool arguments with actual values"""
        if not self.args or not isinstance(self.args, dict):
            return

        secrets_manager = SecretsManager.get_instance()
        for key, value in self.args.items():
            if isinstance(value, str):
                self.args[key] = secrets_manager.replace_placeholders(value)
