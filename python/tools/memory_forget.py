from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.tools.memory_load import DEFAULT_THRESHOLD
from python.helpers import settings


class MemoryForget(Tool):

    async def execute(self, query="", threshold=DEFAULT_THRESHOLD, filter="", **kwargs):
        db = await Memory.get(self.agent)
        dels = await db.delete_documents_by_query(query=query, threshold=threshold, filter=filter)

        # Delete corresponding data from GraphRAG
        await self._delete_from_graphrag(dels, query)

        result = self.agent.read_prompt("fw.memories_deleted.md", memory_count=len(dels))
        return Response(message=result, break_loop=False)

    async def _delete_from_graphrag(self, deleted_docs, query):
        """Delete entities from GraphRAG based on deleted memory documents and query."""
        try:
            # Delete from GraphRAG if enabled
            set = settings.get_settings()
            if set.get("use_graphrag", True):
                from python.helpers.graphrag_helper import GraphRAGHelper
                # Use the original query for GraphRAG deletion
                helper = GraphRAGHelper.get_default()
                helper.delete_knowledge(query)

        except Exception:
            # GraphRAG deletion failure shouldn't break memory deletion
            pass
