from python.helpers.api import ApiHandler, Request, Response
from python.helpers.memory import Memory


class MemoryDashboard(ApiHandler):

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            # Get filter parameters
            area_filter = input.get("area", "")  # Filter by memory area (MAIN, FRAGMENTS, SOLUTIONS, INSTRUMENTS)
            search_query = input.get("search", "")  # Full-text search query
            limit = input.get("limit", 100)  # Number of results to return

            # Get context and agent
            ctxid = input.get("context", "")
            context = self.get_context(ctxid)

            # Check if memory is already initialized to avoid triggering preload
            memory_subdir = context.agent0.config.memory_subdir or "default"
            if Memory.index.get(memory_subdir) is None:
                # Memory not initialized yet, return empty results
                return {
                    "success": True,
                    "memories": [],
                    "total_count": 0,
                    "knowledge_count": 0,
                    "conversation_count": 0,
                    "areas_count": {},
                    "search_query": search_query,
                    "area_filter": area_filter,
                    "message": "Memory database not yet initialized. Use the agent first to initialize memory."
                }

            # Get already initialized memory instance (no initialization triggered)
            db = Memory(
                agent=context.agent0,
                db=Memory.index[memory_subdir],
                memory_subdir=memory_subdir,
            )

            memories = []

            if search_query:
                # If search query provided, use similarity search
                threshold = 0.6  # Lower threshold for broader search in dashboard
                filter_expr = f"area == '{area_filter}'" if area_filter else ""

                docs = await db.search_similarity_threshold(
                    query=search_query,
                    limit=limit,
                    threshold=threshold,
                    filter=filter_expr
                )
                memories = docs
            else:
                # If no search query, get all memories from specified area(s)
                all_docs = db.db.get_all_docs()

                for doc_id, doc in all_docs.items():
                    # Apply area filter if specified
                    if area_filter and doc.metadata.get("area", "") != area_filter:
                        continue

                    memories.append(doc)

                    # Apply limit
                    if len(memories) >= limit:
                        break

            # Format memories for the dashboard
            formatted_memories = []
            for memory in memories:
                metadata = memory.metadata

                # Extract key information
                memory_data = {
                    "id": metadata.get("id", "unknown"),
                    "area": metadata.get("area", "unknown"),
                    "timestamp": metadata.get("timestamp", "unknown"),
                    "content_preview": memory.page_content[:200] + ("..." if len(memory.page_content) > 200 else ""),
                    "content_full": memory.page_content,
                    "knowledge_source": metadata.get("knowledge_source", False),
                    "source_file": metadata.get("source_file", ""),
                    "file_type": metadata.get("file_type", ""),
                    "consolidation_action": metadata.get("consolidation_action", ""),
                    "tags": metadata.get("tags", []),
                    "metadata": metadata  # Include full metadata for advanced users
                }

                formatted_memories.append(memory_data)

            # Sort by timestamp (newest first) - handle "unknown" timestamps
            def get_sort_key(memory):
                timestamp = memory["timestamp"]
                if timestamp == "unknown" or not timestamp:
                    return "0000-00-00 00:00:00"  # Put unknown timestamps at the end
                return timestamp

            formatted_memories.sort(key=get_sort_key, reverse=True)

            # Get summary statistics
            total_memories = len(formatted_memories)
            knowledge_count = sum(1 for m in formatted_memories if m["knowledge_source"])
            conversation_count = total_memories - knowledge_count

            areas_count: dict[str, int] = {}
            for memory in formatted_memories:
                area = memory["area"]
                areas_count[area] = areas_count.get(area, 0) + 1

            return {
                "success": True,
                "memories": formatted_memories,
                "total_count": total_memories,
                "knowledge_count": knowledge_count,
                "conversation_count": conversation_count,
                "areas_count": areas_count,
                "search_query": search_query,
                "area_filter": area_filter
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "memories": [],
                "total_count": 0
            }
