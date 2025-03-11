from python.helpers.api import ApiHandler
from flask import Request, Response
from typing import Any

class ReasoningSet(ApiHandler):
    async def process(
        self, input: dict[str, Any], request: Request
    ) -> dict[str, Any] | Response:
        # input data
        reasoning = input.get("reasoning", "auto")
        if isinstance(reasoning, bool):
            # Handle legacy boolean input
            reasoning = "on" if reasoning else "off"
        elif reasoning not in ["off", "on", "auto"]:
            reasoning = "auto"
        ctxid = input.get("context", "")

        # context instance - get or create
        context = self.get_context(ctxid)

        # Set reasoning state on context
        context.reasoning = reasoning

        # Return response with context id and state
        state_messages = {
            "off": "Reasoning set to OFF",
            "on": "Reasoning set to ON",
            "auto": "Reasoning set to AUTO (dynamic choice by model)"
        }
        return {
            "message": state_messages[reasoning],
            "reasoning": reasoning,
            "context": context.id
        }
