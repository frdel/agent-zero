from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers import persist_chat

class LoadChats(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        chats = input.get("chats", [])
        if not chats:
            raise Exception("No chats provided")

        ctxids = persist_chat.load_json_chats(chats)

        return {
            "message": "Chats loaded.",
            "ctxids": ctxids,
        }
