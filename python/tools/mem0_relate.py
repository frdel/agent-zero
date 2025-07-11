from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings
from typing import List, Dict, Any


class Mem0Relate(Tool):
    """
    Memory relationship tool specifically for mem0 backend that can find
    related memories, create connections between memories, and analyze
    memory relationships for improved context understanding.
    """

    async def execute(self, 
                     memory_id="", 
                     query="", 
                     relation_type="similar",
                     limit=5,
                     **kwargs):
        """
        Find and analyze memory relationships
        
        Args:
            memory_id: ID of the memory to find relationships for
            query: Query to find related memories
            relation_type: Type of relationship ('similar', 'causal', 'temporal')
            limit: Maximum number of related memories to return
        """
        
        # Check if mem0 backend is enabled
        settings = get_settings()
        if settings.get("memory_backend") != "mem0" or not settings.get("mem0_enabled", False):
            result = "Memory relationship features are only available with mem0 backend enabled."
            return Response(message=result, break_loop=False)
        
        try:
            from python.helpers.memory_mem0 import Mem0Memory
            mem0_db = await Mem0Memory.get(self.agent)
            
            if memory_id:
                # Find relationships for a specific memory
                result = await self._find_memory_relationships(mem0_db, memory_id, relation_type, limit)
            elif query:
                # Find relationships based on query
                result = await self._find_query_relationships(mem0_db, query, relation_type, limit)
            else:
                result = "Please provide either a memory_id or query to find relationships."
                
            return Response(message=result, break_loop=False)
            
        except ImportError:
            result = "mem0ai package not installed. Memory relationship features require mem0ai."
            return Response(message=result, break_loop=False)
        
        except Exception as e:
            error_msg = f"Error analyzing memory relationships: {str(e)}"
            return Response(message=error_msg, break_loop=False)
    
    async def _find_memory_relationships(self, mem0_db, memory_id: str, relation_type: str, limit: int) -> str:
        """Find relationships for a specific memory"""
        try:
            # Get the original memory
            original_docs = await mem0_db.search_similarity_threshold(
                query=memory_id, limit=1, threshold=0.0, filter=f"id=='{memory_id}'"
            )
            
            if not original_docs:
                return f"Memory with ID '{memory_id}' not found."
            
            original_memory = original_docs[0]
            
            # Find related memories based on content
            related_docs = await mem0_db.search_similarity_threshold(
                query=original_memory.page_content, 
                limit=limit + 1,  # +1 because original will be included
                threshold=0.5,
                filter=f"id!='{memory_id}'"  # Exclude the original memory
            )
            
            if not related_docs:
                return f"No related memories found for memory '{memory_id}'."
            
            # Format the relationships
            result = f"**Original Memory:**\n{self._format_memory(original_memory)}\n\n"
            result += f"**Related Memories ({relation_type}):**\n\n"
            
            for i, doc in enumerate(related_docs[:limit], 1):
                result += f"{i}. **Similarity Score:** {doc.metadata.get('score', 0):.3f}\n"
                result += f"   {self._format_memory(doc)}\n\n"
            
            return result
            
        except Exception as e:
            return f"Error finding memory relationships: {str(e)}"
    
    async def _find_query_relationships(self, mem0_db, query: str, relation_type: str, limit: int) -> str:
        """Find relationships based on a query"""
        try:
            # Find memories related to the query
            docs = await mem0_db.search_similarity_threshold(
                query=query, limit=limit, threshold=0.5, filter=""
            )
            
            if not docs:
                return f"No memories found related to query: '{query}'"
            
            # Analyze relationships between found memories
            result = f"**Query:** {query}\n\n"
            result += f"**Related Memories ({relation_type}):**\n\n"
            
            for i, doc in enumerate(docs, 1):
                result += f"{i}. **Similarity Score:** {doc.metadata.get('score', 0):.3f}\n"
                result += f"   {self._format_memory(doc)}\n\n"
            
            # Add relationship analysis
            if len(docs) > 1:
                result += "**Relationship Analysis:**\n"
                result += await self._analyze_memory_relationships(docs)
            
            return result
            
        except Exception as e:
            return f"Error finding query relationships: {str(e)}"
    
    async def _analyze_memory_relationships(self, docs: List) -> str:
        """Analyze relationships between multiple memories"""
        analysis = []
        
        # Analyze temporal relationships
        timestamps = []
        for doc in docs:
            timestamp = doc.metadata.get('timestamp', '')
            if timestamp:
                timestamps.append((doc.metadata.get('id', 'Unknown'), timestamp))
        
        if len(timestamps) > 1:
            timestamps.sort(key=lambda x: x[1])
            analysis.append(f"- Temporal sequence: {' → '.join([f'{t[0]} ({t[1]})' for t in timestamps])}")
        
        # Analyze area relationships
        areas = {}
        for doc in docs:
            area = doc.metadata.get('area', 'main')
            if area not in areas:
                areas[area] = []
            areas[area].append(doc.metadata.get('id', 'Unknown'))
        
        if len(areas) > 1:
            area_summary = ", ".join([f"{area}: {len(ids)} memories" for area, ids in areas.items()])
            analysis.append(f"- Area distribution: {area_summary}")
        
        # Analyze content themes
        contents = [doc.page_content for doc in docs]
        common_words = self._find_common_themes(contents)
        if common_words:
            analysis.append(f"- Common themes: {', '.join(common_words)}")
        
        return "\n".join(analysis) if analysis else "No significant relationships detected."
    
    def _find_common_themes(self, contents: List[str]) -> List[str]:
        """Find common themes across memory contents"""
        from collections import Counter
        import re
        
        # Simple word frequency analysis
        all_words = []
        for content in contents:
            words = re.findall(r'\b\w+\b', content.lower())
            all_words.extend([word for word in words if len(word) > 3])
        
        if not all_words:
            return []
        
        word_counts = Counter(all_words)
        # Return words that appear in multiple memories
        common_words = [word for word, count in word_counts.most_common(5) if count > 1]
        return common_words
    
    def _format_memory(self, doc) -> str:
        """Format a memory for display"""
        memory_text = f"**ID:** {doc.metadata.get('id', 'Unknown')}\n"
        memory_text += f"**Area:** {doc.metadata.get('area', 'main')}\n"
        memory_text += f"**Content:** {doc.page_content[:200]}{'...' if len(doc.page_content) > 200 else ''}"
        return memory_text

