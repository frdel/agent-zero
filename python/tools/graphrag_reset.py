from typing import Any

from python.helpers.graphrag_helper import GraphRAGHelper
from python.helpers.tool import Tool, Response


class GraphRAGReset(Tool):
    """Tool for resetting the GraphRAG knowledge graph schema.

    This tool clears the entire knowledge graph and resets its schema
    to resolve compatibility issues. Use with caution as this will
    delete all existing data.

    Parameters
    ----------
    confirm : bool
        Safety confirmation flag. Must be set to True to actually perform the reset.
        Default is False to prevent accidental data loss.
    """

    async def execute(self, confirm: bool = False, **kwargs: Any):  # type: ignore[override]
        if not confirm:
            return Response(
                message="Graph reset not confirmed. Add 'confirm: true' to actually reset the graph schema. "
                        "Warning: This action will delete all knowledge graph data and cannot be undone.",
                break_loop=False
            )

        try:
            helper = GraphRAGHelper.get_default()

            # Use thread executor to avoid blocking
            import asyncio
            import concurrent.futures

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, helper.reset_graph_schema)

            msg = str(result)

        except RuntimeError:
            msg = "Knowledge graph reset failed. The graph may not exist or may already be empty."
        except Exception as exc:
            msg = f"Failed to reset knowledge graph schema: {exc}"

        return Response(message=msg, break_loop=False)
