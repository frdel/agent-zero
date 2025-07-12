from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings
from python.helpers.print_style import PrintStyle
from typing import List, Dict, Any
import asyncio
import json
import os


class Mem0Migrate(Tool):
    """Migrate existing FAISS memories for current `agent_memory_subdir` to mem0 backend.

    Usage: mem0_migrate(confirm=True)
    Without confirm, tool previews how many docs will be migrated.
    """

    async def execute(self, confirm: bool = False, limit: int | None = None, **kwargs):
        settings = get_settings()
        if settings.get("memory_backend") == "mem0" and settings.get("mem0_enabled", False):
            return Response(message="mem0 is already the active backend; nothing to migrate.", break_loop=False)

        # Get current FAISS database
        faiss_db = await Memory.get(self.agent)
        all_docs = list(faiss_db.db.get_all_docs().values())  # type: ignore
        total = len(all_docs)
        if limit:
            all_docs = all_docs[:limit]
        preview_msg = f"Found {total} memory documents to migrate." + (f" Previewing first {len(all_docs)}." if not confirm else "")

        if not confirm:
            return Response(message=preview_msg + "\nRun with confirm=True to proceed.", break_loop=False)

        # Enable mem0 in settings temporarily in-memory
        settings["memory_backend"] = "mem0"
        settings["mem0_enabled"] = True
        # Do not persist yet; operates only in runtime.
        # Insert into mem0
        from python.helpers.memory_mem0 import Mem0Memory
        mem0_db = await Mem0Memory.get(self.agent)

        inserted = 0
        # batch insert to preserve metadata
        batch: list = []
        for doc in all_docs:
            batch.append(doc)
            if len(batch) >= 50:
                await mem0_db.insert_documents(batch)
                inserted += len(batch)
                batch = []
        if batch:
            await mem0_db.insert_documents(batch)
            inserted += len(batch)

        msg = f"Migration complete: {inserted} documents moved to mem0 memory backend."
        PrintStyle.standard(msg)
        return Response(message=msg, break_loop=False)