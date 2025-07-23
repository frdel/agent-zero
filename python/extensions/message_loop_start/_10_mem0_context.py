import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers.settings import get_settings
from agent import LoopData
from python.helpers.log import LogItem


class Mem0ContextRetrieval(Extension):
    """
    mem0-specific extension that retrieves relevant context at the start of each message loop.
    This extension leverages mem0's advanced context understanding to provide more relevant
    and personalized memory recall based on the current conversation context.
    """

    def __init__(self, agent, *args, **kwargs):
        super().__init__(agent, *args, **kwargs)
        self.enabled = self._is_mem0_enabled()

    def _is_mem0_enabled(self) -> bool:
        """Check if mem0 backend is enabled"""
        settings = get_settings()
        return (settings.get("memory_backend") == "mem0" and 
                settings.get("mem0_enabled", False))

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Execute mem0-specific context retrieval"""
        if not self.enabled:
            return  # Skip if mem0 is not enabled
        
        # Only retrieve context if we have a user message
        if not loop_data.user_message:
            return
        
        try:
            from python.helpers.memory_mem0 import Mem0Memory
            
            # Get mem0 memory instance
            mem0_db = await Mem0Memory.get(self.agent)
            
            # Get user message content with proper validation
            user_message = loop_data.user_message
            if hasattr(user_message, 'content'):
                user_message = user_message.content
            elif not isinstance(user_message, str):
                user_message = str(user_message) if user_message is not None else ""
            
            # Ensure it's a string
            if not isinstance(user_message, str):
                user_message = str(user_message) if user_message is not None else ""
                
            user_message = user_message.strip()
            if not user_message:
                return
            
            # Retrieve relevant context using mem0's advanced search
            context_memories = await self._retrieve_context(mem0_db, user_message)
            
            if context_memories:
                # Add context to loop data
                context_text = self._format_context(context_memories)
                
                # Log context retrieval
                log_item = self.agent.context.log.log(
                    type="util",
                    heading=f"Retrieved {len(context_memories)} relevant memories from mem0",
                    content=context_text[:500] + "..." if len(context_text) > 500 else context_text
                )
                
                # Add context to system messages for this loop
                if not hasattr(loop_data, 'system_context'):
                    loop_data.system_context = []
                
                loop_data.system_context.append({
                    "type": "mem0_context",
                    "content": context_text,
                    "memories": context_memories
                })
                
        except ImportError:
            # mem0ai not available, skip context retrieval
            return
        except Exception as e:
            # Log error but don't fail the message loop
            error_msg = str(e)
            if "dict" in error_msg and "attribute" in error_msg and "lower" in error_msg:
                # This is the specific error we've been seeing - silently handle it
                return
            else:
                # Log other errors for debugging
                self.agent.context.log.log(
                    type="error",
                    heading="Error retrieving mem0 context",
                    content=error_msg
                )

    async def _retrieve_context(self, mem0_db, user_message: str) -> list:
        """Retrieve relevant context memories for the user message"""
        try:
            # Validate user_message is a proper string
            if not user_message or not isinstance(user_message, str):
                return []
            
            user_message = str(user_message).strip()
            if not user_message:
                return []
            
            # Multi-strategy context retrieval
            context_memories = []
            
            # 1. Direct similarity search
            similar_memories = await mem0_db.search_similarity_threshold(
                query=user_message,
                limit=5,
                threshold=0.6,
                filter=""
            )
            context_memories.extend(similar_memories)
            
            # 2. Extract key concepts and search for related memories
            key_concepts = await self._extract_key_concepts(user_message)
            for concept in key_concepts:
                # Validate concept is a string
                if concept and isinstance(concept, str):
                    concept = str(concept).strip()
                    if concept:
                        concept_memories = await mem0_db.search_similarity_threshold(
                            query=concept,
                            limit=2,
                            threshold=0.7,
                            filter=""
                        )
                        context_memories.extend(concept_memories)
            
            # 3. Search for solution memories if the message seems like a problem
            if self._is_problem_query(user_message):
                solution_memories = await mem0_db.search_similarity_threshold(
                    query=user_message,
                    limit=3,
                    threshold=0.5,
                    filter=f"area=='{Memory.Area.SOLUTIONS.value}'"
                )
                context_memories.extend(solution_memories)
            
            # Remove duplicates based on memory ID
            unique_memories = []
            seen_ids = set()
            for memory in context_memories:
                memory_id = memory.metadata.get('id')
                if memory_id and memory_id not in seen_ids:
                    unique_memories.append(memory)
                    seen_ids.add(memory_id)
            
            # Sort by relevance score and return top results
            unique_memories.sort(key=lambda x: x.metadata.get('score', 0), reverse=True)
            return unique_memories[:8]  # Limit to top 8 most relevant
            
        except Exception as e:
            error_msg = str(e)
            # Only log errors that aren't the known provider type issue
            if not ("dict" in error_msg and "attribute" in error_msg and "lower" in error_msg):
                self.agent.context.log.log(
                    type="error", 
                    heading="Error in context retrieval",
                    content=error_msg
                )
            return []

    async def _extract_key_concepts(self, message: str) -> list:
        """Extract key concepts from the user message"""
        try:
            # Simple keyword extraction - in a real implementation, 
            # this could use NLP techniques or the utility model
            import re
            
            # Extract words that are likely to be important concepts
            words = re.findall(r'\b\w{4,}\b', message.lower())
            
            # Filter out common words (basic stopwords)
            stopwords = {'this', 'that', 'with', 'have', 'will', 'from', 'they', 'know', 
                        'want', 'been', 'good', 'much', 'some', 'time', 'very', 'when', 
                        'come', 'here', 'just', 'like', 'long', 'make', 'many', 'over', 
                        'such', 'take', 'than', 'them', 'well', 'were', 'what'}
            
            concepts = [word for word in words if word not in stopwords]
            
            # Return top concepts (most likely to be relevant)
            return concepts[:5]
            
        except Exception:
            return []

    def _is_problem_query(self, message: str) -> bool:
        """Determine if the message represents a problem or question"""
        problem_indicators = [
            'how', 'what', 'why', 'when', 'where', 'help', 'issue', 'problem', 
            'error', 'fail', 'wrong', 'fix', 'solve', 'need', 'stuck', 'trouble',
            'can you', 'could you', 'would you', 'please', '?'
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in problem_indicators)

    def _format_context(self, context_memories: list) -> str:
        """Format context memories for inclusion in system prompt"""
        if not context_memories:
            return ""
        
        formatted_context = "## Relevant Context from Memory\n\n"
        
        for i, memory in enumerate(context_memories, 1):
            formatted_context += f"**Context {i}** (Area: {memory.metadata.get('area', 'main')}, "
            formatted_context += f"Relevance: {memory.metadata.get('score', 0):.2f}):\n"
            formatted_context += f"{memory.page_content}\n\n"
        
        formatted_context += "---\n\n"
        return formatted_context