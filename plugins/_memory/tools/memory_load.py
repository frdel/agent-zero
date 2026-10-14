from helpers import plugins
from helpers.tool import Tool, Response
from plugins._memory.helpers.memory import Memory

DEFAULT_THRESHOLD = 0.7
DEFAULT_LIMIT = 10


class MemoryLoad(Tool):

    async def execute(self, query="", threshold=DEFAULT_THRESHOLD, limit=DEFAULT_LIMIT, filter="", **kwargs):
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
            # optional cross-encoder rerank: reorder by query-document
            # relevance so the most relevant memories are listed first
            set = plugins.get_plugin_config("_memory", self.agent) or {}
            if set.get("memory_recall_rerank_enabled") and len(docs) > 1:
                from plugins._memory.helpers.reranker import rerank_docs

                try:
                    reranked = await rerank_docs(
                        self.agent,
                        query,
                        docs,
                        model_name=set.get("memory_recall_rerank_model", ""),
                    )
                    if reranked is not None:
                        docs = reranked
                except Exception:
                    pass  # keep original order on any rerank failure

            text = "\n\n".join(Memory.format_docs_plain(docs))
            result = str(text)

        return Response(message=result, break_loop=False)
