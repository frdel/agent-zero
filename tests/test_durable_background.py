"""Detached inference receipts through real loopback SDK calls and PostgreSQL."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Event, Thread
import time
from types import SimpleNamespace
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import faiss_monkey_patch
import models
from agent import Agent, LoopData, UserMessage
from helpers.durable import background, codec, runtime, state_adapters
from test_durable_cluster import nodes, rig

PROJECT = Path(__file__).resolve().parents[1]
DSN = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")


@pytest.fixture
def provider():
    state = SimpleNamespace(requests=[], arrived=Event(), release=Event())
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.requests.append((self.path, value))
            state.arrived.set()
            state.release.wait(30)
            if self.path.endswith("embeddings"):
                inputs = value["input"] if isinstance(value["input"], list) else [value["input"]]
                reply = {"object": "list", "model": value["model"], "data": [{"object": "embedding", "index": index, "embedding": [1.0, 0.0]} for index, _ in enumerate(inputs)], "usage": {"prompt_tokens": 1, "total_tokens": 1}}
            else:
                text = str(value["messages"])
                response = ('["The user prefers deterministic project recovery with shared receipts."]' if "MEMORIZE" in text else
                            '{"upsert":[{"text":"The user prefers deterministic project recovery with shared receipts.","replace_ids":[]}]}' if "CONSOLIDATE" in text else
                            "[0]" if "FILTER" in text else "<ok/>" if "SAFETY" in text else "query subject")
                reply = {"id": "synthetic", "object": "chat.completion", "model": value["model"], "created": 1,
                         "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": response}}],
                         "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            data = json.dumps(reply).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    state.url = f"http://127.0.0.1:{server.server_port}/v1"
    state.model = models.LiteLLMChatWrapper("synthetic", "openai", api_key="fixture-only", api_base=state.url, a0_retry_attempts=0)
    try:
        yield state
    finally:
        state.release.set(); server.shutdown(); server.server_close(); thread.join(timeout=5)


@pytest.fixture
def task_turn(nodes, provider, monkeypatch, tmp_path):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("A0_DURABILITY_POSTGRES_DSN", DSN)
    monkeypatch.setenv("A0_DURABILITY_EXECUTION_ROOT", str(tmp_path / "jobs"))
    monkeypatch.setattr(Agent, "get_chat_model", lambda _: provider.model)
    monkeypatch.setattr(Agent, "get_utility_model", lambda _: provider.model)
    agent = nodes.rig.context.agent0
    from helpers.history import Message
    agent.loop_data = LoopData(iteration=1, user_message=Message(False, "Synthetic subject"))
    run = nodes.first.sync("admit", agent.context.id, "background-input", {}, codec.checkpoint(agent))
    assert nodes.first.sync("claim", run["run_id"])
    turn = runtime.Turn(nodes.first, agent, run)
    agent.context._durable_turn = turn
    nodes.first.contexts[run["run_id"]] = agent.context
    try:
        yield nodes, turn
    finally:
        for path in (tmp_path / "jobs" / "background").glob("*.broker.json"):
            try:
                os.kill(json.loads(path.read_bytes())["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass


async def _until(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline
        await asyncio.sleep(.02)


@pytest.mark.asyncio
async def test_pending_recall_restores_frozen_corpus_and_each_inference_receipt(task_turn, provider, monkeypatch):
    import faiss
    import numpy as np
    from langchain_core.documents import Document
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from plugins._memory.helpers.memory import Memory, MyFaiss
    from plugins._memory.extensions.python.message_loop_prompts_after import _50_recall_memories as recall
    from plugins._memory.extensions.python.message_loop_prompts_after._91_recall_wait import RecallWait
    nodes, turn = task_turn
    embedding = models.LiteLLMEmbeddingWrapper("synthetic-embedding", "openai", api_key="fixture-only", api_base=provider.url)
    index = faiss.IndexFlatIP(2); index.add(np.asarray([[1, 0], [0, 1]], dtype="float32"))
    db = MyFaiss(embedding, index, InMemoryDocstore({"main": Document("frozen durable fact", metadata={"id": "main", "area": "main"}),
                                                  "solution": Document("old solution", metadata={"id": "solution", "area": "solutions"})}), {0: "main", 1: "solution"})
    memory = Memory(db, "shared-memory")
    async def get(_):
        return memory
    monkeypatch.setattr(Memory, "get", staticmethod(get))
    monkeypatch.setattr(Memory, "_get_embedding_config", staticmethod(lambda _: models.ModelConfig(models.ModelType.EMBEDDING, "openai", "synthetic-embedding")))
    settings = {"memory_recall_enabled": True, "memory_recall_interval": 1, "memory_recall_delayed": True,
        "memory_recall_query_prep": True, "memory_recall_post_filter": True, "memory_recall_history_len": 1000,
        "memory_recall_memories_max_search": 5, "memory_recall_solutions_max_search": 5,
        "memory_recall_similarity_threshold": .6, "memory_recall_memories_max_result": 3, "memory_recall_solutions_max_result": 3}
    monkeypatch.setattr("helpers.plugins.get_plugin_config", lambda name, *args, **kwargs: settings if name == "_memory" else {})
    monkeypatch.setattr(recall, "get_recall_scope", lambda _: ("profile", "project", "shared-memory"))
    monkeypatch.setattr("plugins._memory.extensions.python.message_loop_prompts_after._91_recall_wait.get_recall_scope", recall.get_recall_scope)
    monkeypatch.setattr(Agent, "read_prompt", lambda self, name, **kwargs: "FILTER " + str(kwargs.get("memories", "")) if "filter" in name else "QUERY " + kwargs.get("message", ""))
    monkeypatch.setattr(Agent, "parse_prompt", lambda self, name, **kwargs: "FACTS " + kwargs.get("memories", kwargs.get("solutions", "")))
    await recall.RecallMemories(turn.agent).execute(loop_data=turn.agent.loop_data)
    task = turn.agent.get_data(recall.DATA_NAME_TASK)
    assert type(task) is background.TaskHandle
    await _until(provider.arrived.is_set)
    manifest = state_adapters.capture(turn.agent, mask=lambda value: value)
    nodes.first.sync("collect_resources", grace_seconds=0)
    # Current host data can change while the detached job searches its frozen,
    # authenticated corpus. Restoring the task must not query this new value.
    db.docstore._dict["main"].page_content = "changed on successor"
    nodes.first.sync("release", turn.run_id); assert nodes.second.sync("claim", turn.run_id)
    turn.owner = nodes.second
    state_adapters.restore(turn.agent, manifest, guard=lambda: nodes.second.sync("assert_owner", turn.run_id))
    provider.release.set()
    turn.agent.loop_data.iteration += 1
    await RecallWait(turn.agent).execute(loop_data=turn.agent.loop_data)
    assert turn.agent.loop_data.extras_persistent["memories"] == "FACTS frozen durable fact"
    assert turn.agent.get_data(recall.DATA_NAME_TASK) is None
    assert len(provider.requests) == 3  # query, embedding, filter, each once


@pytest.mark.asyncio
async def test_pending_checker_unknown_broker_outcome_never_passes_the_safety_gate(task_turn, provider):
    from plugins._infection_check.helpers.checker import InfectionChecker, DATA_KEY, DATA_KEY_PASSED
    nodes, turn = task_turn
    checker = InfectionChecker({"mode": "complete", "model": "utility", "prompt": "SAFETY"}, 1)
    checker.response_log = "Synthetic output"
    turn.agent.set_data(DATA_KEY, checker)
    checker.start_analysis(turn.agent)
    await _until(provider.arrived.is_set)
    manifest = state_adapters.capture(turn.agent, mask=lambda value: value)
    path = Path(os.environ["A0_DURABILITY_EXECUTION_ROOT"]) / "background" / (checker._task.reference["id"] + ".broker.json")
    os.kill(json.loads(path.read_bytes())["pid"], signal.SIGKILL)
    nodes.first.sync("release", turn.run_id); assert nodes.second.sync("claim", turn.run_id)
    turn.owner = nodes.second
    state_adapters.restore(turn.agent, manifest, guard=lambda: nodes.second.sync("assert_owner", turn.run_id))
    restored = turn.agent.get_data(DATA_KEY)
    # Await the original immutable request: there is no known verdict and no
    # permission to repeat this safety-model invocation.
    with pytest.raises(runtime.RecoveryHeld, match="background_inference_outcome_unknown"):
        await restored.gate(turn.agent, tool_name="response", tool_args={"text": "Synthetic"})
    assert not turn.agent.get_data(DATA_KEY_PASSED)
    assert len(provider.requests) == 1


def _worker(root):
    from helpers.durable.postgres import PostgresStore
    from helpers import extension, secrets as secret_helpers
    extension._get_extension_classes = lambda *args, **kwargs: []
    secret_helpers.get_secrets_manager = lambda _: SimpleNamespace(mask_values=lambda value: value)
    root = Path(root)
    with PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"], namespace=os.environ["A0_DURABILITY_JOB_NAMESPACE"]) as store:
        class Owner:
            distributed = True
            def __init__(self): self.store = store
            def sync(self, method, *args, **kwargs): return getattr(store, method)(*args, **kwargs)
        owner = Owner()
        run = store.admit("background-context", "input", {}, {"context": {"id": "background-context"}})
        assert store.claim(run["run_id"])
        context = SimpleNamespace(id="background-context")
        agent = SimpleNamespace(context=context, number=0)
        context._durable_turn = SimpleNamespace(agent=agent, owner=owner, run_id=run["run_id"])
        model = models.LiteLLMChatWrapper("synthetic", "openai", api_key="fixture-only", api_base=os.environ["A0_TEST_BACKGROUND_URL"])
        task = background.start(agent, "actual-worker", {"kind": "text", "model": "utility", "messages": [{"role": "human", "content": "query"}]}, {"utility": model})
        (root / "reference.json").write_text(json.dumps(task.reference))
        while True: time.sleep(1)


@pytest.mark.asyncio
async def test_automatic_memory_outbox_commits_once_and_refuses_concurrent_revision(task_turn, provider, monkeypatch):
    import faiss
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from plugins._memory.helpers.memory import Memory, MyFaiss
    from plugins._memory.helpers import durable_memory
    from plugins._memory.extensions.python.monologue_end._50_memorize_fragments import MemorizeMemories
    from helpers.durable import memorization
    nodes, turn = task_turn
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-only")
    embedding = models.LiteLLMEmbeddingWrapper("synthetic-embedding", "openai", api_key="fixture-only", api_base=provider.url)
    memory = Memory(MyFaiss(embedding, faiss.IndexFlatIP(2), InMemoryDocstore({}), {}), "outbox")
    async def get(_): return memory
    monkeypatch.setattr(Memory, "get", staticmethod(get))
    monkeypatch.setattr(Memory, "_get_embedding_config", staticmethod(lambda _: models.ModelConfig(models.ModelType.EMBEDDING, "openai", "synthetic-embedding")))
    monkeypatch.setattr("helpers.plugins.get_plugin_config", lambda *args, **kwargs: {
        "memory_memorize_enabled": True, "memory_memorize_consolidation": True,
        "memory_memorize_replace_threshold": .8, "project_memory_isolation": False, "agent_memory_subdir": "outbox"})
    monkeypatch.setattr(Agent, "read_prompt", lambda self, name, **kwargs: "CONSOLIDATE" if "consolidation" in name else "MEMORIZE")
    # Simulate loss immediately after the atomic outbox transaction, before
    # the original worker can spawn its broker. An unclaimed second host must
    # discover and start the durable, unsent descriptor.
    with monkeypatch.context() as launch_gap:
        launch_gap.setattr(background, "_launch", lambda *args: None)
        await MemorizeMemories(turn.agent).execute(loop_data=turn.agent.loop_data)
    reference = turn.agent.get_data("_durable_memory_outbox")[0]
    assert not provider.requests and not nodes.second.sync("owns", turn.run_id)
    background.recover_pending(nodes.second)
    provider.release.set()
    result = await background.TaskHandle(turn.agent, reference)
    saved = durable_memory.get_snapshot(nodes.first, "outbox")
    assert len(saved["documents"]) == 1 and result["ids"] == [saved["documents"][0]["id"]]
    await MemorizeMemories(turn.agent).execute(loop_data=turn.agent.loop_data)
    assert (await background.TaskHandle(turn.agent, reference))["revision"] == saved["revision"]
    assert len(provider.requests) == 3
    # Another outbox freezes the revision before an independent shared edit.
    provider.arrived.clear(); provider.release.clear()
    task = await memorization.enqueue(turn.agent, turn.agent.loop_data, "solutions")
    await _until(provider.arrived.is_set)
    independent = {"id": "independent-solution", "text": "Independent edited solution", "vector": [0.0, 1.0],
                   "metadata": {"id": "independent-solution", "area": "solutions"}}
    durable_memory.apply_patch(nodes.first, "outbox", saved["revision"], "concurrent-edit",
        {"upsert": [independent], "delete": []}, run_id=turn.run_id)
    provider.release.set()
    result = await task
    assert result["status"] == "conflict"
    assert durable_memory.get_snapshot(nodes.first, "outbox")["documents"] == saved["documents"] + [independent]


@pytest.mark.asyncio
async def test_fragment_and_solution_hooks_commit_concurrent_disjoint_outboxes(task_turn, provider, monkeypatch):
    import faiss
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from plugins._memory.helpers.memory import Memory, MyFaiss
    from plugins._memory.helpers import durable_memory
    from plugins._memory.extensions.python.monologue_end._50_memorize_fragments import MemorizeMemories
    from plugins._memory.extensions.python.monologue_end._51_memorize_solutions import MemorizeSolutions
    nodes, turn = task_turn
    embedding = models.LiteLLMEmbeddingWrapper("synthetic-embedding", "openai", api_key="fixture-only", api_base=provider.url)
    memory = Memory(MyFaiss(embedding, faiss.IndexFlatIP(2), InMemoryDocstore({}), {}), "outbox")
    async def get(_): return memory
    monkeypatch.setattr(Memory, "get", staticmethod(get))
    monkeypatch.setattr(Memory, "_get_embedding_config", staticmethod(lambda _: models.ModelConfig(models.ModelType.EMBEDDING, "openai", "synthetic-embedding")))
    monkeypatch.setattr("helpers.plugins.get_plugin_config", lambda *args, **kwargs: {
        "memory_memorize_enabled": True, "memory_memorize_consolidation": True,
        "memory_memorize_replace_threshold": .8, "project_memory_isolation": False, "agent_memory_subdir": "outbox"})
    monkeypatch.setattr(Agent, "read_prompt", lambda self, name, **kwargs: "CONSOLIDATE" if "consolidation" in name else "MEMORIZE")
    # Both real monologue-end hooks enqueue before either provider can finish.
    await MemorizeMemories(turn.agent).execute(loop_data=turn.agent.loop_data)
    await MemorizeSolutions(turn.agent).execute(loop_data=turn.agent.loop_data)
    references = turn.agent.get_data("_durable_memory_outbox")
    assert len(references) == 2 and durable_memory.get_snapshot(nodes.first, "outbox") is None
    provider.release.set()
    results = await asyncio.gather(*(background.TaskHandle(turn.agent, ref).wait() for ref in references))
    assert sorted(result["revision"] for result in results) == [1, 2]
    saved = durable_memory.get_snapshot(nodes.first, "outbox")
    assert {doc["metadata"]["area"] for doc in saved["documents"]} == {"fragments", "solutions"}
    assert len(provider.requests) == 6
    # Acknowledgement loss after the rebased commit must resolve its original
    # operation receipt, rather than misclassifying its own inserted record as
    # a concurrent edit. Exercise the broker's exact persisted input/results.
    from helpers.durable import memorization
    from helpers.durable.resources import ResourceManager
    for ref, result in zip(references, results):
        if result["revision"] != 2:
            continue
        manager = ResourceManager(nodes.first, turn.agent.context.id)
        request = json.loads(manager.get_bytes(ref["request"]))
        original_sync = nodes.first.sync
        commit_id = request["grants"]["commit:result"]["id"]
        def lost_ack(method, *args, **kwargs):
            row = original_sync(method, *args, **kwargs)
            return dict(row, status="running", result=None) if method == "get_resource_job" and args[0] == commit_id else row
        async def known_phase(label, prepared, action):
            row = original_sync("get_resource_job", request["grants"][label + ":effect"]["id"])
            return json.loads(manager.get_bytes(row["result"]["value"]))
        async def forbidden(*args): raise AssertionError("Known inference repeated")
        with monkeypatch.context() as lost:
            lost.setattr(nodes.first, "sync", lost_ack)
            assert await memorization.execute(nodes.first, request, known_phase, forbidden, forbidden) == result
    assert durable_memory.get_snapshot(nodes.first, "outbox")["revision"] == 2 and len(provider.requests) == 6


@pytest.mark.asyncio
async def test_recent_oversized_messages_compress_on_owner_without_inference(task_turn, provider, monkeypatch):
    from helpers.durable import history
    from helpers import history as ordinary_history
    from plugins._model_config.helpers import model_config
    from extensions.python.message_loop_prompts_before._90_organize_history_wait import OrganizeHistoryWait
    nodes, turn = task_turn
    config = lambda *args, **kwargs: {"ctx_length": 1024, "ctx_history": 1}
    monkeypatch.setattr(ordinary_history, "get_chat_model_config", config)
    monkeypatch.setattr(model_config, "get_chat_model_config", config)
    monkeypatch.setattr(Agent, "read_prompt", lambda self, name, **kwargs: "... content truncated ...")
    raw = {"raw_content": [{"type": "text", "text": "raw tool result " * 1000}], "preview": None}
    turn.agent.history.current.messages = [
        ordinary_history.Message(False, "recent user input " * 1000),
        ordinary_history.Message(True, raw, tokens=10000)]
    originals = [message.content for message in turn.agent.history.current.messages]
    turn.agent.set_data(Agent.DATA_NAME_RESPONSES_STATE, {"response_id": "synthetic", "provider": "openai"})
    assert turn.agent.history.is_over_limit()
    await OrganizeHistoryWait(turn.agent).execute()
    assert not turn.agent.history.is_over_limit()
    assert len(turn.agent.history.current.messages) == 2
    assert [message.content for message in turn.agent.history.current.messages] == originals
    assert all(message.summary for message in turn.agent.history.current.messages)
    assert turn.agent.get_data(Agent.DATA_NAME_RESPONSES_STATE) == {"provider": "openai"}
    assert turn.agent.get_data(history.TASK) is None
    assert provider.requests == []


@pytest.mark.asyncio
async def test_history_projection_retains_appended_input_without_background_mutation(task_turn, provider, monkeypatch):
    from helpers.durable import history
    from helpers.history import Message
    from extensions.python.message_loop_end._10_organize_history import OrganizeHistory
    from extensions.python.message_loop_prompts_before._90_organize_history_wait import OrganizeHistoryWait
    nodes, turn = task_turn
    for index in range(6):
        turn.agent.history.current.messages.append(Message(index % 2 == 0, ("synthetic old record " + str(index) + " ") * 100))
    original = turn.agent.history.to_dict()
    monkeypatch.setattr(turn.agent.history, "is_over_limit", lambda: True)
    monkeypatch.setattr(Agent, "read_prompt", lambda self, name, **kwargs: "QUERY " + str(kwargs.get("content", "")))
    await OrganizeHistory(turn.agent).execute()
    task = turn.agent.get_data(history.TASK)
    await _until(provider.arrived.is_set)
    assert turn.agent.history.to_dict() == original
    manifest = state_adapters.capture(turn.agent, mask=lambda value: value)
    turn.agent.history.current.messages.append(Message(False, "new user input preserved"))
    nodes.first.sync("release", turn.run_id); assert nodes.second.sync("claim", turn.run_id)
    turn.owner = nodes.second
    state_adapters.restore(turn.agent, manifest, guard=lambda: nodes.second.sync("assert_owner", turn.run_id))
    provider.release.set()
    await OrganizeHistoryWait(turn.agent).execute()
    assert turn.agent.history.current.messages[-1].content == "new user input preserved"
    assert turn.agent.history.bulks[0].summary == "query subject"
    assert turn.agent.get_data(history.TASK) is None and len(provider.requests) == 1


@pytest.mark.skipif(not DSN, reason="Requires explicitly disposable PostgreSQL")
def test_detached_inference_commits_after_actual_framework_worker_sigkill(provider, tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from helpers.durable.postgres import PostgresStore
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("A0_DURABILITY_POSTGRES_DSN", DSN)
    monkeypatch.setenv("A0_DURABILITY_EXECUTION_ROOT", str(tmp_path / "jobs"))
    environment = dict(os.environ, A0_DURABILITY_JOB_NAMESPACE="background_" + uuid.uuid4().hex, A0_TEST_BACKGROUND_URL=provider.url)
    worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(tmp_path)], cwd=PROJECT, env=environment,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 15
        while not provider.arrived.is_set():
            if worker.poll() is not None: raise AssertionError(worker.communicate()[1].decode())
            assert time.monotonic() < deadline
            time.sleep(.02)
        worker.kill(); worker.communicate(timeout=5)
        reference = json.loads((tmp_path / "reference.json").read_bytes())
        with PostgresStore(DSN, namespace=environment["A0_DURABILITY_JOB_NAMESPACE"]) as store:
            assert store.claim(reference["run_id"])
            provider.release.set()
            deadline = time.monotonic() + 15
            while store.get_resource_job(reference["id"] + ":final:result")["status"] != "completed":
                assert time.monotonic() < deadline
                time.sleep(.02)
            class Owner:
                distributed = True
                def sync(self, method, *args, **kwargs): return getattr(store, method)(*args, **kwargs)
            context = SimpleNamespace(id="background-context")
            agent = SimpleNamespace(context=context)
            context._durable_turn = SimpleNamespace(agent=agent, owner=Owner(), run_id=reference["run_id"])
            assert asyncio.run(background.TaskHandle(agent, reference).wait()) == "query subject"
            assert len(provider.requests) == 1
    finally:
        provider.release.set()
        if worker.poll() is None: worker.kill(); worker.communicate(timeout=5)


if __name__ == "__main__":
    _worker(sys.argv[2])
