"""Recover leaked text calls before optional repair or final-answer fallback."""

from __future__ import annotations

import json
from typing import Any

from helpers.extension import Extension
from helpers.extract_tools import extract_leaked_tool_request, normalize_tool_request
from helpers.responses_tools import build_responses_function_tools, original_tool_name


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

        status, request = extract_leaked_tool_request(response)
        if request is not None:
            try:
                if getattr(llm_result, "mode", None) == "chat_completions":
                    _, name_map = build_responses_function_tools(self.agent)
                else:
                    name_map = self.agent.get_data("responses_tool_name_map")
                if not isinstance(name_map, dict) or not all(
                    isinstance(key, str) and isinstance(name, str)
                    for key, name in name_map.items()
                ):
                    raise ValueError("Tool surface unavailable")
                request["tool_name"] = original_tool_name(request["tool_name"], name_map)
                name, args = normalize_tool_request(request)
                name = original_tool_name(name, name_map)
                if name not in name_map.values():
                    raise ValueError("Tool not offered")
                request = {"tool_name": name, "tool_args": args}
            except Exception:
                status, request = "rejected", None
        if status == "clean":
            return
        params = self.agent.loop_data.params_temporary
        if request is not None:
            llm_result.response = json.dumps(
                request, ensure_ascii=False, separators=(",", ":")
            )
            params["leaked_tool_call"] = "call"
            self.agent.context.log.log(
                type="info", content="Recovered a complete leaked tool call."
            )
            return
        # Provider-reported truncation retains its existing warning and retry owner.
        if getattr(llm_result, "truncated", False):
            return
        params["leaked_tool_call"] = status
        if status == "quoted":
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
            if status == "truncated"
            else "fw.msg_leaked_tool_call.md"
        )
        warning = self.agent.read_prompt(prompt)
        warning_message = self.agent.hist_add_warning(message=warning)
        self.agent.context.log.log(
            type="warning",
            content=f"{self.agent.agent_name}: {warning}",
            id=warning_message.id,
        )
