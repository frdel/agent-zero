from typing import Any

from helpers import extract_tools
from helpers.extension import Extension


class LogPlainResponses(Extension):
    def execute(self, data: dict[str, Any] | None = None, **kwargs):
        if not self.agent or not isinstance(data, dict):
            return

        call_kwargs = data.get("kwargs")
        if not isinstance(call_kwargs, dict):
            call_kwargs = {}

        llm_result = call_kwargs.get("llm_result")
        if getattr(llm_result, "mode", "") != "responses" or getattr(llm_result, "function_calls", None):
            return

        message = call_kwargs.get("message")
        call_args = data.get("args")
        if message is None and isinstance(call_args, tuple) and len(call_args) > 1:
            message = call_args[1]
        if not isinstance(message, str) or not message:
            return
        if (
            extract_tools.extract_tool_request(message) is not None
            or extract_tools.is_misformatted_tool_request(message)
        ):
            return

        params = getattr(getattr(self.agent, "loop_data", None), "params_temporary", None)
        if not isinstance(params, dict) or "log_item_response" in params:
            return
        if params.get("leaked_tool_call") in {"rejected", "truncated"}:
            return

        log_item = params.get("log_item_generating")
        if log_item is None:
            return

        params["log_item_response"] = log_item
        log_item.update(
            type="response",
            heading="",
            content=message,
            finished=True,
            update_progress="none",
        )
