from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Replicate the framework's faiss import stub (faiss-cpu SVE probe vs numpy);
# must run before any `import faiss` (see dev-ticket-2026-08-21 notes).
from helpers import faiss_monkey_patch  # noqa: F401
import faiss

from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from plugins._memory.helpers import memory as memory_module
from plugins._memory.helpers.memory import MyFaiss

DIM = 8


class DeterministicEmbeddings(Embeddings):
    """Offline deterministic embeddings - no network, no API keys."""

    def _vector(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(DIM)
        return (vec / np.linalg.norm(vec)).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


def _build_store(texts: list[str]) -> MyFaiss:
    emb = DeterministicEmbeddings()
    index = faiss.IndexFlatIP(DIM)
    docs = [
        Document(page_content=t, metadata={"id": f"doc-{i}", "area": "main"})
        for i, t in enumerate(texts)
    ]
    docstore = InMemoryDocstore({f"doc-{i}": d for i, d in enumerate(docs)})
    mapping = {i: f"doc-{i}" for i in range(len(docs))}
    index.add(np.array(emb.embed_documents(texts), dtype=np.float32))
    return MyFaiss(
        embedding_function=emb,
        index=index,
        docstore=docstore,
        index_to_docstore_id=mapping,
    )


def _load(tmp_path: Path) -> MyFaiss:
    return MyFaiss.load_local(
        folder_path=str(tmp_path),
        embeddings=DeterministicEmbeddings(),
        allow_dangerous_deserialization=True,
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tmp_files(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.glob("*.tmp"))


def test_atomic_save_success_leaves_no_temp_files(tmp_path):
    store = _build_store(["alpha memory", "beta memory", "gamma memory"])
    store.save_local(str(tmp_path))

    assert (tmp_path / "index.faiss").exists()
    assert (tmp_path / "index.pkl").exists()
    assert _tmp_files(tmp_path) == []

    reloaded = _load(tmp_path)
    assert reloaded.index.ntotal == 3
    assert set(reloaded.index_to_docstore_id.values()) == {
        "doc-0",
        "doc-1",
        "doc-2",
    }


def test_crash_between_writes_leaves_no_orphan_state(tmp_path, monkeypatch):
    """Regression (a): crash between the two file writes.

    After Fix C, a crash after the index tmp write but before the pickle
    write must leave both originals untouched and clean up temp files, so
    the on-disk pair never desyncs.
    """
    store = _build_store(["alpha memory", "beta memory"])
    store.save_local(str(tmp_path))
    baseline = {
        name: _file_hash(tmp_path / name)
        for name in ("index.faiss", "index.pkl")
    }

    # mutate the in-memory store (simulates mid-consolidation state)
    store.add_documents(
        [Document(page_content="delta memory", metadata={"id": "doc-2", "area": "main"})],
        ids=["doc-2"],
    )
    assert store.index.ntotal == 3

    real_write_index = faiss.write_index

    def crashing_write_index(index, path):
        real_write_index(index, path)
        raise RuntimeError("simulated crash after index tmp write")

    monkeypatch.setattr(memory_module.faiss, "write_index", crashing_write_index)

    with pytest.raises(RuntimeError):
        store.save_local(str(tmp_path))

    # originals byte-identical -> no half-written pair, no orphan state
    assert _file_hash(tmp_path / "index.faiss") == baseline["index.faiss"]
    assert _file_hash(tmp_path / "index.pkl") == baseline["index.pkl"]
    assert _tmp_files(tmp_path) == []

    reloaded = _load(tmp_path)
    assert reloaded.index.ntotal == 2
    assert set(reloaded.index_to_docstore_id.values()) == {"doc-0", "doc-1"}


def test_crash_between_renames_self_heals_on_search(tmp_path, monkeypatch):
    """Residual window of Fix C: crash between the two os.replace calls.

    Disk ends up with the NEW index.faiss (3 vectors) and the OLD index.pkl
    (2 docstore entries) - the orphan state. Fix B must make search skip and
    purge the orphan instead of raising ValueError.
    """
    store = _build_store(["alpha memory", "beta memory"])
    store.save_local(str(tmp_path))

    store.add_documents(
        [Document(page_content="delta memory", metadata={"id": "doc-2", "area": "main"})],
        ids=["doc-2"],
    )

    real_replace = os.replace
    calls = {"n": 0}

    def crashing_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            # crash BEFORE the second rename: new index.faiss is in place,
            # old index.pkl stays -> the orphan/desync state
            raise RuntimeError("simulated crash between renames")
        real_replace(src, dst)

    monkeypatch.setattr(memory_module.os, "replace", crashing_replace)

    with pytest.raises(RuntimeError):
        store.save_local(str(tmp_path))
    monkeypatch.undo()

    # orphan state on disk: NEW index.faiss (3 vectors) + OLD index.pkl
    # (2 docstore entries, 2 mapping entries - the mapping lives in the
    # pickle), so vector position 2 is unmapped -> KeyError path in Fix B
    reloaded = _load(tmp_path)
    assert reloaded.index.ntotal == 3
    assert len(reloaded.index_to_docstore_id) == 2
    assert len(reloaded.docstore._dict) == 2

    # Fix B: search self-heals instead of ValueError
    results = reloaded.similarity_search("alpha memory", k=3)
    assert results
    assert reloaded.index.ntotal == 2
    assert set(reloaded.index_to_docstore_id.values()) == {"doc-0", "doc-1"}

    # healed state persists through save/load
    reloaded.save_local(str(tmp_path))
    again = _load(tmp_path)
    assert again.index.ntotal == 2
    assert set(again.index_to_docstore_id.values()) == {"doc-0", "doc-1"}


def test_orphaned_id_lookup_skips_instead_of_raising(tmp_path):
    """Regression (b): lookup of an orphaned ID skips, no ValueError."""
    store = _build_store(["alpha memory", "beta memory"])
    store.save_local(str(tmp_path))

    reloaded = _load(tmp_path)

    # inject orphan: extra vector + mapping entry with no docstore doc
    vec = np.array(
        [DeterministicEmbeddings().embed_query("orphan vector")], dtype=np.float32
    )
    reloaded.index.add(vec)
    reloaded.index_to_docstore_id[2] = "orphan-missing-id"
    assert reloaded.index.ntotal == 3
    assert "orphan-missing-id" not in reloaded.docstore._dict

    results = reloaded.similarity_search("alpha memory", k=3)

    assert all(doc.metadata["id"] != "orphan-missing-id" for doc in results)
    assert reloaded.index.ntotal == 2
    assert set(reloaded.index_to_docstore_id.values()) == {"doc-0", "doc-1"}


def test_missing_mapping_entry_self_heals(tmp_path):
    """Reverse desync: docstore has the doc but the mapping entry is gone.

    The parent raises KeyError on the unmapped position; Fix B must purge
    the unmapped vector and return results instead of crashing.
    """
    store = _build_store(["alpha memory", "beta memory"])
    store.save_local(str(tmp_path))

    reloaded = _load(tmp_path)
    del reloaded.index_to_docstore_id[1]

    results = reloaded.similarity_search("beta memory", k=2)

    assert results
    assert reloaded.index.ntotal == 1
    assert set(reloaded.index_to_docstore_id.values()) == {"doc-0"}
