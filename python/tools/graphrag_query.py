from typing import Any

from python.helpers.graphrag_helper import GraphRAGHelper
from python.helpers.tool import Tool, Response


class GraphRAGQuery(Tool):
    """Tool for querying the GraphRAG knowledge graph via natural language.

    Parameters
    ----------
    message : str
        Natural language question to be answered using the graph.
    """

    async def execute(self, message: str = "", **kwargs: Any):  # type: ignore[override]
        # Nothing to do if no question provided
        if not message:
            return Response(message="No query provided.", break_loop=False)

        helper = GraphRAGHelper.get_default()
        try:
            answer = helper.query(message)
        except RuntimeError as exc:
            answer = (
                "Knowledge graph has no data yet. "
                "Please ingest information first using the appropriate ingestion tool."
            )
        except Exception as exc:  # Catch-all to avoid tool crash in conversation
            answer = f"GraphRAG query failed: {exc}"

        return Response(message=str(answer), break_loop=False)
