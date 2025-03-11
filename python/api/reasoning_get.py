from python.helpers.api import ApiHandler
from flask import Request, Response
from typing import Any, Dict

class ReasoningGet(ApiHandler):
    async def process(
        self, input: Dict[str, Any], request: Request
    ) -> Dict[str, Any] | Response:
        # Get context ID from input
        ctxid = input.get("context", "")

        # Get context instance
        context = self.get_context(ctxid)

        # Return current reasoning state
        return {
            "reasoning": context.reasoning if hasattr(context, "reasoning") else False,
            "context": context.id
        }
