"""Tests for the memory-rebuild checkpoint/resume mechanism in
plugins/_memory/helpers/memory.py.

Context: a reindex (triggered when the configured embedding model no longer
matches the one a memory store was built with) used to embed every document
in a single pass and only persist the result at the very end. Interrupting
that pass (crash, restart, a slow/shared embeddings backend) threw away all
already-embedded work. The fix batches the reindex and checkpoints to disk
after every batch (`index.rebuilding.faiss`/`.pkl`), so a resumed run can
skip documents it already embedded.

That checkpoint must not be trusted blindly: if the target embedding model
changes *again* while a rebuild is interrupted, the checkpoint's vectors are
of a different dimension/semantic space than what the new target model
would produce. These tests cover both the happy path (resume under the same
model) and that guard (refuse a stale, wrong-model checkpoint and rebuild
fresh instead of corrupting/crashing on it).
"""

import json
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- Stub out heavy/unrelated modules memory.py's import chain pulls in
# transitively via `import models` / `from agent import Agent, AgentContext`,
# so these tests exercise the real memory.py + real FAISS without needing a
# full runtime (network clients, MCP, litellm providers, etc.) to be usable.
sys.modules.setdefault("giturlparse", types.SimpleNamespace(parse=lambda *a, **k: None))


from langchain_core.documents import Document  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402

from plugins._memory.helpers import memory as memory_module  # noqa: E402
from plugins._memory.helpers.memory import Memory, MyFaiss  # noqa: E402


class FakeModelConfig:
    """Minimal stand-in for models.ModelConfig -- memory.py only reads
    .provider, .name and calls .build_kwargs()."""

    def __init__(self, provider: str, name: str, kwargs: dict | None = None, api_key: str = ""):
        self.provider = provider
        self.name = name
        self.kwargs = kwargs or {}
        self.api_key = api_key

    def build_kwargs(self):
        kwargs = dict(self.kwargs)
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return kwargs


class FakeEmbeddings(Embeddings):
    """Deterministic, network-free stand-in for a real embedding model.
    Encodes the text length into the vector so different texts get distinct
    (but reproducible) embeddings; dimension is fixed per instance so tests
    can simulate two "different models" by using two different dimensions.
    """

    def __init__(self, dim: int = 4):
        self.dim = dim

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        seed = sum(text.encode())
        return [((seed + i) % 97) / 97.0 for i in range(self.dim)]


@pytest.fixture(autouse=True)
def _patch_embedding_backend(monkeypatch):
    """Every test gets a fresh FakeEmbeddings via models.get_embedding_model,
    keyed off model name so two different "models" (by name) get two
    different, mutually-incompatible embedding dimensions -- mirroring a
    real embedding-model swap (e.g. Qwen 4096-dim -> Nemotron 2048-dim)."""

    dims_by_name = {"model-a": 4, "model-b": 6}

    def fake_get_embedding_model(provider, name, model_config=None, **kwargs):
        return FakeEmbeddings(dim=dims_by_name.get(name, 4))

    monkeypatch.setattr(memory_module.models, "get_embedding_model", fake_get_embedding_model)
    # Memory.index is a module-level cache keyed by subdir; make sure one
    # test's cached db can't leak into the next.
    memory_module.Memory.index = {}


def _make_docs(n: int) -> dict[str, Document]:
    return {f"id-{i}": Document(page_content=f"document number {i}") for i in range(n)}


def test_load_rebuild_checkpoint_returns_nothing_when_absent(tmp_path):
    db, resumed_ids = Memory._load_rebuild_checkpoint(
        str(tmp_path), FakeModelConfig("other", "model-a"), FakeEmbeddings(4)
    )
    assert db is None
    assert resumed_ids == set()


