from python.helpers.api import ApiHandler, Input, Output, Request, Response
from python.helpers import persist_chat


class LoadChats(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        chats = input.get("chats", [])
        if not chats:
            raise Exception("No chats provided")

        from python.helpers.user_management import get_user_manager
        um = get_user_manager()
        current_user = um.get_current_username_safe()
        ctxids = persist_chat.load_json_chats(chats, current_user)

        return {
            "message": "Chats loaded.",
            "ctxids": ctxids,
        }
