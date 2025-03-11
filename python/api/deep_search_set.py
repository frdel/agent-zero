from python.helpers.api import ApiHandler
from flask import Request, Response
from typing import Any

class DeepSearchSet(ApiHandler):
    async def process(
        self, input: dict[str, Any], request: Request
    ) -> dict[str, Any] | Response:
        # input data
        deep_search = True if input.get("deep_search", False) else False
        ctxid = input.get("context", "")

        # context instance - get or create
        context = self.get_context(ctxid)

        # Set deep_search state on context
        context.deep_search = deep_search

        # Return response with context id and state
        return {
            "message": "Deep search enabled." if deep_search else "Deep search disabled.",
            "deep_search": deep_search,
            "context": context.id
        }
