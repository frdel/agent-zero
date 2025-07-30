from python.helpers.api import ApiHandler, Request, Response
from python.helpers.memory import Memory


class MemoryDelete(ApiHandler):

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            # Get memory ID to delete
            memory_id = input.get("memory_id", "")
            if not memory_id:
                return {
                    "success": False,
                    "error": "Memory ID is required"
                }

            # Get context and agent
            ctxid = input.get("context", "")
            context = self.get_context(ctxid)

            # Check if memory is initialized to avoid triggering preload
            memory_subdir = context.agent0.config.memory_subdir or "default"
            if Memory.index.get(memory_subdir) is None:
                return {
                    "success": False,
                    "error": "Memory database not initialized"
                }

            # Get already initialized memory instance (no initialization triggered)
            db = Memory(
                agent=context.agent0,
                db=Memory.index[memory_subdir],
                memory_subdir=memory_subdir,
            )

            # Delete the memory by ID
            deleted_docs = await db.delete_documents_by_ids([memory_id])

            if deleted_docs:
                return {
                    "success": True,
                    "message": f"Memory {memory_id} deleted successfully",
                    "deleted_count": len(deleted_docs)
                }
            else:
                return {
                    "success": False,
                    "error": f"Memory {memory_id} not found or already deleted"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
