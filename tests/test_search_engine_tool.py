import pytest

import plugins._search_engine.tools.search_engine as search_engine_module
from plugins._search_engine.tools.search_engine import SEARCH_ENGINE_RESULTS, SearchEngine


class _FakeAgent:
    def __init__(self) -> None:
        self.interventions = 0

    async def handle_intervention(self, *args, **kwargs) -> None:
        self.interventions += 1


def _make_tool() -> SearchEngine:
    return SearchEngine(
        agent=_FakeAgent(), name="search_engine", method="execute", args={}, message="search", loop_data=None
    )


def test_format_result_joins_title_url_and_content() -> None:
    formatted = _make_tool().format_result_searxng(
        {"results": [{"title": "T", "url": "https://x", "content": "C"}]},
        "Search Engine",
    )

    assert formatted == "T\nhttps://x\nC"


def test_format_result_caps_results_at_limit() -> None:
    items = [{"title": f"t{i}", "url": f"u{i}", "content": "c"} for i in range(30)]

    formatted = _make_tool().format_result_searxng({"results": items}, "Search Engine")

    assert formatted.count("\n\n") == SEARCH_ENGINE_RESULTS - 1
    assert "t29" not in formatted
    assert "t9" in formatted


def test_format_result_skips_non_dict_entries() -> None:
    items = ["garbage", {"title": "ok", "url": "u", "content": "c"}, None, 42]

    formatted = _make_tool().format_result_searxng({"results": items}, "Search Engine")

    assert formatted == "ok\nu\nc"


def test_format_result_handles_error_results() -> None:
    formatted = _make_tool().format_result_searxng(RuntimeError("boom"), "Search Engine")

    assert formatted == "Search Engine search failed: boom"


def test_format_result_handles_missing_and_none_results() -> None:
    assert _make_tool().format_result_searxng({}, "Search Engine") == ""
    assert _make_tool().format_result_searxng(None, "Search Engine") == ""


@pytest.mark.anyio
async def test_execute_returns_formatted_results(monkeypatch):
    async def fake_search(query: str):
        return {"results": [{"title": "T", "url": "U", "content": "C"}]}

    monkeypatch.setattr(search_engine_module, "searxng", fake_search)
    tool = _make_tool()

    response = await tool.execute(query="test")

    assert response.break_loop is False
    assert response.message == "T\nU\nC"
    assert tool.agent.interventions == 1


@pytest.mark.anyio
async def test_execute_survives_search_failure(monkeypatch):
    async def failing_search(query: str):
        raise RuntimeError("searxng down")

    monkeypatch.setattr(search_engine_module, "searxng", failing_search)

    response = await _make_tool().execute(query="test")

    assert response.break_loop is False
    assert "search failed" in response.message.lower()