def test_write_then_load_rebuild_checkpoint_round_trips(tmp_path):
    embedder = FakeEmbeddings(4)
    index = memory_module.faiss.IndexFlatIP(embedder.dim)
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    db = MyFaiss(
        embedding_function=embedder,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    docs = _make_docs(3)
    db.add_documents(documents=list(docs.values()), ids=list(docs.keys()))

    model_config = FakeModelConfig("other", "model-a")
    Memory._write_rebuild_checkpoint(db, str(tmp_path), model_config)

    assert (tmp_path / "index.rebuilding.faiss").exists()
    assert (tmp_path / "index.rebuilding.pkl").exists()
    meta = json.loads((tmp_path / "index.rebuilding.json").read_text())
    assert meta == {"model_provider": "other", "model_name": "model-a", "model_kwargs": {}}

    loaded_db, resumed_ids = Memory._load_rebuild_checkpoint(
        str(tmp_path), model_config, embedder
    )
    assert loaded_db is not None
    assert resumed_ids == set(docs.keys())


def test_load_rebuild_checkpoint_rejects_different_model(tmp_path):
    """The core bug fix: a checkpoint recorded for one embedding model must
    never be resumed into when the currently-configured model is different
    -- even though both files are present and loadable, the vectors are from
    an incompatible embedding space."""
    embedder_a = FakeEmbeddings(4)
    index = memory_module.faiss.IndexFlatIP(embedder_a.dim)
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    db = MyFaiss(
        embedding_function=embedder_a,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    docs = _make_docs(3)
    db.add_documents(documents=list(docs.values()), ids=list(docs.keys()))
    Memory._write_rebuild_checkpoint(db, str(tmp_path), FakeModelConfig("other", "model-a"))

    # A DIFFERENT model is now the target (different name -> different dim
    # via the fixture's fake backend).
    embedder_b = FakeEmbeddings(6)
    loaded_db, resumed_ids = Memory._load_rebuild_checkpoint(
        str(tmp_path), FakeModelConfig("other", "model-b"), embedder_b
    )
    assert loaded_db is None
    assert resumed_ids == set()
    # The stale checkpoint is left in place (only initialize()'s caller
    # decides to overwrite/clear it, once it actually rebuilds); this helper
    # only refuses to *use* it.
    assert (tmp_path / "index.rebuilding.faiss").exists()


def test_load_rebuild_checkpoint_discards_when_meta_missing(tmp_path):
    """A checkpoint with no model marker (e.g. left by a version of this
    code predating the marker, or a corrupted write) must not be trusted
    either -- treat it the same as a model mismatch, not as a free pass."""
    embedder = FakeEmbeddings(4)
    index = memory_module.faiss.IndexFlatIP(embedder.dim)
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    db = MyFaiss(
        embedding_function=embedder,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    docs = _make_docs(2)
    db.add_documents(documents=list(docs.values()), ids=list(docs.keys()))
    db.save_local(folder_path=str(tmp_path), index_name=Memory._REBUILD_INDEX_NAME)
    # deliberately no .json meta file written

    loaded_db, resumed_ids = Memory._load_rebuild_checkpoint(
        str(tmp_path), FakeModelConfig("other", "model-a"), embedder
    )
    assert loaded_db is None
    assert resumed_ids == set()


def test_clear_rebuild_checkpoint_removes_all_three_files(tmp_path):
    embedder = FakeEmbeddings(4)
    index = memory_module.faiss.IndexFlatIP(embedder.dim)
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    db = MyFaiss(
        embedding_function=embedder,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    Memory._write_rebuild_checkpoint(db, str(tmp_path), FakeModelConfig("other", "model-a"))
    assert (tmp_path / "index.rebuilding.faiss").exists()

    Memory._clear_rebuild_checkpoint(str(tmp_path))

    assert not (tmp_path / "index.rebuilding.faiss").exists()
    assert not (tmp_path / "index.rebuilding.pkl").exists()
    assert not (tmp_path / "index.rebuilding.json").exists()


def test_clear_rebuild_checkpoint_is_a_noop_when_absent(tmp_path):
    # Must not raise just because there was nothing to resume from.
    Memory._clear_rebuild_checkpoint(str(tmp_path))


class _NullLogItem:
    def stream(self, **kwargs):
        pass

    def update(self, **kwargs):
        pass


def _initialize(tmp_path, monkeypatch, model_config, in_memory=False):
    monkeypatch.setattr(memory_module, "abs_db_dir", lambda subdir: str(tmp_path))
    return Memory.initialize(_NullLogItem(), model_config, "default", in_memory)


def test_initialize_creates_fresh_index_when_none_exists(tmp_path, monkeypatch):
    db, created = _initialize(tmp_path, monkeypatch, FakeModelConfig("other", "model-a"))
    assert created is True
    assert db.get_all_docs() == {}
    assert (tmp_path / "index.faiss").exists()
    assert not (tmp_path / "index.rebuilding.faiss").exists()


def test_initialize_resumes_interrupted_rebuild_under_same_model(tmp_path, monkeypatch):
    """End-to-end: an existing (stale-model) index plus a partial rebuild
    checkpoint for the CURRENT model must result in only the not-yet-
    embedded documents being (re)embedded, not all of them."""
    monkeypatch.setattr(memory_module, "abs_db_dir", lambda subdir: str(tmp_path))

    old_embedder = FakeEmbeddings(4)  # pretend this is "model-a" too, just stale content
    old_docs = _make_docs(5)
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    old_index = memory_module.faiss.IndexFlatIP(old_embedder.dim)
    old_db = MyFaiss(
        embedding_function=old_embedder,
        index=old_index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    old_db.add_documents(documents=list(old_docs.values()), ids=list(old_docs.keys()))
    # This is the STALE on-disk index: recorded under a DIFFERENT model name
    # so initialize() decides a reindex is needed.
    Memory._save_db_file(old_db, "default")
    memory_module.files.write_file(
        memory_module.files.get_abs_path(str(tmp_path), "embedding.json"),
        json.dumps({"model_provider": "other", "model_name": "stale-model"}),
    )

    # A partial rebuild already embedded the first 3 of those 5 documents,
    # under the model we're about to target ("model-a") -- simulating a
    # crash partway through a previous reindex attempt.
    partial_ids = list(old_docs.keys())[:3]
    partial_index = memory_module.faiss.IndexFlatIP(4)
    partial_db = MyFaiss(
        embedding_function=FakeEmbeddings(4),
        index=partial_index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    partial_db.add_documents(
        documents=[old_docs[i] for i in partial_ids], ids=partial_ids
    )
    Memory._write_rebuild_checkpoint(
        partial_db, str(tmp_path), FakeModelConfig("other", "model-a")
    )

    added_calls = []
    original_add_documents = MyFaiss.add_documents

    def spy_add_documents(self, documents, ids=None, **kwargs):
        added_calls.append(list(ids or []))
        return original_add_documents(self, documents, ids=ids, **kwargs)

    monkeypatch.setattr(MyFaiss, "add_documents", spy_add_documents)

    db, created = Memory.initialize(
        _NullLogItem(), FakeModelConfig("other", "model-a"), "default", False
    )

    assert created is True
    # Only the 2 documents NOT already in the checkpoint were (re)embedded.
    all_added_ids = {i for batch in added_calls for i in batch}
    assert all_added_ids == set(old_docs.keys()) - set(partial_ids)
    # The final index nonetheless contains all 5 original documents.
    assert set(db.get_all_docs().keys()) == set(old_docs.keys())
    # The checkpoint is cleaned up once the rebuild completes successfully.
    assert not (tmp_path / "index.rebuilding.faiss").exists()
    # The final embedding.json now reflects the model we just rebuilt under.
    final_meta = json.loads((tmp_path / "embedding.json").read_text())
    assert final_meta == {"model_provider": "other", "model_name": "model-a"}


def test_initialize_discards_stale_checkpoint_when_model_changed_again(tmp_path, monkeypatch):
    """The scenario this fix exists for: a rebuild was interrupted, then the
    target embedding model changed AGAIN before the next attempt. The stale
    checkpoint (built for the now-abandoned intermediate model) must be
    discarded, not resumed into -- resuming would otherwise mix embedding
    spaces or crash on a FAISS dimension mismatch the moment a new batch is
    added."""
    monkeypatch.setattr(memory_module, "abs_db_dir", lambda subdir: str(tmp_path))

    old_docs = _make_docs(4)
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    old_index = memory_module.faiss.IndexFlatIP(4)
    old_db = MyFaiss(
        embedding_function=FakeEmbeddings(4),
        index=old_index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    old_db.add_documents(documents=list(old_docs.values()), ids=list(old_docs.keys()))
    Memory._save_db_file(old_db, "default")
    memory_module.files.write_file(
        memory_module.files.get_abs_path(str(tmp_path), "embedding.json"),
        json.dumps({"model_provider": "other", "model_name": "stale-model"}),
    )

    # An interrupted rebuild checkpoint exists, but it was for "model-a"
    # (dim=4) -- NOT the model we're now targeting ("model-b", dim=6).
    partial_index = memory_module.faiss.IndexFlatIP(4)
    partial_db = MyFaiss(
        embedding_function=FakeEmbeddings(4),
        index=partial_index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    partial_db.add_documents(
        documents=[list(old_docs.values())[0]], ids=[list(old_docs.keys())[0]]
    )
    Memory._write_rebuild_checkpoint(
        partial_db, str(tmp_path), FakeModelConfig("other", "model-a")
    )

    # Must not raise (e.g. a FAISS "assert d == self.d" dimension error from
    # blindly adding dim=6 vectors into the dim=4 stale checkpoint index).
    db, created = Memory.initialize(
        _NullLogItem(), FakeModelConfig("other", "model-b"), "default", False
    )

    assert created is True
    assert set(db.get_all_docs().keys()) == set(old_docs.keys())
    assert db.index.d == 6
    final_meta = json.loads((tmp_path / "embedding.json").read_text())
    assert final_meta == {"model_provider": "other", "model_name": "model-b"}


def test_checkpoint_signature_excludes_api_key(tmp_path):
    """A credential rotation alone (same provider/name/other-kwargs, only
    api_key differs) must not invalidate an otherwise-matching checkpoint --
    it has no bearing on the embedding output, and the signature is
    persisted to disk in the memory dir where a plaintext key doesn't
    belong."""
    embedder = FakeEmbeddings(4)
    index = memory_module.faiss.IndexFlatIP(embedder.dim)
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    db = MyFaiss(
        embedding_function=embedder,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    docs = _make_docs(2)
    db.add_documents(documents=list(docs.values()), ids=list(docs.keys()))
    Memory._write_rebuild_checkpoint(
        db, str(tmp_path), FakeModelConfig("other", "model-a", api_key="old-secret-123")
    )

    meta = json.loads((tmp_path / "index.rebuilding.json").read_text())
    assert "old-secret-123" not in json.dumps(meta)

    loaded_db, resumed_ids = Memory._load_rebuild_checkpoint(
        str(tmp_path),
        FakeModelConfig("other", "model-a", api_key="rotated-secret-456"),
        embedder,
    )
    assert loaded_db is not None
    assert resumed_ids == set(docs.keys())


def test_checkpoint_signature_rejects_dimension_affecting_kwarg_change(tmp_path):
    """The bug the automated review caught: provider+name alone aren't
    enough to key the checkpoint on. A kwarg that changes the embedder's
    actual output (e.g. an OpenAI-style `dimensions` override) must be part
    of the signature, or a checkpoint built under the old kwargs gets
    resumed into under the new ones -- silently mixing embedding spaces."""
    embedder = FakeEmbeddings(4)
    index = memory_module.faiss.IndexFlatIP(embedder.dim)
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    db = MyFaiss(
        embedding_function=embedder,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    docs = _make_docs(2)
    db.add_documents(documents=list(docs.values()), ids=list(docs.keys()))
    Memory._write_rebuild_checkpoint(
        db, str(tmp_path), FakeModelConfig("other", "model-a", kwargs={"dimensions": 1536})
    )

    loaded_db, resumed_ids = Memory._load_rebuild_checkpoint(
        str(tmp_path),
        FakeModelConfig("other", "model-a", kwargs={"dimensions": 512}),
        embedder,
    )
    assert loaded_db is None
    assert resumed_ids == set()


def test_initialize_does_not_clear_checkpoint_before_final_save_succeeds(
    tmp_path, monkeypatch
):
    """The other bug the automated review caught: clearing the rebuild
    checkpoint must happen strictly AFTER the final index/meta are durably
    written. If `_save_db_file` (or anything after it) fails or the process
    is killed first, the checkpoint must still be there to resume from --
    otherwise that crash loses both the checkpoint and the final index."""
    monkeypatch.setattr(memory_module, "abs_db_dir", lambda subdir: str(tmp_path))

    # A genuine reindex has to be triggered for the batch loop (and its
    # checkpoint writes) to run at all -- set up a stale-model existing
    # index, same as the other end-to-end tests.
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy

    old_docs = _make_docs(2)
    old_index = memory_module.faiss.IndexFlatIP(4)
    old_db = MyFaiss(
        embedding_function=FakeEmbeddings(4),
        index=old_index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.COSINE,
        relevance_score_fn=Memory._cosine_normalizer,
    )
    old_db.add_documents(documents=list(old_docs.values()), ids=list(old_docs.keys()))
    Memory._save_db_file(old_db, "default")
    memory_module.files.write_file(
        memory_module.files.get_abs_path(str(tmp_path), "embedding.json"),
        json.dumps({"model_provider": "other", "model_name": "stale-model"}),
    )

    def boom(*args, **kwargs):
        raise RuntimeError("simulated crash during final save")

    monkeypatch.setattr(Memory, "_save_db_file", staticmethod(boom))

    with pytest.raises(RuntimeError, match="simulated crash"):
        Memory.initialize(
            _NullLogItem(), FakeModelConfig("other", "model-a"), "default", False
        )

    # The rebuild checkpoint (written by the batch loop before the crash)
    # must still be on disk -- it's the only resumable state left.
    assert (tmp_path / "index.rebuilding.faiss").exists()
    assert (tmp_path / "index.rebuilding.json").exists()
