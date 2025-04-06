from python.helpers import tokens
from python.helpers.api import ApiHandler
from flask import Request, Response


class GetHistory(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", [])
        context = self.get_context(ctxid)
        agent = context.streaming_agent or context.agent0
        history = agent.history.output()
        size = tokens.approximate_tokens(agent.history.output_text())

        return {
            "history": history,
            "tokens": size
        }