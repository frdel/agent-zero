import time

from python.helpers.api import ApiHandler
from flask import Request, Response

from agent import AgentContext

from python.helpers import persist_chat
from python.helpers.task_scheduler import TaskScheduler


class Poll(ApiHandler):

    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", None)
        from_no = input.get("log_from", 0)

        # context instance - get or create
        context = self.get_context(ctxid)

        logs = context.log.output(start=from_no)

        # loop AgentContext._contexts

        # Get a task scheduler instance
        scheduler = TaskScheduler.get()

        # Always reload the scheduler on each poll to ensure we have the latest task state
        await scheduler.reload()

        # loop AgentContext._contexts and number unnamed chats

        ctxs = []
        tasks = []
        processed_contexts = set()  # Track processed context IDs

        all_ctxs = list(AgentContext._contexts.values())
        # First, identify all tasks
        for ctx in all_ctxs:
            # Skip if already processed
            if ctx.id in processed_contexts:
                continue

            # Create the base context data that will be returned
            context_data = {
                "id": ctx.id,
                "name": ctx.name,
                "created_at": ctx.created_at,
                "no": ctx.no,
                "log_guid": ctx.log.guid,
                "log_version": len(ctx.log.updates),
                "log_length": len(ctx.log.logs),
                "paused": ctx.paused,
            }

            # Determine if this is a task by checking if a task with this UUID exists
            is_task = scheduler.get_task_by_uuid(ctx.id) is not None

            if not is_task:
                ctxs.append(context_data)
            else:
                # If this is a task, get task details from the scheduler
                task_details = scheduler.serialize_task(ctx.id)
                if task_details:
                    # Add task details to context_data with the same field names
                    # as used in scheduler endpoints to maintain UI compatibility
                    context_data.update({
                        "uuid": task_details.get("uuid"),
                        "state": task_details.get("state"),
                        "type": task_details.get("type"),
                        "system_prompt": task_details.get("system_prompt"),
                        "prompt": task_details.get("prompt"),
                        "last_run": task_details.get("last_run"),
                        "last_result": task_details.get("last_result"),
                        "attachments": task_details.get("attachments", [])
                    })

                    # Add type-specific fields
                    if task_details.get("type") == "scheduled":
                        context_data["schedule"] = task_details.get("schedule")
                    else:
                        context_data["token"] = task_details.get("token")

                tasks.append(context_data)

            # Mark as processed
            processed_contexts.add(ctx.id)

        # Sort tasks and chats by their creation date, descending
        ctxs.sort(key=lambda x: x["created_at"], reverse=True)
        tasks.sort(key=lambda x: x["created_at"], reverse=True)

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
