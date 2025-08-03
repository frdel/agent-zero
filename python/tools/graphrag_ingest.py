from typing import Any

from python.helpers.graphrag_helper import GraphRAGHelper
from python.helpers.tool import Tool, Response


class GraphRAGIngest(Tool):
    """Tool that ingests arbitrary text into the GraphRAG knowledge graph.

    Parameters
    ----------
    text : str
        The textual information that should be analysed and stored within the
        knowledge graph.
    instruction : str, optional
        Optional extraction instruction that guides the LLM what kind of
        information should be extracted (e.g. "focus on medications and side
        effects").
    """

    async def execute(self, text: str = "", instruction: str = "", **kwargs: Any):  # type: ignore[override]
        if not text:
            return Response(message="No text provided for ingestion.", break_loop=False)

        helper = GraphRAGHelper.get_default()
        try:
            helper.ingest_text(text, instruction if instruction else None)
            msg = "Text successfully ingested into the knowledge graph."
        except Exception as exc:
            msg = f"Failed to ingest text into knowledge graph: {exc}"

        return Response(message=msg, break_loop=False)
