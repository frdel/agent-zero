"""Retry model turns cut off by the output token limit with a specific warning."""

from __future__ import annotations

from typing import Any

from helpers import extract_tools
from helpers.extension import Extension
from helpers.print_style import PrintStyle


class TruncatedResponse(Extension):
    def execute(self, result_data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if not self.agent or not isinstance(result_data, dict):
            return
        if result_data.get("skip_default_processing"):
            return

        llm_result = result_data.get("llm_result")
        if not getattr(llm_result, "truncated", False):
            return
        if getattr(llm_result, "function_calls", None):
            return
        response = getattr(llm_result, "response", "")
        if isinstance(response, str) and extract_tools.extract_tool_request(response):
            return

        # Name truncation as the cause instead of the generic misformat warning.
        warning = self.agent.read_prompt("fw.msg_output_limit.md")
        warning_message = self.agent.hist_add_warning(message=warning)
        notice = self.agent.read_prompt(
            "fw.msg_output_limit_response.md",
            finish_reason=getattr(llm_result, "finish_reason", ""),
        )
        PrintStyle(font_color="orange", padding=True).print(notice)
        self.agent.context.log.log(
            type="warning",
            content=f"{self.agent.agent_name}: {notice}",
            id=warning_message.id,
        )
        result_data["skip_default_processing"] = True
