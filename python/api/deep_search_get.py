from python.helpers.api import ApiHandler
from flask import Request, Response
from typing import Any, Dict

class DeepSearchGet(ApiHandler):
    async def process(
        self, input: Dict[str, Any], request: Request
    ) -> Dict[str, Any] | Response:
        # Get context ID from input
        ctxid = input.get("context", "")

        # Get context instance
        context = self.get_context(ctxid)

        # Return current deep_search state
        return {
            "deep_search": context.deep_search if hasattr(context, "deep_search") else False,
            "context": context.id
        }
