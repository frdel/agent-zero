from python.helpers.api import ApiHandler, Input, Output, Request, Response

from agent import AgentContext
from python.helpers import persist_chat
import os
import shutil
from python.helpers import files

class RemoveChat(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        ctxid = input.get("context", "")

        # Remove context instance
        AgentContext.remove(ctxid)
        
        # Remove chat persistence
        persist_chat.remove_chat(ctxid)
        
        # Remove chat-specific memory and knowledge
        memory_path = files.get_abs_path("memory", "chats", ctxid)
        knowledge_path = files.get_abs_path("knowledge", "chats", ctxid)
        
        if os.path.exists(memory_path):
            shutil.rmtree(memory_path)
        if os.path.exists(knowledge_path):
            shutil.rmtree(knowledge_path)

        return {
            "message": "Context and associated data removed.",
        }