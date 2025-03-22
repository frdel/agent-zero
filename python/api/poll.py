from python.helpers.api import ApiHandler
from flask import Request, Response

from agent import AgentContext

from python.helpers import persist_chat


class Poll(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", None)
        from_no = input.get("log_from", 0)

        # context instance - get or create
        context = self.get_context(ctxid)

        logs = context.log.output(start=from_no)

        # loop AgentContext._contexts
        ctxs = []
        tasks = []
        processed_contexts = set()  # Track processed context IDs

        # First, identify all tasks
        for ctx in AgentContext._contexts.values():
            # Skip if already processed
            if ctx.id in processed_contexts:
                continue

            context_data = {
                "id": ctx.id,
                "name": ctx.name,
                "no": ctx.no,
                "log_guid": ctx.log.guid,
                "log_version": len(ctx.log.updates),
                "log_length": len(ctx.log.logs),
                "paused": ctx.paused,
            }

            # Determine if this is a task using multiple methods
            ctx_path = persist_chat.get_chat_folder_path(ctx.id)
            is_task = (ctx_path and persist_chat.TASKS_FOLDER in ctx_path)

            # Add to the appropriate list
            if is_task:
                tasks.append(context_data)
            else:
                ctxs.append(context_data)

            # Mark as processed
            processed_contexts.add(ctx.id)

        # data from this server
        return {
            "context": context.id,
            "contexts": ctxs,
            "tasks": tasks,
            "logs": logs,
            "log_guid": context.log.guid,
            "log_version": len(context.log.updates),
            "log_progress": context.log.progress,
            "log_progress_active": context.log.progress_active,
            "paused": context.paused,
        }
