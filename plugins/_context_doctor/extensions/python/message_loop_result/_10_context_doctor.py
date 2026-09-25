"""Repair model output and refresh its log details before default processing."""

from __future__ import annotations

import json
from typing import Any, override

from helpers import extract_tools
from helpers.extension import Extension
from helpers.plugins import get_plugin_config
from helpers.print_style import PrintStyle
from plugins._context_doctor.helpers.context_doctor import (
    looks_like_tool_call,
    transform_response,
    update_log_item,
)


class ContextDoctor(Extension):
    @override
    def execute(self, result_data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if not self.agent or not isinstance(result_data, dict):
            return
        if result_data.get("skip_default_processing"):
            return

        # Extract LLM response
        llm_result = result_data.get("llm_result")
        # Canonical calls already belong to the agent's policy-gated dispatcher.
        if getattr(llm_result, "function_calls", None):
            return
        response = getattr(llm_result, "response", None)
        if not isinstance(response, str) or not response.strip():
            return

        # Repair response before default processing
        config = get_plugin_config("_context_doctor", agent=self.agent) or {}
        transformed = transform_response(
            response,
            suppress_xml=config.get("suppress_xml", True),
            split_thoughts=config.get("split_thoughts", True),
        )
        is_tool_call = looks_like_tool_call(response, transformed)
        if (
            getattr(llm_result, "mode", None) == "responses"
            and not is_tool_call
            and not extract_tools.is_misformatted_tool_request(response)
        ):
            return  # Core dispatches Responses output text through the response tool.
        llm_result.response = transformed

        # Treat as raw-text fallback when no usable tool call was extracted
        if not is_tool_call:
            # Manually add ai response and warnings
            log_item = self.agent.loop_data.params_temporary.get("log_item_generating")
            self.agent.hist_add_ai_response(
                transformed,
                id=log_item.id if log_item else "",
                llm_result=llm_result,
            )
            if log_item is not None:
                update_log_item(
                    self.agent,
                    log_item,
                    transformed,
                    update_log=config.get("update_log", False),
                    raw_response=response,
                )

            warning = self.agent.read_prompt("fw.msg_thoughts_fallback.md")
            warning_message = self.agent.hist_add_warning(message=warning)
            PrintStyle(font_color="orange", padding=True).print(warning)
            self.agent.context.log.log(
                type="warning",
                content=f"{self.agent.agent_name}: {self.agent.read_prompt('fw.msg_thoughts_fallback_response.md')}",
                id=warning_message.id,
            )
            result_data["skip_default_processing"] = True
            return

        # Suppressed XML does not update the generating log
        params = getattr(
            getattr(self.agent, "loop_data", None), "params_temporary", None
        )
        if not isinstance(params, dict) or transformed == "{}":
            return

        # Refresh log item
        log_item = params.get("log_item_generating")
        if log_item is not None:
            update_log_item(
                self.agent,
                log_item,
                transformed,
                update_log=config.get("update_log", False),
                raw_response=response,
            )

        # Extract final text from a response tool call
        try:
            parsed = json.loads(transformed)
            tool_args = parsed.get("tool_args", {}) if isinstance(parsed, dict) else {}
            response_text = (
                tool_args.get("text") if parsed.get("tool_name") == "response" else None
            )
        except (AttributeError, TypeError, ValueError):
            response_text = None
        if not isinstance(response_text, str) or not response_text.strip():
            return

        # Create a response log item when streaming did not create one
        response_item = params.get("log_item_response")
        if response_item is None and log_item is not None:
            response_item = self.agent.context.log.log(
                type="response",
                heading=f"icon://chat {self.agent.agent_name}: Responding",
                id=getattr(log_item, "id", ""),
            )
            params["log_item_response"] = response_item
        if response_item is not None:
            response_item.update(content=response_text)
