from helpers.api import ApiHandler, Input, Output, Request, Response


from helpers import persist_chat
from helpers.task_scheduler import TaskScheduler


class Reset(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        ctxid = input.get("context", "")
        from helpers.durable.runtime import service, control
        owner = service()
        if owner and getattr(owner, "distributed", False):
            import json
            from helpers.durable.store import _identity
            if not isinstance(ctxid, str) or not ctxid.strip():
                return Response("An explicit chat identity is required.", status=400)
            try:
                request_id = _identity(input.get("request_id"), "request id")
            except ValueError:
                return Response(json.dumps({"error": "Shared reset requires a stable request ID. No records were reset."}), status=409, mimetype="application/json")
            control(ctxid, "reset", request_id=request_id)
            return {"message": "Shared chat reset recorded. Workers will discard the previous generation.", "reset": True}

        # attempt to stop any scheduler tasks bound to this context
        TaskScheduler.get().cancel_tasks_by_context(ctxid, terminate_thread=True)

        # context instance - get or create
        context = self.use_context(ctxid)
        context.reset()
        persist_chat.save_tmp_chat(context)
        persist_chat.remove_msg_files(ctxid)

        # Reset updates context metadata (log guid/version) and must refresh other tabs' lists.
        from helpers.state_monitor_integration import mark_dirty_all
        mark_dirty_all(reason="api.chat_reset.Reset")

        return {
            "message": "Agent restarted.",
        }
