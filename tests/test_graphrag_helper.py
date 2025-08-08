"""Tests for GraphRAG integration helper.

These unit-tests monkey-patch external network / LLM dependencies so that the
logic inside :pymod:`python.helpers.graphrag_helper` can be exercised without
real calls to providers while still asserting that the correct objects are
constructed and invoked.
"""
from __future__ import annotations

import types
from typing import List

import pytest

# We import the module *after* monkey-patching critical dependencies in each
# test so that the import uses our fakes.


@pytest.fixture()
def patched_graphrag(monkeypatch):
    """Patch expensive external dependencies inside graphrag_helper.

    Returns the imported ``graphrag_helper`` module ready for testing.
    """

    # ------------------------------------------------------------------ fakes
    # Fake LiteModel that records the init args but does *not* call real LLMs
    class FakeLiteModel:  # pylint: disable=too-few-public-methods
        init_args = None  # type: ignore  # holds last call signature

        def __init__(self, *args, **kwargs):  # noqa: D401, ANN001
            # store the arguments for later inspection
            FakeLiteModel.init_args = (args, kwargs)

        # KnowledgeGraphModelConfig.with_model may deepcopy the model – to make
        # that work we implement ``__deepcopy__`` returning ``self``.
        def __deepcopy__(self, _memo):  # noqa: D401, ANN001
            return self

    # Fake KnowledgeGraph instance that captures ingestion + query behaviour
    class FakeChatSession:  # pylint: disable=too-few-public-methods
        def send_message(self, message):  # noqa: D401, ANN001
            # Echo a deterministic answer structure similar to SDK
            return {"answer": f"MOCK_ANSWER to: {message}"}

    class FakeKG:  # pylint: disable=too-few-public-methods
        def __init__(self, *args, **kwargs):  # noqa: D401, ANN001, D401
            self.processed_sources: List = []

        def process_sources(self, sources, *args, **kwargs):  # noqa: D401, ANN001
            self.processed_sources.extend(sources)

        def chat_session(self):  # noqa: D401
            return FakeChatSession()

    # Fake Ontology to avoid LLM analysis during ``Ontology.from_sources``
    class FakeOntology:  # pylint: disable=too-few-public-methods
        pass

    # Fake model config factory to avoid deepcopy internals
    class FakeModelConfig:  # pylint: disable=too-few-public-methods
        pass

    def fake_with_model(model):  # noqa: D401, ANN001
        return FakeModelConfig()

    # Fake settings minimal set
    def fake_settings():  # noqa: D401
        return {
            "chat_model_provider": "openai",
            "chat_model_name": "gpt-4.1",
            "chat_model_api_base": "",
            "chat_model_kwargs": {},
        }

    # ----------------------------------------------------------------- patches
    import importlib

    module_path = "python.helpers.graphrag_helper"
    graphrag_helper = importlib.import_module(module_path)

    monkeypatch.setattr(graphrag_helper, "LiteModel", FakeLiteModel)
    monkeypatch.setattr(graphrag_helper, "KnowledgeGraph", FakeKG)
    monkeypatch.setattr(graphrag_helper, "Ontology", types.SimpleNamespace(from_sources=lambda *_args, **_kw: FakeOntology()))
    monkeypatch.setattr(
        graphrag_helper, "KnowledgeGraphModelConfig",
        types.SimpleNamespace(with_model=fake_with_model)
    )
    monkeypatch.setattr(graphrag_helper, "get_settings", fake_settings)

    # Reset singleton between tests
    graphrag_helper.GraphRAGHelper._default_instance = None  # type: ignore

    return graphrag_helper


# ---------------------------------------------------------------------------
#                               Test cases
# ---------------------------------------------------------------------------

def test_singleton_instance(patched_graphrag):  # noqa: D103, ANN001
    GraphRAGHelper = patched_graphrag.GraphRAGHelper  # type: ignore

    instance1 = GraphRAGHelper.get_default()
    instance2 = GraphRAGHelper.get_default()

    assert instance1 is instance2, "GraphRAGHelper should be a singleton instance"


def test_ingestion_creates_graph_and_processes_sources(patched_graphrag):  # noqa: D103, ANN001
    GraphRAGHelper = patched_graphrag.GraphRAGHelper  # type: ignore
    FakeKG = patched_graphrag.KnowledgeGraph  # type: ignore

    helper = GraphRAGHelper()
    assert helper._kg is not None, "KnowledgeGraph should be instantiated on helper init"
    kg: FakeKG = helper._kg  # type: ignore[arg-type]

    # Before ingestion
    assert kg.processed_sources == []

    helper.ingest_text("Paris is the capital of France.")

    # After ingestion the sources list should contain one entry
    assert len(kg.processed_sources) == 1, "Source should have been processed"


def test_query_returns_answer(patched_graphrag):  # noqa: D103, ANN001
    GraphRAGHelper = patched_graphrag.GraphRAGHelper  # type: ignore

    helper = GraphRAGHelper()
    # Ensure ingestion first so KG exists (even though FakeKG already exists)
    helper.ingest_text("Sample text to build ontology.")

    answer = helper.query("What is this?")

    assert answer.startswith("MOCK_ANSWER"), "Helper should return mocked answer from FakeChatSession"


# ---------------------------------------------------------------------------
#                       Tool classes – smoke-tests
# ---------------------------------------------------------------------------

def test_tools_smoke(monkeypatch, patched_graphrag):  # noqa: D103, ANN001
    # Patch GraphRAGHelper methods so tools run without complex setup
    helper = patched_graphrag.GraphRAGHelper.get_default()

    ingested: dict = {"called": False}

    def fake_ingest_text(text, instruction=None):  # noqa: D401, ANN001
        ingested["called"] = True

    monkeypatch.setattr(helper, "ingest_text", fake_ingest_text)
    monkeypatch.setattr(helper, "query", lambda q: "tool-answer")

    from python.tools.graphrag_ingest import GraphRAGIngest
    from python.tools.graphrag_query import GraphRAGQuery

    # Build minimal stubs for required constructor params
    class StubAgent:  # pylint: disable=too-few-public-methods
        def log_to_all(self, *args, **kwargs):  # noqa: D401, ANN001
            pass

    stub_agent = StubAgent()

    ingest_tool = GraphRAGIngest(stub_agent, "graphrag_ingest", None, {}, "", None)
    query_tool = GraphRAGQuery(stub_agent, "graphrag_query", None, {}, "", None)

    # Run tools
    import asyncio

    asyncio.run(ingest_tool.execute(text="tool text"))
    assert ingested["called"], "Ingest tool should call helper.ingest_text"

    resp = asyncio.run(query_tool.execute(message="some question"))
    assert resp.message == "tool-answer", "Query tool should return helper answer"
