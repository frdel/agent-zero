"""Retry completed model turns that repeat the prior response."""

from __future__ import annotations

from typing import Any

from helpers.extension import Extension
from helpers.print_style import PrintStyle


class RepeatResponse(Extension):
    def execute(self, result_data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if not self.agent or not isinstance(result_data, dict):
            return
        if result_data.get("skip_default_processing"):
            return

        llm_result = result_data.get("llm_result")
        response = getattr(llm_result, "response", "")
        repeat_response = (
            llm_result.repeat_response_text()
            if getattr(llm_result, "function_calls", None) else response
        )
        if not isinstance(repeat_response, str) or repeat_response != self.agent.loop_data.last_response:
            return

        warning = self.agent.read_prompt("fw.msg_repeat.md")
        log_item = self.agent.loop_data.params_temporary.get("log_item_generating")
        assistant_message = self.agent.hist_add_ai_response(
            response,
            id=log_item.id if log_item else "",
            llm_result=llm_result,
        )
        warning_message = self.agent.hist_add_warning(message=warning)
        PrintStyle(font_color="orange", padding=True).print(warning)
        self.agent.context.log.log(
            type="warning",
            content=self.agent.read_prompt('fw.msg_repeat_response.md'),
            id=warning_message.id,
        )
        result_data["skip_default_processing"] = True
