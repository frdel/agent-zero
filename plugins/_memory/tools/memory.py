import uuid

from helpers.tool import Tool, Response
from helpers.strings import truncate_text
from plugins._memory.helpers.memory import Memory

DEFAULT_THRESHOLD = 0.7
DEFAULT_LIMIT = 10


class MemoryTool(Tool):

    async def execute(self, action="", **kwargs) -> Response:
        action = _normalize_action(action)
        if action == "load":
            return await self._load(**kwargs)
        if action == "save":
            return await self._save(**kwargs)
        if action == "delete":
            return await self._delete(**kwargs)
        if action == "forget":
            return await self._forget(**kwargs)
        return Response(
            message=self.agent.read_prompt("fw.memory.invalid_action.md"),
            break_loop=False,
        )

    async def _load(self, query="", threshold=DEFAULT_THRESHOLD, limit=DEFAULT_LIMIT, filter="", **kwargs) -> Response:
        if threshold is None or threshold == "":
            threshold = DEFAULT_THRESHOLD
        if limit is None or limit == "":
            limit = DEFAULT_LIMIT
        threshold = float(threshold)
        limit = int(limit)

        db = await Memory.get(self.agent)
        docs = await db.search_similarity_threshold(query=query, limit=limit, threshold=threshold, filter=filter)

        if len(docs) == 0:
            result = self.agent.read_prompt("fw.memories_not_found.md", query=query)
        else:
            text = "\n\n".join(Memory.format_docs_plain(docs))
            result = str(text)

        return Response(message=result, break_loop=False)

    async def _save(self, text="", area="", **kwargs) -> Response:
        if not area:
            area = Memory.Area.MAIN.value

        metadata = {"area": area, **kwargs}

        db = await Memory.get(self.agent)
        id = await db.insert_text(text, metadata)

        result = self.agent.read_prompt("fw.memory_saved.md", memory_id=id)
        return Response(message=result, break_loop=False)

    async def _delete(self, ids="", **kwargs) -> Response:
        db = await Memory.get(self.agent)
        ids = [id.strip() for id in ids.split(",") if id.strip()]
        dels = await db.delete_documents_by_ids(ids=ids, cascade=True)

        result = self.agent.read_prompt("fw.memories_deleted.md", memory_count=len(dels))
        return Response(message=result, break_loop=False)

    async def _forget(self, query="", threshold=DEFAULT_THRESHOLD, filter="", **kwargs) -> Response:
        db = await Memory.get(self.agent)
        dels = await db.delete_documents_by_query(
            query=query,
            threshold=threshold,
            filter=filter,
            include_exact=True,
            cascade=True,
        )

        result = self.agent.read_prompt("fw.memories_deleted.md", memory_count=len(dels))
        return Response(message=result, break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="memory",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self):
        action = _normalize_action(self.args.get("action"))
        if action == "save":
            detail = str(self.args.get("text") or "").strip()
            text = f"Saving memory: {truncate_text(detail, 60)}" if detail else "Saving memory"
            return f"icon://bookmark_add {text}"
        if action == "delete":
            detail = str(self.args.get("ids") or "").strip()
            text = f"Deleting memories: {truncate_text(detail, 60)}" if detail else "Deleting memories"
            return f"icon://delete {text}"
        if action == "forget":
            detail = str(self.args.get("query") or "").strip()
            text = f"Forgetting memories: {truncate_text(detail, 60)}" if detail else "Forgetting memories"
            return f"icon://auto_delete {text}"
        if action == "load":
            detail = str(self.args.get("query") or "").strip()
            text = f"Searching memories: {truncate_text(detail, 60)}" if detail else "Searching memories"
            return f"icon://saved_search {text}"
        return "icon://psychology Using memory"


def _normalize_action(action) -> str:
    return str(action or "").strip().lower().replace("-", "_")
