from typing import Any

from python.helpers.graphrag_helper import GraphRAGHelper
from python.helpers.tool import Tool, Response


class GraphRAGDelete(Tool):
    """Tool for deleting knowledge from the GraphRAG knowledge graph.

    This tool allows targeted deletion of specific entities and relationships
    from the knowledge graph based on natural language queries.

    Parameters
    ----------
    query : str
        Natural language description of what knowledge should be deleted.
        The tool will extract keywords and find matching entities/relationships.
    confirm : bool
        Safety confirmation flag. Must be set to True to actually delete knowledge.
        Default is False to prevent accidental data loss.
    """

    async def execute(self, query: str = "", confirm: bool = False, **kwargs: Any):  # type: ignore[override]
        if not query:
            return Response(
                message="No deletion query provided. Please specify what knowledge should be deleted.",
                break_loop=False
            )

        if not confirm:
            return Response(
                message="Deletion not confirmed. Add 'confirm: true' to actually delete knowledge from the graph. "
                        "Warning: This action cannot be undone.",
                break_loop=False
            )

        try:
            # Try to delete from main area by default, could be enhanced to specify area
        helper = GraphRAGHelper.get_for_area("main")

            # Use thread executor to avoid blocking
            import asyncio
            import concurrent.futures

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    helper.delete_knowledge,
                    query,
                    not confirm  # preview mode when confirm is False
                )

            msg = str(result)

        except RuntimeError:
            msg = "Knowledge graph has no data to delete. The graph appears to be empty."
        except Exception as exc:
            msg = f"Failed to process deletion request: {exc}"

        return Response(message=msg, break_loop=False)
