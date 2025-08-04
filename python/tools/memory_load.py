from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response

DEFAULT_THRESHOLD = 0.7
DEFAULT_LIMIT = 10


class MemoryLoad(Tool):

    async def execute(self, query="", threshold=DEFAULT_THRESHOLD, limit=DEFAULT_LIMIT, filter="", **kwargs):
        db = await Memory.get(self.agent)
        docs = await db.search_similarity_threshold(query=query, limit=limit, threshold=threshold, filter=filter)

        # Query GraphRAG for additional insights
        graph_knowledge = await self._query_graphrag(query)

        if len(docs) == 0 and not graph_knowledge:
            result = self.agent.read_prompt("fw.memories_not_found.md", query=query)
        else:
            # Format memory results
            memory_text = ""
            if docs:
                memory_text = "\n\n".join(Memory.format_docs_plain(docs))

            # Format graph knowledge
            graph_text = ""
            if graph_knowledge:
                graph_text = f"\n\n# Knowledge Graph Insights:\n{graph_knowledge}"

            # Combine results
            result = memory_text + graph_text

        return Response(message=result, break_loop=False)

    async def _query_graphrag(self, query: str) -> str:
        """Query GraphRAG knowledge graph for additional insights."""
        try:
            from python.helpers.graphrag_helper import GraphRAGHelper

            # Get GraphRAG helper and query
            helper = GraphRAGHelper.get_default()

            # Try enhanced correction first, then fallback to standard queries
            try:
                # Try enhanced correction if available
                if hasattr(helper, 'query_with_enhanced_correction'):
                    result = helper.query_with_enhanced_correction(query)
                    if result and "No relevant information" not in result and result.strip():
                        return result
            except Exception:
                pass

            # Fallback to multiple query formulations
            queries_to_try = [
                query,  # Original query
                f"What do you know about {query}?",  # More direct
                f"Tell me about entities related to: {query}",  # Entity-focused
            ]

            results = []
            for q in queries_to_try[:2]:  # Limit to 2 queries to avoid too much processing
                try:
                    result = helper.query(q)
                    if result and "No relevant information" not in result and result.strip():
                        results.append(result)
                except Exception:
                    continue

            if results:
                # Combine and deduplicate results
                combined_result = "\n\n".join(results)
                return combined_result
            else:
                return ""

        except Exception:
            # GraphRAG query failure shouldn't break memory recall
            return ""
