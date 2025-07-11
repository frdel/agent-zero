from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings

DEFAULT_THRESHOLD = 0.7
DEFAULT_LIMIT = 10


class Mem0Query(Tool):
    """
    Enhanced memory query tool specifically for mem0 backend that provides
    advanced querying capabilities including user-specific memory search,
    memory relationships, and contextual retrieval.
    """

    async def execute(self, 
                     query="", 
                     threshold=DEFAULT_THRESHOLD, 
                     limit=DEFAULT_LIMIT, 
                     filter="", 
                     user_context=True,
                     **kwargs):
        """
        Query memories with enhanced mem0 features
        
        Args:
            query: Search query string
            threshold: Similarity threshold (0-1)
            limit: Maximum number of results
            filter: Additional filter conditions
            user_context: Whether to include user-specific context
        """
        
        # Check if mem0 backend is enabled
        settings = get_settings()
        if settings.get("memory_backend") != "mem0" or not settings.get("mem0_enabled", False):
            # Fall back to regular memory search
            db = await Memory.get(self.agent)
            docs = await db.search_similarity_threshold(
                query=query, limit=limit, threshold=threshold, filter=filter
            )
            
            if len(docs) == 0:
                result = self.agent.read_prompt("fw.memories_not_found.md", query=query)
            else:
                text = "\n\n".join(Memory.format_docs_plain(docs))
                result = str(text)
                
            return Response(message=result, break_loop=False)
        
        # Use mem0 backend for enhanced search
        try:
            from python.helpers.memory_mem0 import Mem0Memory
            mem0_db = await Mem0Memory.get(self.agent)
            
            # Enhanced search with mem0 features
            docs = await mem0_db.search_similarity_threshold(
                query=query, limit=limit, threshold=threshold, filter=filter
            )
            
            if len(docs) == 0:
                result = self.agent.read_prompt("fw.memories_not_found.md", query=query)
            else:
                # Format results with enhanced metadata
                formatted_memories = []
                for doc in docs:
                    memory_text = f"**Memory ID:** {doc.metadata.get('id', 'Unknown')}\n"
                    memory_text += f"**Score:** {doc.metadata.get('score', 0):.3f}\n"
                    memory_text += f"**Area:** {doc.metadata.get('area', 'main')}\n"
                    memory_text += f"**Timestamp:** {doc.metadata.get('timestamp', 'Unknown')}\n"
                    memory_text += f"**Content:** {doc.page_content}\n"
                    
                    # Add additional metadata if available
                    for key, value in doc.metadata.items():
                        if key not in ['id', 'score', 'area', 'timestamp']:
                            memory_text += f"**{key.title()}:** {value}\n"
                            
                    formatted_memories.append(memory_text)
                
                result = "\n---\n".join(formatted_memories)
                
            return Response(message=result, break_loop=False)
            
        except ImportError:
            # Fall back to regular memory search if mem0ai is not available
            db = await Memory.get(self.agent)
            docs = await db.search_similarity_threshold(
                query=query, limit=limit, threshold=threshold, filter=filter
            )
            
            if len(docs) == 0:
                result = self.agent.read_prompt("fw.memories_not_found.md", query=query)
            else:
                text = "\n\n".join(Memory.format_docs_plain(docs))
                result = str(text)
                
            return Response(message=result, break_loop=False)
        
        except Exception as e:
            error_msg = f"Error querying mem0 memories: {str(e)}"
            return Response(message=error_msg, break_loop=False)