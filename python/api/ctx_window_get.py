from python.helpers import tokens
from python.helpers.api import ApiHandler
from flask import Request, Response


class GetCtxWindow(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", [])
        context = self.get_context(ctxid)
        agent = context.streaming_agent or context.agent0
        window = agent.get_data(agent.DATA_NAME_CTX_WINDOW)
        size = tokens.approximate_tokens(window)

        return {"content": window, "tokens": size}
