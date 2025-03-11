from python.helpers.tool import Tool, Response
from typing import Any, Literal
from python.helpers.print_style import PrintStyle
from models import ModelProvider
from python.helpers import settings


class ReasoningTool(Tool):

    async def execute(self, **kwargs: dict[str, Any]) -> Response:
        if (
            (self.agent.config.chat_model.provider in [ModelProvider.ANTHROPIC, ModelProvider.OPENAI, ModelProvider.OPENROUTER])
            and self.agent.config.chat_model.reasoning
        ):
            reasoning_effort: str = str(kwargs.get("reasoning_effort", "low"))
            if reasoning_effort not in ["low", "medium", "high"]:
                PrintStyle(font_color="orange", padding=True).print(
                    f"Invalid reasoning effort '{reasoning_effort}'. Defaulting to 'low'."
                )
                reasoning_effort = "low"

            set = settings.get_settings()
            chat_model_ctx_length = int(set["chat_model_ctx_length"])
            chat_model_ctx_output = int((1.0 - float(set["chat_model_ctx_history"])) * chat_model_ctx_length)

            self.agent.set_data("chat_model_reasoning_effort", reasoning_effort)
            if reasoning_effort == "low":
                default: int = int(0.25 * chat_model_ctx_output)
                self.agent.set_data("chat_model_reasoning_tokens", min(4000, default))
            elif reasoning_effort == "medium":
                default: int = int(0.5 * chat_model_ctx_output)
                self.agent.set_data("chat_model_reasoning_tokens", min(16000, default))
            elif reasoning_effort == "high":
                default: int = int(0.75 * chat_model_ctx_output)
                self.agent.set_data("chat_model_reasoning_tokens", min(32000, default))

            PrintStyle(font_color="green", bold=True, padding=True).print(
                f"DEBUG: chat_model_ctx_output: {chat_model_ctx_output}, chat_model_ctx_length: {chat_model_ctx_length}, reasoning_effort: {reasoning_effort}, reasoning_tokens: {self.agent.get_data('chat_model_reasoning_tokens')}"
            )

        response = self.agent.read_prompt("fw.reasoning_tool.md", query=kwargs.get("query"))
        return Response(message=response, break_loop=False)
