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
        if not user_msg:
            return

        try:
            db = await Memory.get(self.agent)
            docs = await db.search_similarity_threshold(
                query=user_msg,
                limit=self.DEFAULT_LIMIT,
                threshold=self.DEFAULT_THRESHOLD,
                filter="",
            )
            if docs:
                context_snippets = []
                for doc in docs:
                    snippet = f"[{doc.metadata.get('area','main')}] {doc.page_content}"
                    context_snippets.append(snippet)
                loop_data.context += "\n\n" + "\n".join(context_snippets)
        except Exception as e:
            PrintStyle.error(f"mem0 context retrieval failed: {e}") 