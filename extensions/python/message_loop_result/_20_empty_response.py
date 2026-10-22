"""Retry completed model turns with neither response nor reasoning."""

from __future__ import annotations

from typing import Any

from helpers.errors import HandledException
from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers.settings import get_settings


STATE_KEY = "_unusable_response_failures"


class EmptyResponse(Extension):
    def execute(self, result_data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if not self.agent or not isinstance(result_data, dict):
            return
        if result_data.get("skip_default_processing"):
            return

        llm_result = result_data.get("llm_result")
        response = getattr(llm_result, "response", "")
        reasoning = getattr(llm_result, "reasoning", "")
        if not isinstance(response, str) or not isinstance(reasoning, str):
            return
        if response.strip():
            return

        if reasoning.strip():
            warning = self.agent.read_prompt("fw.msg_reasoning_only.md")
            warning_message = self.agent.hist_add_warning(message=warning)
            PrintStyle(font_color="orange", padding=True).print(warning)
            self.agent.context.log.log(
                type="warning",
                content=self.agent.read_prompt('fw.msg_reasoning_only_response.md'),
                id=warning_message.id,
            )
            result_data["skip_default_processing"] = True
            return

        warning = self.agent.read_prompt("fw.msg_empty_response.md")
        PrintStyle(font_color="orange", padding=True).print(warning)
        state = self.agent.loop_data.params_persistent
        previous = state.get(STATE_KEY, {})
        previous_iteration = previous.get("iteration") if isinstance(previous, dict) else None
        count = (
            previous.get("count", 0) + 1
            if previous_iteration == self.agent.loop_data.iteration - 1
            else 1
        )
        state[STATE_KEY] = {"iteration": self.agent.loop_data.iteration, "count": count}
        limit = get_settings()["max_consecutive_unusable_responses"]
        if count >= limit:
            stop_message = self.agent.read_prompt(
                "fw.msg_unusable_response_limit.md", limit=limit
            )
            self.agent.context.log.log(type="warning", content=stop_message)
            raise HandledException(stop_message)
        self.agent.context.log.log(
            type="warning",
            content=warning,
        )
        result_data["skip_default_processing"] = True
