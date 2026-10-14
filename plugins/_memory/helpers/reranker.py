"""Optional cross-encoder reranking for memory recall.

Reorders retrieved documents by query-document relevance before truncation
(`memory_recall_memories_max_result`) and before the optional LLM post-filter,
so precision of what enters the context window is decided by a joint
query-document scorer instead of bi-encoder cosine order.

The default model is cross-encoder/ms-marco-MiniLM-L6-v2 (local, ~80 MB).
sentence-transformers and torch are framework-pinned dependencies, so this
helper adds no new install. Reranking is pure reordering: it never drops or
mutates documents, and on any model-load failure it returns None so callers
keep the original order.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"

_lock = threading.Lock()
_loaded: tuple[str, Any] | None = None
_load_failed = False


def _load_model(model_name: str) -> Any | None:
    """Lazy singleton model loader; failure disables reranking for the session."""
    global _loaded, _load_failed
    if _load_failed:
        return None
    with _lock:
        if _loaded is not None and _loaded[0] == model_name:
            return _loaded[1]
        try:
            from sentence_transformers import CrossEncoder  # framework-pinned

            model = CrossEncoder(model_name, max_length=512)
        except Exception as e:
            _load_failed = True
            from helpers.print_style import PrintStyle

            PrintStyle.error(
                f"[_memory] Reranker model load failed ({model_name}): {e}"
            )
            return None
        _loaded = (model_name, model)
        return model


def _reset_cache() -> None:
    """Test hook: forget the cached model and any failure state."""
    global _loaded, _load_failed
    with _lock:
        _loaded = None
        _load_failed = False


async def rerank_docs(
    agent: Any,
    query: str,
    docs: list,
    *,
    model_name: str = "",
) -> list | None:
    """Reorder docs by cross-encoder relevance to the query.

    Returns None when reranking is unavailable (load failure or empty input
    beyond trivial size); callers keep the original order in that case.
    """
    if not query or not docs or len(docs) < 2:
        return docs if docs else None
    model = _load_model(model_name.strip() or DEFAULT_MODEL)
    if model is None:
        return None
    pairs = [(query, doc.page_content) for doc in docs]
    loop = asyncio.get_running_loop()
    scores = await loop.run_in_executor(None, lambda: model.predict(pairs))
    order = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)
    return [docs[i] for i in order]