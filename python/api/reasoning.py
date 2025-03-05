from python.helpers.api import ApiHandler
from flask import Request, Response
from typing import Any

class Reasoning(ApiHandler):
    async def process(
        self, input: dict[str, Any], request: Request
    ) -> dict[str, Any] | Response:
        # input data
        reasoning = True if input.get("reasoning", False) else False
        ctxid = input.get("context", "")

        # context instance - get or create
        context = self.get_context(ctxid)

        # Set reasoning state on context
        context.reasoning = reasoning

        return {
            "message": "Reasoning enabled." if reasoning else "Reasoning disabled.",
            "reasoning": reasoning,
        }
