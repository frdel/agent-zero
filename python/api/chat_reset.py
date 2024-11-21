from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers import persist_chat

class Reset(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", "")

        # context instance - get or create
        context = self.get_context(ctxid)
        context.reset()
        persist_chat.save_tmp_chat(context)

        return {
            "message": "Agent restarted.",
        }
