from python.helpers.api import ApiHandler, Input, Output, Request, Response

from python.helpers import tokens


class GetCtxWindow(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        ctxid = input.get("context", [])
        context = self.get_context(ctxid)
        agent = context.streaming_agent or context.agent0
        window = agent.get_data(agent.DATA_NAME_CTX_WINDOW)
        size = tokens.approximate_tokens(window)

        return {"content": window, "tokens": size}
