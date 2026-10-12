from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

import models


def test_framework_imports_do_not_load_embedding_or_speech_runtimes():
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
import models
import preload
for name in (
    'sentence_transformers', 'torch', 'whisper',
    'plugins._kokoro_tts.helpers.runtime',
    'plugins._whisper_stt.helpers.runtime',
):
    assert name not in sys.modules, name
"""],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "LITELLM_LOCAL_MODEL_COST_MAP": "True"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def _clear_local_embedding_models():
    with models._LOCAL_EMBEDDING_MODELS_LOCK:
        models._LOCAL_EMBEDDING_MODELS.clear()


@pytest.fixture
def startup_runtime(monkeypatch):
    import run_ui

    monkeypatch.setattr(run_ui, "configure_process_environment", lambda: None)
    monkeypatch.setattr(run_ui, "run_migration_checks", lambda: None)
    monkeypatch.setattr(run_ui, "prepare_web_runtime", lambda: (None, "localhost", 0))
    monkeypatch.setattr(run_ui, "start_web_server", lambda *_args: None)
    return run_ui


@pytest.mark.parametrize("skip_init", [False, True])
def test_runtime_preload_overlaps_chat_restoration_within_extension_hooks(monkeypatch, skip_init, startup_runtime):
    import run_ui

    calls = []

    def extension_hook(point, agent, data):
        if not point.startswith("_functions/run_ui/init_a0/"):
            return
        calls.append(point.rsplit("/", 1)[-1])
        if skip_init and point.endswith("/start"):
            data["result"] = None

    monkeypatch.setattr(run_ui.extension, "call_extensions_sync", extension_hook)
    def preload():
        calls.append("preload")

        def wait(timeout):
            assert timeout == 10
            calls.append("preload_ready")

        return SimpleNamespace(result_sync=wait)

    monkeypatch.setattr(run_ui.initialize, "initialize_preload", preload)
    monkeypatch.setattr(
        run_ui.initialize, "initialize_chats",
        lambda: SimpleNamespace(result_sync=lambda: calls.append("chats")),
    )
    monkeypatch.setattr(run_ui.initialize, "initialize_mcp", lambda: calls.append("mcp"))
    monkeypatch.setattr(run_ui.initialize, "initialize_job_loop", lambda: calls.append("jobs"))

    run_ui.run()

    assert calls == (["start", "end"] if skip_init else [
        "start", "preload", "chats", "end", "preload_ready", "mcp", "jobs",
    ])


@pytest.mark.parametrize("error", [None, TimeoutError(), RuntimeError("preload failed")])
def test_runtime_preload_wait_remains_best_effort(monkeypatch, error, startup_runtime):
    import run_ui

    calls = []
    errors = []

    def wait(timeout):
        assert timeout == 10
        raise error

    monkeypatch.setattr(run_ui.extension, "call_extensions_sync", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        run_ui.initialize, "initialize_preload",
        lambda: SimpleNamespace(result_sync=wait) if error is not None else None,
    )
    monkeypatch.setattr(
        run_ui.initialize, "initialize_chats",
        lambda: SimpleNamespace(result_sync=lambda: calls.append("chats")),
    )
    monkeypatch.setattr(run_ui.initialize, "initialize_mcp", lambda: calls.append("mcp"))
    monkeypatch.setattr(run_ui.initialize, "initialize_job_loop", lambda: calls.append("jobs"))
    monkeypatch.setattr(run_ui, "PrintStyle", lambda: SimpleNamespace(print=lambda _: None, error=errors.append))

    run_ui.run()

    assert calls == ["chats", "mcp", "jobs"]
    assert errors == (["Error waiting for preload: preload failed"] if isinstance(error, RuntimeError) else [])


@pytest.mark.parametrize("blocked_stage", ["construction", "encoding"])
def test_startup_continues_after_ten_seconds_with_model_still_loading(monkeypatch, blocked_stage, record_property, startup_runtime):
    import preload
    import run_ui
    from helpers import persist_chat
    from helpers.defer import EventLoopThread
    from plugins._model_config.helpers import model_config

    release = threading.Event()
    blocked = threading.Event()
    chats_loaded = threading.Event()
    warmed = threading.Event()
    preload_done = threading.Event()
    later_startup = []
    errors = []
    constructions = []
    config = models.ModelConfig(models.ModelType.EMBEDDING, "huggingface", "sentence-transformers/timeout-test")

    def extension_hook(point, agent, data):
        if point.endswith("/initialize_preload/end"):
            data["result"].add_done_callback(lambda _: preload_done.set())

    def hold():
        blocked.set()
        assert release.wait(20), "Test did not release the model operation"

    class HeldModel:
        def __init__(self, name, **kwargs):
            constructions.append(name)
            if blocked_stage == "construction":
                hold()

        def encode(self, inputs, **kwargs):
            if blocked_stage == "encoding":
                hold()
            warmed.set()
            return [[1.0] for _ in inputs]

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=HeldModel))
    monkeypatch.setattr(model_config, "get_embedding_model_config_object", lambda: config)
    monkeypatch.setattr(models, "get_provider_config", lambda *_args: None)
    monkeypatch.setattr(models, "get_api_key_raw", lambda *_args: "None")
    monkeypatch.setattr(run_ui.extension, "call_extensions_sync", extension_hook)
    monkeypatch.setattr(persist_chat, "load_tmp_chats", chats_loaded.set)
    monkeypatch.setattr(run_ui.initialize, "initialize_mcp", lambda: later_startup.append("mcp"))
    monkeypatch.setattr(run_ui.initialize, "initialize_job_loop", lambda: later_startup.append("jobs"))
    monkeypatch.setattr(preload, "PrintStyle", lambda: SimpleNamespace(print=lambda _: None, error=errors.append))
    monkeypatch.setattr(run_ui, "PrintStyle", lambda: SimpleNamespace(print=lambda _: None, error=errors.append))
    _clear_local_embedding_models()

    # Release blocked work even if a regression removes the startup timeout.
    with ThreadPoolExecutor(max_workers=1) as pool:
        started = time.monotonic()
        startup = pool.submit(run_ui.run)
        try:
            assert blocked.wait(3)
            assert chats_loaded.wait(3)
            startup.result(timeout=12)
            elapsed = time.monotonic() - started
            record_property("startup_wait_seconds", round(elapsed, 3))
            assert 9.5 <= elapsed < 13, elapsed
            assert later_startup == ["mcp", "jobs"]
            assert not warmed.is_set()
            assert not release.is_set()

            release.set()
            assert preload_done.wait(3)
            assert warmed.is_set()
            runtime_model = models.get_embedding_model(config.provider, config.name, model_config=config)
            assert runtime_model.embed_query("first message") == [1.0]
            assert constructions == ["timeout-test"]
            assert not errors
        finally:
            release.set()
            startup.result(timeout=12)
            assert preload_done.wait(3)
            EventLoopThread().terminate()
            _clear_local_embedding_models()


@pytest.mark.parametrize("scenario", ["cached", "missing", "broken", "remote", "busy_restoration"])
def test_real_preload_startup_handles_ready_or_unavailable_models(monkeypatch, scenario, record_property, startup_runtime):
    import preload
    import run_ui
    from helpers import persist_chat
    from helpers.defer import EventLoopThread
    from plugins._model_config.helpers import model_config

    chats_started = threading.Event()
    release_chats = threading.Event()
    model_constructed = threading.Event()
    preload_done = threading.Event()
    constructions = []
    errors = []
    calls = []
    config = models.ModelConfig(
        models.ModelType.EMBEDDING,
        "openai" if scenario == "remote" else "huggingface",
        "sentence-transformers/startup-test",
    )

    class Model:
        def __init__(self, name, **kwargs):
            constructions.append(name)
            if scenario in {"missing", "broken"}:
                raise OSError(scenario + " model")
            model_constructed.set()

        def encode(self, inputs, **kwargs):
            return [[1.0] for _ in inputs]

    def restore_chats():
        chats_started.set()
        if scenario == "busy_restoration":
            assert release_chats.wait(5)

    def extension_hook(point, agent, data):
        if point.endswith("/initialize_preload/end"):
            data["result"].add_done_callback(lambda _: preload_done.set())

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Model))
    monkeypatch.setattr(models, "get_provider_config", lambda *_args: None)
    monkeypatch.setattr(models, "get_api_key_raw", lambda *_args: "None")
    monkeypatch.setattr(model_config, "get_embedding_model_config_object", lambda: config)
    monkeypatch.setattr(run_ui.extension, "call_extensions_sync", extension_hook)
    monkeypatch.setattr(persist_chat, "load_tmp_chats", restore_chats)
    monkeypatch.setattr(run_ui.initialize, "initialize_mcp", lambda: calls.append("mcp"))
    monkeypatch.setattr(run_ui.initialize, "initialize_job_loop", lambda: calls.append("jobs"))
    monkeypatch.setattr(preload, "PrintStyle", lambda: SimpleNamespace(print=lambda _: None, error=errors.append))
    monkeypatch.setattr(run_ui, "PrintStyle", lambda: SimpleNamespace(print=lambda _: None, error=errors.append))
    _clear_local_embedding_models()
    if scenario == "cached":
        models.get_embedding_model(config.provider, config.name)

    with ThreadPoolExecutor(max_workers=1) as pool:
        started = time.monotonic()
        startup = pool.submit(run_ui.run)
        try:
            assert chats_started.wait(2)
            if scenario == "busy_restoration":
                assert model_constructed.wait(2)
                assert not startup.done()
                release_chats.set()
            startup.result(timeout=2)
            elapsed = time.monotonic() - started
            record_property("startup_wait_seconds", round(elapsed, 3))
            assert elapsed < 2, elapsed
            assert preload_done.wait(2)
            assert calls == ["mcp", "jobs"]
            assert len(constructions) == (0 if scenario == "remote" else 1)
            assert errors == (["Error in preload: " + scenario + " model"] if scenario in {"missing", "broken"} else [])
        finally:
            release_chats.set()
            startup.result(timeout=12)
            assert preload_done.wait(2)
            EventLoopThread().terminate()
            _clear_local_embedding_models()


def test_local_embedding_preload_is_reused_with_runtime_model_config(monkeypatch):
    created = []

    class FakeSentenceTransformer:
        def __init__(self, model, **kwargs):
            created.append((model, kwargs))

    monkeypatch.setitem(
        sys.modules, "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    _clear_local_embedding_models()

    try:
        preload = models.LocalSentenceTransformerWrapper(
            "huggingface",
            "sentence-transformers/example",
            device="cpu",
            model_kwargs={"revision": "stable", "trust_remote_code": False},
        )
        runtime_config = SimpleNamespace(name="runtime")
        runtime = models.LocalSentenceTransformerWrapper(
            "huggingface",
            "sentence-transformers/example",
            model_config=runtime_config,
            model_kwargs={"trust_remote_code": False, "revision": "stable"},
            device="cpu",
        )

        assert runtime.model is preload.model
        assert runtime.a0_model_conf is runtime_config
        assert created == [
            (
                "example",
                {
                    "device": "cpu",
                    "model_kwargs": {
                        "revision": "stable",
                        "trust_remote_code": False,
                    },
                },
            )
        ]
    finally:
        _clear_local_embedding_models()


def test_local_embedding_cache_tracks_effective_constructor_options(monkeypatch):
    created = []

    class FakeSentenceTransformer:
        def __init__(self, model, **kwargs):
            created.append((model, kwargs))

    monkeypatch.setitem(
        sys.modules, "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    _clear_local_embedding_models()

    try:
        first = models.LocalSentenceTransformerWrapper(
            "huggingface", "sentence-transformers/example", device="cpu"
        )
        second = models.LocalSentenceTransformerWrapper(
            "huggingface", "sentence-transformers/example", device="cuda"
        )

        assert second.model is not first.model
        assert created == [
            ("example", {"device": "cpu"}),
            ("example", {"device": "cuda"}),
        ]
        assert len(models._LOCAL_EMBEDDING_MODELS) == 1
    finally:
        _clear_local_embedding_models()


def test_concurrent_preload_and_runtime_share_one_model(monkeypatch):
    created = []
    construction_started = threading.Event()
    release_construction = threading.Event()

    class FakeSentenceTransformer:
        def __init__(self, model, **kwargs):
            created.append((model, kwargs))
            construction_started.set()
            assert release_construction.wait(timeout=2)

    monkeypatch.setitem(
        sys.modules, "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    _clear_local_embedding_models()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                models.LocalSentenceTransformerWrapper,
                "huggingface",
                "sentence-transformers/example",
            )
            assert construction_started.wait(timeout=2)
            second = executor.submit(
                models.LocalSentenceTransformerWrapper,
                "huggingface",
                "sentence-transformers/example",
            )
            release_construction.set()

            assert second.result().model is first.result().model

        assert created == [("example", {})]
    finally:
        release_construction.set()
        _clear_local_embedding_models()


def test_failed_model_change_keeps_the_working_cached_model(monkeypatch):
    created = []

    class FakeSentenceTransformer:
        def __init__(self, model, **kwargs):
            created.append((model, kwargs))
            if model == "broken":
                raise RuntimeError("model unavailable")

    monkeypatch.setitem(
        sys.modules, "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    _clear_local_embedding_models()

    try:
        working = models.LocalSentenceTransformerWrapper(
            "huggingface", "sentence-transformers/working"
        )
        with pytest.raises(RuntimeError, match="model unavailable"):
            models.LocalSentenceTransformerWrapper(
                "huggingface", "sentence-transformers/broken"
            )
        reused = models.LocalSentenceTransformerWrapper(
            "huggingface", "sentence-transformers/working"
        )

        assert reused.model is working.model
        assert created == [("working", {}), ("broken", {})]
    finally:
        _clear_local_embedding_models()


@pytest.mark.asyncio
async def test_preload_uses_the_runtime_embedding_configuration(monkeypatch):
    import preload
    from plugins._model_config.helpers import model_config

    config = SimpleNamespace(
        provider="huggingface",
        name="sentence-transformers/example",
        build_kwargs=lambda: {"device": "cpu"},
    )
    calls = []
    embedded = []
    loop_thread = threading.get_ident()

    class FakeEmbeddings:
        async def aembed_query(self, text):
            embedded.append(text)

    def get_embedding_model(provider, name, **kwargs):
        assert threading.get_ident() != loop_thread
        calls.append((provider, name, kwargs))
        return FakeEmbeddings()

    monkeypatch.setattr(
        model_config, "get_embedding_model_config_object", lambda: config
    )
    monkeypatch.setattr(preload.models, "get_embedding_model", get_embedding_model)

    await preload.preload()

    assert calls == [
        (
            "huggingface",
            "sentence-transformers/example",
            {"model_config": config, "device": "cpu"},
        )
    ]
    assert embedded == ["test"]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "huggingface"])
async def test_preload_skips_remote_models_and_contains_local_failures(monkeypatch, provider):
    import preload
    from plugins._model_config.helpers import model_config

    config = SimpleNamespace(provider=provider, name="example", build_kwargs=lambda: {})
    calls = []
    errors = []

    def fail_embedding(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(model_config, "get_embedding_model_config_object", lambda: config)
    monkeypatch.setattr(models, "get_embedding_model", fail_embedding)
    monkeypatch.setattr(
        preload, "PrintStyle",
        lambda: SimpleNamespace(print=lambda _: None, error=errors.append),
    )

    await preload.preload()

    if provider == "huggingface":
        assert calls == [("huggingface", "example")]
        assert errors == ["Error in preload: model unavailable"]
    else:
        assert calls == []
        assert errors == []


def test_watchdog_setup_overlaps_real_warmup_before_mcp_and_http(monkeypatch, startup_runtime):
    import preload
    import run_ui
    from helpers import persist_chat
    from helpers.defer import EventLoopThread
    from plugins._model_config.helpers import model_config

    model_started = threading.Event()
    release_model = threading.Event()
    preload_done = threading.Event()
    calls = []
    config = models.ModelConfig(
        models.ModelType.EMBEDDING, "huggingface", "sentence-transformers/overlap-test"
    )

    class Model:
        def __init__(self, *_args, **_kwargs):
            model_started.set()
            assert release_model.wait(5)

        def encode(self, inputs, **_kwargs):
            calls.append("model_warmed")
            return [[1.0] for _ in inputs]

    def extension_hook(point, agent, data):
        if point.endswith("/initialize_preload/end"):
            data["result"].add_done_callback(lambda _: preload_done.set())
        if point.endswith("/init_a0/end"):
            assert model_started.wait(2)
            assert not preload_done.is_set()
            calls.append("watchdogs_start")
            release_model.set()
            assert preload_done.wait(2)
            calls.append("watchdogs_end")

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Model))
    monkeypatch.setattr(model_config, "get_embedding_model_config_object", lambda: config)
    monkeypatch.setattr(models, "get_provider_config", lambda *_args: None)
    monkeypatch.setattr(models, "get_api_key_raw", lambda *_args: "None")
    monkeypatch.setattr(run_ui.extension, "call_extensions_sync", extension_hook)
    monkeypatch.setattr(persist_chat, "load_tmp_chats", lambda: calls.append("chats"))
    monkeypatch.setattr(run_ui.initialize, "initialize_mcp", lambda: calls.append("mcp"))
    monkeypatch.setattr(run_ui.initialize, "initialize_job_loop", lambda: calls.append("jobs"))
    monkeypatch.setattr(run_ui, "start_web_server", lambda *_args: calls.append("http"))
    _clear_local_embedding_models()
    try:
        run_ui.run()
        assert calls == ["chats", "watchdogs_start", "model_warmed", "watchdogs_end", "mcp", "jobs", "http"]
    finally:
        release_model.set()
        assert preload_done.wait(2)
        EventLoopThread().terminate()
        _clear_local_embedding_models()


def test_runtime_accepts_extension_skip_result(monkeypatch, startup_runtime):
    import run_ui

    calls = []
    monkeypatch.setattr(run_ui, "init_a0", lambda: True)
    monkeypatch.setattr(run_ui, "start_web_server", lambda *_args: calls.append("http"))
    run_ui.run()
    assert calls == ["http"]
