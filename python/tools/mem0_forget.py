from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings

DEFAULT_THRESHOLD = 0.8

class Mem0Forget(Tool):
    """Forget (delete) memories matching a query or specific IDs.

    Allows targeted cleanup. Supports both mem0 and FAISS backends via Memory
    interface.
    """

    async def execute(
        self,
        query: str = "",
        threshold: float = DEFAULT_THRESHOLD,
        filter: str = "",
        ids: list[str] | None = None,
        **kwargs,
    ):
        db = await Memory.get(self.agent)

        if ids:
            removed_docs = await db.delete_documents_by_ids(ids)
        else:
            if not query:
                return Response(message="⚠️ Provide a query or ids to forget.", break_loop=False)
            removed_docs = await db.delete_documents_by_query(query=query, threshold=threshold, filter=filter)

        if not removed_docs:
            return Response(message="No memories matched your criteria.", break_loop=False)

        msg = self.agent.read_prompt("fw.msg_cleanup.md", count=len(removed_docs))
        return Response(message=msg, break_loop=False)