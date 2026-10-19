from pathlib import Path
from types import SimpleNamespace

from plugins._document_query.tools.document_query import DocumentQueryTool

PROMPTS = Path("plugins/_document_query/prompts")


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())

    def read_prompt(self, name: str, **kwargs) -> str:
        text = (PROMPTS / name).read_text(encoding="utf-8")
        for key, value in kwargs.items():
            text = text.replace("{{" + key + "}}", str(value))
        return text.strip()


def _make_tool(args: dict) -> DocumentQueryTool:
    return DocumentQueryTool(
        agent=_FakeAgent(), name="document_query", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_passes_document_through():
    tool = _make_tool({"document": "https://example.com/docs/report.pdf", "query": "summary"})

    entry = tool.get_log_object()

    assert entry["type"] == "document_query"
    assert entry["heading"] == "icon://manage_search Querying: report.pdf"
    assert entry["kvps"]["document"] == "https://example.com/docs/report.pdf"
    assert entry["kvps"]["query"] == "summary"


def test_get_heading_lists_first_document_and_count():
    assert _make_tool({}).get_heading() == "icon://manage_search Reading"
    assert _make_tool({"document": ["https://example.com/a.pdf", "https://example.com/b.pdf"]}).get_heading() == "icon://manage_search Reading: a.pdf + 1 more"
    assert _make_tool({"document": ["https://example.com/a.pdf", "https://example.com/b.pdf"], "queries": ["total"]}).get_heading() == "icon://manage_search Querying: a.pdf + 1 more"


def test_empty_queries_read_documents():
    assert _make_tool({"document": "https://example.com/a.pdf", "queries": []}).get_heading() == "icon://manage_search Reading: a.pdf"
    assert _make_tool({"document": "https://example.com/a.pdf", "query": ""}).get_heading() == "icon://manage_search Reading: a.pdf"
