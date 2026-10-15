"""Embedding routing contracts.

Regression tests for the model-config read-boundary routing rule: keyless
huggingface embeddings without an api_base normalize to the local
sentence-transformers route; an explicit api_base opts into remote. Covers
the 2026-10-15 incident where an unprefixed local name silently routed to
the remote HF Inference API and failed mid-turn.
"""

from pathlib import Path
import sys
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.setdefault("giturlparse", SimpleNamespace(parse=lambda *a, **k: None))
sys.modules.setdefault("whisper", SimpleNamespace(load_model=lambda *a, **k: None))

import pytest

from plugins._model_config.helpers import model_config


def _resolve(monkeypatch, embedding_model):
    monkeypatch.setattr(
        model_config,
        "get_effective_config",
        lambda agent=None: {"embedding_model": dict(embedding_model)},
    )
    return model_config.get_embedding_model_config()


def test_unprefixed_local_name_routes_local(monkeypatch):
    cfg = _resolve(
        monkeypatch,
        {"provider": "huggingface", "name": "BAAI/bge-small-en-v1.5"},
    )
    assert cfg["provider"] == "huggingface"
    assert cfg["name"] == "sentence-transformers/BAAI/bge-small-en-v1.5"


def test_prefixed_name_unchanged(monkeypatch):
    cfg = _resolve(
        monkeypatch,
        {"provider": "huggingface", "name": "sentence-transformers/BAAI/bge-small-en-v1.5"},
    )
    assert cfg["name"] == "sentence-transformers/BAAI/bge-small-en-v1.5"


def test_explicit_api_base_keeps_remote_route(monkeypatch):
    cfg = _resolve(
        monkeypatch,
        {"provider": "huggingface", "name": "BAAI/bge-small-en-v1.5", "api_base": "https://api.example.com"},
    )
    assert cfg["name"] == "BAAI/bge-small-en-v1.5"


def test_huggingface_org_prefix_stripped_and_local(monkeypatch):
    cfg = _resolve(
        monkeypatch,
        {"provider": "huggingface", "name": "huggingface/BAAI/bge-small-en-v1.5"},
    )
    assert cfg["name"] == "sentence-transformers/BAAI/bge-small-en-v1.5"


def test_legacy_minilm_alias_still_prefixed(monkeypatch):
    cfg = _resolve(
        monkeypatch,
        {"provider": "huggingface", "name": "all-MiniLM-L6-v2"},
    )
    assert cfg["name"] == "sentence-transformers/all-MiniLM-L6-v2"


def test_bare_prefix_with_weak_provider_becomes_huggingface(monkeypatch):
    cfg = _resolve(
        monkeypatch,
        {"provider": "openai", "name": "sentence-transformers/all-MiniLM-L6-v2"},
    )
    assert cfg["provider"] == "huggingface"
    assert cfg["name"] == "sentence-transformers/all-MiniLM-L6-v2"


def test_hf_token_presence_is_not_a_remote_signal(monkeypatch):
    # An HF token also authorizes local model downloads, so key presence
    # alone must not opt into the remote HF Inference API; only api_base
    # does.
    monkeypatch.setenv("API_KEY_HUGGINGFACE", "hf_dummy_token")
    cfg = _resolve(
        monkeypatch,
        {"provider": "huggingface", "name": "BAAI/bge-small-en-v1.5"},
    )
    assert cfg["name"] == "sentence-transformers/BAAI/bge-small-en-v1.5"


def test_empty_name_is_untouched(monkeypatch):
    cfg = _resolve(monkeypatch, {"provider": "huggingface", "name": ""})
    assert cfg.get("name", "") == ""


def _isolate_core(monkeypatch):
    import models

    monkeypatch.setattr(models, "_merge_provider_defaults", lambda t, p, k: (p, k))
    return models


def test_core_wrapper_local_for_prefixed_name(monkeypatch):
    models = _isolate_core(monkeypatch)
    created = []

    class FakeLocal:
        def __init__(self, provider, model, model_config=None, **kw):
            created.append(model)

    monkeypatch.setattr(models, "LocalSentenceTransformerWrapper", FakeLocal)
    models.get_embedding_model("huggingface", "sentence-transformers/BAAI/bge-small-en-v1.5")
    # The core passes the prefixed name; the real wrapper strips the prefix
    # itself in its constructor.
    assert created == ["sentence-transformers/BAAI/bge-small-en-v1.5"]


def test_core_wrapper_remote_for_unprefixed_direct_call(monkeypatch):
    # The core wrapper stays provider-agnostic: alias repair is owned by the
    # model-config read boundary, so a direct unprefixed call remains remote.
    models = _isolate_core(monkeypatch)
    created = []

    class FakeRemote:
        def __init__(self, model, provider, model_config=None, **kw):
            created.append((provider, model))

    monkeypatch.setattr(models, "LiteLLMEmbeddingWrapper", FakeRemote)
    models.get_embedding_model("huggingface", "BAAI/bge-small-en-v1.5")
    assert created == [("huggingface", "BAAI/bge-small-en-v1.5")]
