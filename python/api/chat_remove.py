from python.helpers.api import ApiHandler, Input, Output, Request, Response


from agent import AgentContext
from python.helpers import persist_chat
from python.api.chat_rename import ChatNames


class RemoveChat(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        ctxid = input.get("context", "")

        # Remove from agent contexts and persisted chats
        AgentContext.remove(ctxid)
        persist_chat.remove_chat(ctxid)

        # Remove the chat name mapping
        chat_names = ChatNames.get_instance()
        chat_names.remove_chat(ctxid)

        return {
            "message": "Context removed.",
        }
