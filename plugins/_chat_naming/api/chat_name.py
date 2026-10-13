from __future__ import annotations

from agent import AgentContext
from helpers.api import ApiHandler, Input, Output, Request, Response
from helpers.persist_chat import save_tmp_chat
from helpers.state_monitor_integration import mark_dirty_all
from helpers.task_scheduler import TaskScheduler
from plugins._chat_naming.helpers import naming


class ChatName(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        del request
        action = str(input.get("action", "get") or "get").strip().lower()
        kind = str(input.get("kind", "chat") or "chat").strip().lower()
        item_id = str(input.get("item_id", "") or "").strip()
        if kind not in {"chat", "task"}:
            return Response("Invalid row kind.", 400)
        if not item_id:
            return Response("Missing chat or task ID.", 400)

        context = AgentContext.get(item_id)
        if not context:
            return Response("Chat context not found.", 404)

        try:
            if action == "get":
                current_name = await self._current_name(kind, item_id, context.name or "")
                return {"ok": True, "name": current_name}
            if action == "generate":
                current_name = await self._current_name(kind, item_id, context.name or "")
                name = await naming.generate_name(
                    context.agent0,
                    current_name=current_name,
                )
                return {"ok": True, "name": name}
            if action == "save":
                name = naming.normalize_manual_name(input.get("name", ""))
                if kind == "task":
                    await self._save_task_name(item_id, name)
                    context.set_data(naming.MANUAL_NAME_KEY, True)
                    context.name = name
                    save_tmp_chat(context)
                    mark_dirty_all(reason="plugins._chat_naming.save_task_name")
                else:
                    context.set_data(naming.MANUAL_NAME_KEY, True)
                    naming.save_context_name(context.agent0, name)
                return {"ok": True, "name": name}
            return Response(f"Unknown action: {action}", 400)
        except ValueError as error:
            return Response(str(error), 400)
        except Exception as error:
            return Response(str(error), 500)

    async def _current_name(self, kind: str, item_id: str, fallback: str) -> str:
        if kind != "task":
            return fallback
        scheduler = TaskScheduler.get()
        await scheduler.reload()
        task = scheduler.get_task_by_uuid(item_id)
        if not task:
            raise ValueError("Scheduled task not found.")
        return str(task.name or fallback)

    async def _save_task_name(self, item_id: str, name: str) -> None:
        scheduler = TaskScheduler.get()
        await scheduler.reload()
        task = await scheduler.update_task(item_id, name=name)
        if not task:
            raise ValueError("Scheduled task not found.")