class Mem0Relate(Tool):
    """Create a logical relationship between existing memories.

    This writes a lightweight linking document that references two or more
    memory IDs and stores a `relation` label. By storing the link as a memory
    document itself, both FAISS and mem0 backends can discover it later via
    querying.
    """

    async def execute(
        self,
        primary_id: str = "",
        related_ids: List[str] | None = None,
        relation: str = "related",
        note: str = "",
        **kwargs,
    ):
        if not primary_id or not related_ids:
            return Response(message="⚠️ primary_id and related_ids are required", break_loop=False)

        # Compose relation text
        related_str = ", ".join(related_ids)
        content_lines = [
            f"Relation: {relation}",
            f"PrimaryID: {primary_id}",
            f"RelatedIDs: {related_str}",
        ]
        if note:
            content_lines.append(f"Note: {note}")

        text = "\n".join(content_lines)
        metadata = {
            "area": Memory.Area.INSTRUMENTS.value,
            "type": "relation",
            "relation": relation,
            "primary_id": primary_id,
            "related_ids": related_ids,
        }
        metadata.update(kwargs)

        db = await Memory.get(self.agent)
        rid = await db.insert_text(text, metadata)
        conf = self.agent.read_prompt("fw.memory_saved.md", memory_id=rid)
        return Response(message=conf, break_loop=False)