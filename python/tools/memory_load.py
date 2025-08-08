from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers import settings

DEFAULT_THRESHOLD = 0.7
DEFAULT_LIMIT = 10


class MemoryLoad(Tool):

    async def execute(self, query="", threshold=DEFAULT_THRESHOLD, limit=DEFAULT_LIMIT, filter="", **kwargs):
        db = await Memory.get(self.agent)
        docs = await db.search_similarity_threshold(query=query, limit=limit, threshold=threshold, filter=filter)

        # Format memory results for context
        memory_text = ""
        if docs:
            memory_text = "\n\n".join(Memory.format_docs_plain(docs))

        # Query GraphRAG with memory context for enhanced relevance (if enabled)
        memory_context = {'memories': memory_text} if memory_text else None
        graph_knowledge = ""
        try:
            set = settings.get_settings()
            if set.get("use_graphrag", True):
                graph_knowledge = await self._query_graphrag(query, memory_context)
        except Exception:
            # GraphRAG failure shouldn't break memory loading
            pass

        if len(docs) == 0 and not graph_knowledge:
            result = self.agent.read_prompt("fw.memories_not_found.md", query=query)
        else:
            # Format graph knowledge
            graph_text = ""
            if graph_knowledge:
                graph_text = f"\n\n# Knowledge Graph Insights:\n{graph_knowledge}"

            # Combine results
            result = memory_text + graph_text

        return Response(message=result, break_loop=False)

    async def _query_graphrag(self, query: str, memory_context: dict = None) -> str:
        """Query GraphRAG knowledge graph for additional insights with memory context."""
        try:
            from python.helpers.graphrag_helper import GraphRAGHelper

            # Enhanced query with memory context if available
            if memory_context and (memory_context.get('memories') or memory_context.get('solutions')):
                context_info = []

                if memory_context.get('memories'):
                    context_info.append(f"Related memories found:\n{memory_context['memories'][:500]}...")

                if memory_context.get('solutions'):
                    context_info.append(f"Related solutions found:\n{memory_context['solutions'][:500]}...")

                # Create context-enhanced query
                enhanced_query = f"""Based on the following memory context, provide additional insights from the knowledge graph:

{chr(10).join(context_info)}

Original question: {query}

Focus on entities, relationships, or knowledge that complements the above memories and solutions."""

                # Try the context-enhanced query first
                try:
                    helper = GraphRAGHelper.get_default()
                    result = helper.query_with_memory_context(enhanced_query, memory_context)
                    if result and "No relevant information" not in result:
                        return result
                except Exception:
                    pass  # Fall back to standard queries

            # Fallback to multiple query formulations for better coverage
            queries_to_try = [
                query,  # Original query
                f"What do you know about {query}?",  # More direct
                f"Tell me about entities related to: {query}",  # Entity-focused
            ]

            results = []
            for q in queries_to_try[:2]:  # Limit to 2 queries to avoid too much processing
                try:
                    helper = GraphRAGHelper.get_default()
                    result = helper.query(q)
                    if result and "No relevant information" not in result:
                        results.append(result)
                except Exception:
                    continue

            if results:
                return "\n\n".join(results)
            else:
                # Final fallback to multi-area query
                areas_to_query = ["main"]
                if memory_context and memory_context.get('memories'):
                    areas_to_query.extend(["fragments", "solutions"])  # Add memory areas

                # Remove duplicates while preserving order
                areas_to_query = list(dict.fromkeys(areas_to_query))

                # Query multiple areas and combine results
                results = GraphRAGHelper.query_multi_area(query, areas_to_query, memory_context)

                if results:
                    # Format results from multiple areas
                    return GraphRAGHelper.format_multi_area_results(results)
                else:
                    return ""

        except Exception:
            # GraphRAG query failure shouldn't break memory recall
            return ""
