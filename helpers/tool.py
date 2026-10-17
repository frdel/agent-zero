from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from agent import Agent, LoopData
from helpers.extension import call_extensions_async
from helpers.print_style import PrintStyle
from helpers.strings import sanitize_string


@dataclass
class Response:
    message:str
    break_loop: bool
    additional: dict[str, Any] | None = None

def coerce_bool(value: Any, default: bool) -> bool:
    """Coerce a tool argument to bool: booleans pass, common true/false strings map, unknown values fall back to truthiness."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)

class Tool:

    def __init__(self, agent: Agent, name: str, method: str | None, args: dict[str,str], message: str, loop_data: LoopData | None, **kwargs) -> None:
        self.agent = agent
        self.name = name
        self.method = method
        self.args = args
        self.loop_data = loop_data
        self.message = message
        self.progress: str = ""

    @abstractmethod
    async def execute(self,**kwargs) -> Response:
        pass

    async def set_progress(self, content: str | None):
        ctx = {"content": content or ""}
        await call_extensions_async("tool_output_update", self.agent, ctx=ctx)
        self.progress = ctx["content"]

    def add_progress(self, content: str | None):
        if not content:
            return
        self.progress += content

    async def before_execution(self, **kwargs):
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(f"{self.agent.agent_name}: Using tool '{self.name}'")
        self.log = self.get_log_object()
        if self.args and isinstance(self.args, dict):
            for key, value in self.args.items():
                ctx = {"content": str(value) if not isinstance(value, str) else value}
                await call_extensions_async("tool_output_update", self.agent, ctx=ctx)
                display_value = ctx["content"]
                PrintStyle(font_color="#85C1E9", bold=True).stream(self.nice_key(key)+": ")
                PrintStyle(font_color="#85C1E9", padding=isinstance(value,str) and "\n" in value).stream(display_value)
                PrintStyle().print()

    async def after_execution(self, response: Response, **kwargs):
        text = sanitize_string(response.message.strip())
        self.agent.hist_add_tool_result(self.name, text, id=self.log.id, **(response.additional or {}))
        PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(f"{self.agent.agent_name}: Response from tool '{self.name}'")
        PrintStyle(font_color="#85C1E9").print(text)
        self.log.update(content=text)

    def get_log_object(self):
        import uuid
        pre_id = str(uuid.uuid4())
        if self.method:
            heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}:{self.method}'"
        else:
            heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}'"
        return self.agent.context.log.log(type="tool", heading=heading, content="", kvps=self.args, _tool_name=self.name, id=pre_id)

    def nice_key(self, key:str):
        words = key.split('_')
        words = [words[0].capitalize()] + [word.lower() for word in words[1:]]
        result = ' '.join(words)
        return result
