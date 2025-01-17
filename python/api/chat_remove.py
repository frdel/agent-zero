from python.helpers.api import ApiHandler, Input, Output, Request, Response


from agent import AgentContext
from python.helpers import persist_chat


class RemoveChat(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        ctxid = input.get("context", "")

        # context instance - get or create
        AgentContext.remove(ctxid)
        persist_chat.remove_chat(ctxid)

        return {
            "message": "Context removed.",
        }
