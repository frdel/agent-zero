from python.helpers.api import ApiHandler
from flask import Request, Response

from agent import AgentContext
from python.helpers import persist_chat


class RemoveChat(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", "")

        # context instance - get or create
        AgentContext.remove(ctxid)
        persist_chat.remove_chat(ctxid)

        return {
            "message": "Context removed.",
        }
