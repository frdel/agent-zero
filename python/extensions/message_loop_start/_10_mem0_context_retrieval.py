import asyncio
from python.helpers.extension import Extension
from python.helpers.settings import get_settings
from python.helpers.memory import Memory
from agent import LoopData
from python.helpers.print_style import PrintStyle

class Mem0ContextRetrieval(Extension):
    """If mem0 backend is active, fetch highly relevant memories for the new
    user message and attach them to loop_data.context so that downstream
    prompts receive richer context.
    """

    DEFAULT_LIMIT = 15
    DEFAULT_THRESHOLD = 0.5

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Only run when mem0 backend enabled
        settings = get_settings()
        if settings.get("memory_backend") != "mem0" or not settings.get("mem0_enabled", False):
            return  # skip

        user_msg = loop_data.user_message or ""
        
        # Validate and clean user message
        if not user_msg or not isinstance(user_msg, str):
            return
            
        user_msg = str(user_msg).strip()
        if not user_msg:
            return

        try:
            PrintStyle.info(f"Getting Memory instance for mem0 context retrieval...")
            db = await Memory.get(self.agent)
            PrintStyle.info(f"Memory instance obtained: {type(db)}")
            
            # Temporarily disable search to isolate the error
            PrintStyle.info(f"Attempting mem0 search with query: '{user_msg}'")
            docs = await db.search_similarity_threshold(
                query=user_msg,
                limit=self.DEFAULT_LIMIT,
                threshold=self.DEFAULT_THRESHOLD,
                filter="",
            )
            PrintStyle.info(f"Search completed successfully, found {len(docs)} documents")
            if docs:
                context_snippets = []
                for doc in docs:
                    # Ensure page_content is a string
                    page_content = doc.page_content
                    if not isinstance(page_content, str):
                        page_content = str(page_content) if page_content is not None else ""
                    
                    area = doc.metadata.get('area', 'main')
                    if not isinstance(area, str):
                        area = str(area) if area is not None else 'main'
                        
                    snippet = f"[{area}] {page_content}"
                    context_snippets.append(snippet)
                    
                loop_data.context += "\n\n" + "\n".join(context_snippets)
        except Exception as e:
            PrintStyle.error(f"mem0 context retrieval failed: {e}") 