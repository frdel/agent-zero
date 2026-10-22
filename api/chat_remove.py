from helpers.api import ApiHandler, Input, Output, Request, Response
from agent import AgentContext
from helpers import persist_chat
from helpers.task_scheduler import TaskScheduler


class RemoveChat(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        ctxid = input.get("context", "")
        from helpers.durable import runtime
        owner = runtime.service()
        if owner and getattr(owner, "distributed", False):
            import json
            from helpers.durable.store import ConflictError, StaleRunError, DurableStoreError
            try:
                result = persist_chat.remove_chat(ctxid, request_id=input.get("request_id"), run_id=input.get("run_id"),
                    expected_generation=input.get("expected_generation"), epoch=input.get("epoch"), version=input.get("version"))
                return Response(json.dumps(result), status=202 if result["queued"] else 200, mimetype="application/json")
            except (ConflictError, StaleRunError, persist_chat.SharedDeletionHeld):
                return Response(json.dumps({"error": "Refresh this chat before requesting removal."}), status=409, mimetype="application/json")
            except (ValueError, TypeError, KeyError):
                return Response(json.dumps({"error": "Invalid shared removal request."}), status=400, mimetype="application/json")
            except (DurableStoreError, RuntimeError):
                return Response(json.dumps({"error": "Chat removal needs recovery storage attention."}), status=503, mimetype="application/json")
        try:
            persist_chat.ensure_removal_supported(ctxid)
        except persist_chat.SharedDeletionHeld as exc:
            import json
            return Response(json.dumps({"error": str(exc)}), status=409, mimetype="application/json")

        scheduler = TaskScheduler.get()
        scheduler.cancel_tasks_by_context(ctxid, terminate_thread=True)

        context = AgentContext.use(ctxid)
        if context:
            # stop processing any tasks
            context.reset()

        AgentContext.remove(ctxid)
        persist_chat.remove_chat(ctxid)

        await scheduler.reload()

        tasks = scheduler.get_tasks_by_context_id(ctxid)
        for task in tasks:
            await scheduler.remove_task_by_uuid(task.uuid)

        # Context removal affects global chat/task lists in all tabs.
        from helpers.state_monitor_integration import mark_dirty_all
        mark_dirty_all(reason="api.chat_remove.RemoveChat")

        return {
            "message": "Context removed.",
        }
