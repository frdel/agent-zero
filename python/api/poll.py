from python.helpers.api import ApiHandler
from flask import Request, Response

from agent import AgentContext
from python.api.chat_rename import ChatNames

class Poll(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", None)
        from_no = input.get("log_from", 0)

        # context instance - get or create
        context = self.get_context(ctxid)
        logs = context.log.output(start=from_no)

        # Get chat names instance
        chat_names = ChatNames.get_instance()

        # loop AgentContext._contexts and number unnamed chats
        ctxs = []
        chat_count = 1
        for ctx in AgentContext._contexts.values():
            name = chat_names.get_name(ctx.id)
            # If it's a default name (Chat #xxxxx), replace with sequential number
            if name.startswith("Chat #"):
                name = f"Chat {chat_count}"
            chat_count += 1

            ctxs.append(
                {
                    "id": ctx.id,
                    "no": ctx.no,
                    "name": name,
                    "log_guid": ctx.log.guid,
                    "log_version": len(ctx.log.updates),
                    "log_length": len(ctx.log.logs),
                    "paused": ctx.paused,
                }
            )

        # data from this server
        return {
            "context": context.id,
            "contexts": ctxs,
            "logs": logs,
            "log_guid": context.log.guid,
            "log_version": len(context.log.updates),
            "log_progress": context.log.progress,
            "log_progress_active": context.log.progress_active,
            "paused": context.paused,
        }
