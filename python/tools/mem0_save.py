from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings

class Mem0Save(Tool):
    """Advanced memory save tool for mem0 backend.

    Supports enriched metadata and area selection. If mem0 is disabled, falls
    back to the regular MemorySave behaviour via generic Memory interface.
    """

    async def execute(self, text: str = "", area: str = "", metadata: dict | None = None, **kwargs):
        if not text:
            return Response(message="⚠️ No text provided to save to memory.", break_loop=False)

        # default area
        if not area:
            area = Memory.Area.MAIN.value

        # Merge explicit metadata and additional kwargs
        meta = metadata.copy() if metadata else {}
        meta.update(kwargs)
        meta.setdefault("area", area)

        # Detect backend
        settings = get_settings()
        use_mem0 = settings.get("memory_backend") == "mem0" and settings.get("mem0_enabled", False)

        # Save through Memory factory (handles mem0 transparently)
        db = await Memory.get(self.agent)
        memory_id = await db.insert_text(text, meta)

        # Build confirmation message
        if use_mem0:
            tmpl = "fw.memory_saved.md"  # reuse existing prompt
        else:
            tmpl = "fw.memory_saved.md"

        result = self.agent.read_prompt(tmpl, memory_id=memory_id)
        return Response(message=result, break_loop=False) 