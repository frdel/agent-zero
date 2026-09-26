"""Recover leaked text calls before optional repair or final-answer fallback."""

from __future__ import annotations

import json
from typing import Any

from helpers.extension import Extension
from helpers.leaked_tool_calls import salvage_leaked_tool_call
from helpers.responses_tools import build_responses_function_tools


def _validated_name_map(value: Any) -> dict[str, str] | None:
    if isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(name, str) for key, name in value.items()
    ):
        return value
    return None


class LeakedToolCall(Extension):
    def execute(self, result_data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if not self.agent or not isinstance(result_data, dict):
            return
        if result_data.get("skip_default_processing"):
            return
        llm_result = result_data.get("llm_result")
        # Actual transport tool calls remain authoritative; never execute text
        # alongside them or interfere with provider-native continuation items.
        if getattr(llm_result, "function_calls", None) or getattr(
            llm_result, "builtin_items", None
        ):
            return
        response = getattr(llm_result, "response", None)
        if not isinstance(response, str) or not response:
            return

        is_chat = getattr(llm_result, "mode", None) == "chat_completions"
        name_map = (
            None
            if is_chat
            else _validated_name_map(self.agent.get_data("responses_tool_name_map"))
        )
        result = salvage_leaked_tool_call(
            response,
            offered_tools=name_map.values() if name_map is not None else None,
            tool_name_map=name_map,
        )
        if is_chat and result.detail == "tool_surface_unavailable":
            # Chat turns deliberately build no native schemas. Resolve their
            # policy-filtered prompt/MCP surface only for a complete candidate,
            # using the existing builder instead of a second tool registry.
            try:
                _, current_names = build_responses_function_tools(self.agent)
                name_map = _validated_name_map(current_names)
            except Exception:
                name_map = None
            result = salvage_leaked_tool_call(
                response,
                offered_tools=name_map.values() if name_map is not None else None,
                tool_name_map=name_map,
            )
        if result.status == "clean":
            return

        params = self.agent.loop_data.params_temporary
        params["leaked_tool_call"] = {"status": result.status, "detail": result.detail}
        if result.request is not None:
            llm_result.response = json.dumps(
                result.request, ensure_ascii=False, separators=(",", ":")
            )
            self.agent.context.log.log(
                type="info", content="Recovered a complete leaked tool call."
            )
            return

        # History insertion owns Responses state advancement. Keep the warning
        # static so the existing exact-match counter sees it.
        result_data["skip_default_processing"] = True
        log_item = params.get("log_item_generating")
        self.agent.hist_add_ai_response(
            response, id=log_item.id if log_item else "", llm_result=llm_result
        )
        prompt = (
            "fw.msg_truncated_tool_call.md"
            if result.status == "truncated"
            else "fw.msg_leaked_tool_call.md"
        )
        warning = self.agent.read_prompt(prompt)
        warning_message = self.agent.hist_add_warning(message=warning)
        self.agent.context.log.log(
            type="warning",
            content=f"{self.agent.agent_name}: {warning}",
            id=warning_message.id,
        )
