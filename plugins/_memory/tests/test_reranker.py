"""Tests for the optional _memory cross-encoder reranker."""

from types import SimpleNamespace

import pytest

from plugins._memory.helpers import reranker


def _doc(text):
    return SimpleNamespace(page_content=text, metadata={})


@pytest.fixture(autouse=True)
def _clean_cache():
    reranker._reset_cache()
    yield
    reranker._reset_cache()


class TestRerankDocs:
    @pytest.mark.asyncio
    async def test_reorders_by_relevance(self, monkeypatch):
        query = "Which suppliers did we stop using in 2025?"
        docs = [
            _doc("Employee onboarding checklist for new team members."),
            _doc("Vendor termination log 2025: stopped using Chen Manufacturing."),
        ]
        scores = [-10.0, 5.0]

        class FakeModel:
            def predict(self, pairs):
                assert all(p[0] == query for p in pairs)
                return scores

        monkeypatch.setattr(reranker, "_load_model", lambda name: FakeModel())
        result = await reranker.rerank_docs(None, query, docs)
        assert result == [docs[1], docs[0]]

    @pytest.mark.asyncio
    async def test_load_failure_returns_none(self, monkeypatch):
        monkeypatch.setattr(reranker, "_load_model", lambda name: None)
        docs = [_doc("a"), _doc("b")]
        assert await reranker.rerank_docs(None, "q", docs) is None

    @pytest.mark.asyncio
    async def test_single_doc_passthrough(self):
        docs = [_doc("only")]
        assert await reranker.rerank_docs(None, "q", docs) == docs

    @pytest.mark.asyncio
    async def test_empty_or_no_query(self):
        # empty query cannot rerank: docs pass through unchanged
        docs = [_doc("a")]
        assert await reranker.rerank_docs(None, "", docs) == docs
        # empty docs: nothing to do, signals no-op
        assert await reranker.rerank_docs(None, "q", []) is None

    @pytest.mark.asyncio
    async def test_default_model_used_when_blank(self, monkeypatch):
        seen = {}

        def fake_load(name):
            seen["name"] = name
            return None

        monkeypatch.setattr(reranker, "_load_model", fake_load)
        await reranker.rerank_docs(None, "q", [_doc("a"), _doc("b")], model_name="  ")
        assert seen["name"] == reranker.DEFAULT_MODEL


class TestConfigContract:
    def test_defaults_declared(self):
        from pathlib import Path

        cfg = Path(__file__).resolve().parents[1] / "default_config.yaml"
        text = cfg.read_text(encoding="utf-8")
        assert "memory_recall_rerank_enabled: false" in text
        assert "cross-encoder/ms-marco-MiniLM-L6-v2" in text

    def test_recall_extension_reads_new_keys(self):
        from pathlib import Path

        ext = (
            Path(__file__).resolve().parents[1]
            / "extensions/python/message_loop_prompts_after/_50_recall_memories.py"
        )
        text = ext.read_text(encoding="utf-8")
        assert 'set.get("memory_recall_rerank_enabled")' in text
        assert 'set.get("memory_recall_rerank_model", "")' in text
