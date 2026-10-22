"""Two real services share only a disposable PostgreSQL database."""
import asyncio
import copy
import os
import uuid
from types import SimpleNamespace

import pytest

from agent import Agent, LoopData, UserMessage
from helpers.durable import codec, runtime
from helpers.durable.cluster import ClusterRecoveryService, RunHandle, portable
from helpers.durable.store import ConflictError
from test_durable_runtime import rig

DSN = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")


@pytest.fixture
def nodes(rig, monkeypatch):
    if not DSN:
        pytest.skip("Requires explicit disposable PostgreSQL")
    namespace = "cluster_" + uuid.uuid4().hex
    first = runtime.RecoveryService(None, backend="postgres", dsn=DSN, namespace=namespace, scan_interval=.02)
    second = ClusterRecoveryService(DSN, namespace=namespace, scan_interval=.02)
    assert not first.failed and not second.failed
    monkeypatch.setattr(runtime, "_service", first)
    try:
        yield SimpleNamespace(first=first, second=second, rig=rig)
    finally:
        first.close(); second.close()


def admit(nodes, input_id="shared-input"):
    context = nodes.rig.context
    message = UserMessage("Shared input", id=input_id)
    return nodes.first.sync("admit", context.id, input_id, codec.message_payload(message),
                            codec.checkpoint(context.agent0))


def test_live_claim_prevents_second_host_context_construction(nodes, monkeypatch):
    run = admit(nodes)
    assert nodes.first.sync("claim", run["run_id"])
    def forbidden(_data):
        raise AssertionError("A joining host constructed an unclaimed context")
    monkeypatch.setattr("helpers.persist_chat._deserialize_context", forbidden)
    nodes.second.scan()
    assert nodes.second.contexts == {} and nodes.rig.requests == []
    assert nodes.first.sync("owns", run["run_id"])
    nodes.first.sync("release", run["run_id"])
    # Even after takeover is available, unknown constructors must be rejected
    # before they can run hooks against a reconstructed executable context.
    class EffectfulInitializer:
        pass
    monkeypatch.setattr("helpers.extension._get_extension_classes", lambda point, **kwargs:
                        [EffectfulInitializer] if point == "agent_init" else [])
    nodes.second.scan()
    assert nodes.second.sync("get_run", run["run_id"])["status"] == "attention"
    assert nodes.second.contexts == {} and nodes.rig.requests == []


def test_another_host_continues_shared_history_without_local_chat_files(nodes):
    from helpers import persist_chat
    persist_chat.save_tmp_chat(nodes.rig.context)
    assert nodes.first.sync("get_projection", "genesis:" + nodes.rig.context.id)
    first = nodes.second.communicate_remote(nodes.rig.context.id, UserMessage("First", id="first"), ui=True)
    assert first.result_sync(timeout=10) == "Done"
    second = nodes.second.communicate_remote(nodes.rig.context.id, UserMessage("Second", id="second"))
    assert isinstance(second, RunHandle) and second.result_sync(timeout=10) == "Done"
    runs = nodes.second.sync("list_runs")
    assert len(runs) == 2 and all(run["status"] == "completed" for run in runs)
    last = max(runs, key=lambda run: (run["created_at"], run["run_id"]))
    assert "First" in str(last["checkpoint"]["context"]["agents"][0]["history"])
    assert "Second" in str(last["checkpoint"]["context"]["agents"][0]["history"])
    assert len(nodes.rig.requests) == 2
    # Terminal journal retention cannot erase the current conversation needed
    # to admit its next turn on another host.
    assert nodes.second.sync("compact", retain_terminal=0)["runs_pruned"] == 2
    retained = nodes.second.communicate_remote(nodes.rig.context.id, UserMessage("Retained conversation", id="retained"))
    assert retained.result_sync(timeout=10) == "Done"
    head = nodes.first.sync("get_context_head", nodes.rig.context.id)
    assert "First" in head["checkpoint"]["context"]["agents"][0]["history"]
    assert "Retained conversation" in head["checkpoint"]["context"]["agents"][0]["history"]
    # Reset is a shared generation change, not a requester-side object reset.
    receipt = nodes.first.sync("control_request", nodes.rig.context.id, "reset", "reset-once")
    third = nodes.second.communicate_remote(nodes.rig.context.id, UserMessage("After reset", id="after-reset"))
    assert third.result_sync(timeout=10) == "Done"
    after = max(nodes.second.sync("list_runs"), key=lambda run: run["checkpoint_seq"])
    history = after["checkpoint"]["context"]["agents"][0]["history"]
    assert "After reset" in history and "First" not in history and "Second" not in history
    assert nodes.first.sync("control_request", nodes.rig.context.id, "reset", "reset-once") == receipt
    assert nodes.second.sync("get_run", after["run_id"])["status"] == "completed"


def test_remote_pause_and_input_are_acknowledged_without_snapshot_unpause(nodes):
    run = admit(nodes)
    assert nodes.first.sync("claim", run["run_id"])
    context = nodes.first._restore_claimed(run)
    command = nodes.second.submit_command(run["run_id"], "pause", {"paused": True}, "pause-once")
    nodes.first.refresh_commands(context, run["run_id"])
    assert context.paused
    nodes.second.communicate_remote(context.id, UserMessage("Intervene", id="i" * 200))
    nodes.first.refresh_commands(context, run["run_id"])
    turn = runtime.Turn(nodes.first, context.agent0, nodes.first.sync("get_run", run["run_id"]))
    context._durable_turn = turn
    context.agent0.loop_data = LoopData(iteration=0)
    asyncio.run(turn.save("iteration_ready"))
    saved = nodes.second.sync("get_run", run["run_id"])
    assert saved["status"] == "blocked" and saved["checkpoint"]["paused"]
    assert saved["checkpoint"]["intervention"]["message"] == "Intervene"
    receipt = nodes.second.sync("enqueue_command", run["run_id"], "pause", {"paused": True}, command["request_id"])
    assert receipt["status"] == "applied" and receipt["result"]["accepted"]
    assert len(nodes.first.sync("pending_commands", run["run_id"])) == 0


def test_ui_intervention_prepares_on_owner_and_reuses_attachment_receipt(nodes, monkeypatch):
    from pathlib import Path
    import hashlib
    import time
    from cryptography.fernet import Fernet
    from helpers.extension import Extension
    from helpers.durable.resources import ResourceManager, SCHEME
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    context = nodes.rig.context
    run = admit(nodes)
    assert nodes.first.sync("claim", run["run_id"])
    context.agent0.loop_data = LoopData(iteration=0)
    nodes.first.sync("transition", run["run_id"], "iteration_ready", codec.checkpoint(context.agent0))
    prepared = []
    class PrepareIntervention(Extension):
        async def execute(self, data, **kwargs):
            assert nodes.first.sync("owns", run["run_id"])
            assert Path(data["attachment_paths"][0]).read_bytes() == b"portable input"
            prepared.append(data["message"])
            data["message"] = "Prepared: " + data["message"]
    monkeypatch.setattr("helpers.extension._get_extension_classes", lambda point, **kwargs:
                        [PrepareIntervention] if point == "user_message_ui" else [])
    ref = ResourceManager(nodes.second, context.id).put_bytes("attachment", "input.txt", b"portable input")
    message = UserMessage("Change direction", attachments=[SCHEME + ref["id"]], id="ui-change")
    with nodes.first._scan_lock, nodes.second._scan_lock:
        nodes.second.communicate_remote(context.id, message, ui=True)
        request_id = "input:" + hashlib.sha256(message.id.encode()).hexdigest()
        deadline = time.monotonic() + 10
        while nodes.second.sync("get_command", run["run_id"], request_id)["status"] != "applied":
            nodes.first.refresh_commands(context, run["run_id"])
            assert time.monotonic() < deadline
            time.sleep(.01)
        receipt = nodes.second.sync("get_command", run["run_id"], request_id)
        assert receipt["result"]["accepted"]
        saved = nodes.second.sync("get_run", run["run_id"])
        assert saved["checkpoint"]["intervention"]["message"] == "Prepared: Change direction"
        assert saved["checkpoint"]["intervention"]["attachments"] == [SCHEME + ref["id"]]
        assert Path(context.agent0.intervention.attachments[0]).read_bytes() == b"portable input"
        nodes.first.refresh_commands(context, run["run_id"])
        assert prepared == ["Change direction"]
        nodes.first.sync("release", run["run_id"])
        assert nodes.second.sync("claim", run["run_id"])
        assert nodes.second.sync("get_command", run["run_id"], request_id) == receipt


def test_ui_hooks_run_on_claimed_worker_and_unknown_preparation_never_replays(nodes, monkeypatch):
    from helpers import extension
    from helpers.extension import Extension
    observed = []

    class PrepareUi(Extension):
        async def execute(self, data, **kwargs):
            await asyncio.sleep(0)
            owner = nodes.second if nodes.second.sync("owns", current_id[0]) else nodes.first
            assert owner.sync("owns", current_id[0])
            assert owner.sync("get_call", current_id[0], "input_ui")["status"] == "intent"
            observed.append(data["message"])
            data["message"] = "Prepared: " + data["message"]

    monkeypatch.setattr(extension, "_get_extension_classes", lambda point, **kwargs: [PrepareUi] if point == "user_message_ui" else [])
    raw = UserMessage("Raw UI input", id="ui-first")
    data = codec.checkpoint(nodes.rig.context.agent0)
    data["ui_input_pending"] = True
    run = nodes.first.sync("admit", nodes.rig.context.id, raw.id, codec.message_payload(raw), data)
    current_id = [run["run_id"]]
    assert nodes.second.dispatch_for_run(run["run_id"]).result_sync(timeout=10) == "Done"
    saved = nodes.second.sync("get_run", run["run_id"])
    assert saved["input_payload"]["message"] == "Raw UI input"
    assert "Prepared: Raw UI input" in saved["checkpoint"]["context"]["agents"][0]["history"]
    users = [item for item in saved["checkpoint"]["context"]["log"]["logs"] if item["type"] == "user"]
    assert [item["content"] for item in users] == ["Prepared: Raw UI input"]
    assert observed == ["Raw UI input"] and len(nodes.rig.requests) == 1
    for node in (nodes.first, nodes.second):
        active_context = node.contexts.get(run["run_id"])
        if active_context and active_context.task:
            active_context.task.result_sync(timeout=10)

    # A committed preparation can move to another worker before initialization.
    known_message = UserMessage("Known preparation", id="ui-known")
    data = copy.deepcopy(saved["checkpoint"])
    data.update(ui_input_pending=True, result=None, terminal=None)
    with nodes.first._scan_lock, nodes.second._scan_lock:
        known = nodes.first.sync("admit", nodes.rig.context.id, known_message.id, codec.message_payload(known_message), data)
        current_id[0] = known["run_id"]
        assert nodes.first.sync("claim", known["run_id"])
        context = nodes.first._restore_claimed(known)
        assert asyncio.run(nodes.first.prepare_input(context, known))["message"] == "Prepared: Known preparation"
        nodes.first.sync("release", known["run_id"])
    assert nodes.second.dispatch_for_run(known["run_id"]).result_sync(timeout=10) == "Done"
    assert observed == ["Raw UI input", "Known preparation"] and len(nodes.rig.requests) == 2
    for node in (nodes.first, nodes.second):
        active_context = node.contexts.get(known["run_id"])
        if active_context and active_context.task:
            active_context.task.result_sync(timeout=10)

    # An intent without a result may already have produced hook effects.
    latest = nodes.first.sync("get_run", known["run_id"])
    unknown_message = UserMessage("Unknown preparation", id="ui-unknown")
    data = copy.deepcopy(latest["checkpoint"])
    data.update(ui_input_pending=True, result=None, terminal=None)
    with nodes.first._scan_lock, nodes.second._scan_lock:
        unknown = nodes.first.sync("admit", nodes.rig.context.id, unknown_message.id, codec.message_payload(unknown_message), data)
        current_id[0] = unknown["run_id"]
        nodes.second.communicate_remote(nodes.rig.context.id, UserMessage("Intervene", id="ui-intervention"), ui=True)
        assert len(nodes.second.sync("pending_commands", unknown["run_id"])) == 1
        assert nodes.first.sync("claim", unknown["run_id"])
        nodes.first.sync("start_call", unknown["run_id"], "input_ui", "input_ui", codec.message_payload(unknown_message))
        nodes.first.sync("release", unknown["run_id"])
    nodes.second.dispatch_for_run(unknown["run_id"]).result_sync(timeout=10)
    assert nodes.second.sync("get_run", unknown["run_id"])["status"] == "attention"
    assert observed == ["Raw UI input", "Known preparation"] and len(nodes.rig.requests) == 2


def test_runner_release_during_command_refresh_does_not_disable_worker(nodes, monkeypatch):
    run = admit(nodes)
    assert nodes.second.sync("claim", run["run_id"])
    nodes.second._restore_claimed(run)
    refresh = nodes.second.refresh_commands
    released = []

    def finish_before_refresh(context, run_id):
        if run_id == run["run_id"] and not released:
            # scan() has already observed this live claim and active run.
            nodes.second.sync("transition", run_id, "completed", status="completed")
            nodes.second.sync("release", run_id)
            released.append(run_id)
        return refresh(context, run_id)

    monkeypatch.setattr(nodes.second, "refresh_commands", finish_before_refresh)
    nodes.second.recover()
    assert released == [run["run_id"]] and not nodes.second.failed
    following = nodes.second.communicate_remote(nodes.rig.context.id, UserMessage("Following input", id="after-release"))
    assert following.result_sync(timeout=10) == "Done"
    assert not nodes.second.failed and len(nodes.rig.requests) == 1


def test_scheduler_projection_uses_compare_and_swap_without_host_files(nodes, monkeypatch, tmp_path):
    from helpers import task_scheduler as scheduler
    monkeypatch.setattr(scheduler, "SCHEDULER_FOLDER", str(tmp_path / "must-not-exist"))
    first = scheduler.SchedulerTaskList(tasks=[])
    second = scheduler.SchedulerTaskList(tasks=[])
    first._reload_shared(nodes.first)
    second._reload_shared(nodes.second)
    task = scheduler.AdHocTask(name="Shared", prompt="Do work", system_prompt="System", context_id=nodes.rig.context.id)
    first.tasks.append(task)
    monkeypatch.setattr(runtime, "_service", nodes.first)
    asyncio.run(first.save())
    second.tasks.append(scheduler.AdHocTask(name="Stale", prompt="Work", system_prompt="System", context_id="other"))
    monkeypatch.setattr(runtime, "_service", nodes.second)
    with pytest.raises(ConflictError):
        asyncio.run(second.save())
    asyncio.run(second.reload())
    assert [task.name for task in second.tasks] == ["Shared"]
    assert not (tmp_path / "must-not-exist").exists()


def test_portability_rejects_project_and_attachment_resources(rig):
    data = codec.checkpoint(rig.context.agent0)
    assert portable(data, {"message": "Plain"})
    project = copy.deepcopy(data)
    project["context"]["data"]["project"] = "host-project"
    assert not portable(project)
    assert not portable(data, {"attachments": ["/host/private.pdf"]})
    assert not portable(dict(data, requires_state_adapter=True))


@pytest.mark.asyncio
async def test_parent_joins_child_claimed_by_another_host_without_relaunch(nodes, monkeypatch):
    import threading
    from agent import AgentContext
    from helpers.durable import workflows
    from helpers.tool import Response
    from tools.durable_plan import DurablePlan
    started, release = threading.Event(), threading.Event()
    effects = []
    async def child_body(self, **kwargs):
        effects.append("once")
        started.set()
        while not release.is_set():
            await asyncio.sleep(.005)
        return Response("Remote child done", True)
    monkeypatch.setattr(DurablePlan, "execute", child_body)
    monkeypatch.setattr(Agent, "get_tool", lambda self, name, method, args, message, loop_data:
                        DurablePlan(self, name, method, args, message, loop_data))
    parent_run = admit(nodes)
    assert nodes.first.sync("claim", parent_run["run_id"])
    # This test drives the parent's join manually; reserve it just as dispatch
    # does so a background scanner cannot start a second parent monologue.
    nodes.first.driving.add(parent_run["run_id"])
    context = nodes.rig.context
    context.agent0.loop_data = LoopData(iteration=0)
    turn = runtime.Turn(nodes.first, context.agent0, parent_run)
    turn.active_call_id = "tool:0:0"
    context._durable_turn = turn
    child, = await workflows._manifest(turn, [{"name": "durable_plan", "args": {"action": "read"}}])
    run = nodes.first.sync("admit", child["context_id"], child["input_id"],
                           codec.message_payload(UserMessage(child["message"], id=child["input_id"])), child["genesis"])
    assert nodes.second.sync("claim", run["run_id"])
    remote = nodes.second._restore_claimed(run)
    task = nodes.second.dispatch(remote, run)
    try:
        assert await asyncio.to_thread(started.wait, 5)
        handle = workflows._submit(turn, child)
        assert isinstance(handle, RunHandle)
        assert nodes.second.sync("owns", run["run_id"])
        assert not nodes.first.sync("owns", run["run_id"])
        release.set()
        joined = await workflows._join(turn, child, handle, timeout=5)
        assert joined["state"] == "success" and joined["result"] == "Remote child done"
        assert await workflows._join(turn, child, handle) == joined
        assert effects == ["once"] and nodes.rig.requests == []
    finally:
        release.set()
        task.kill()


def test_only_scheduler_role_polls_and_shared_plan_finishes_once(nodes, monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone
    from helpers import task_scheduler as scheduler
    monkeypatch.setattr(scheduler, "SCHEDULER_FOLDER", str(tmp_path / "unused-host-tasks"))
    monkeypatch.setattr(scheduler.TaskScheduler, "_instance", None)
    monkeypatch.setattr(scheduler.SchedulerTaskList, "_SchedulerTaskList__instance", None)
    monkeypatch.setattr(scheduler, "initialize_agent", lambda: nodes.rig.context.config)
    now = datetime(2026, 10, 22, 10, 0, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler, "_now", lambda: now)
    engine = scheduler.TaskScheduler.get()
    task = scheduler.PlannedTask(name="Shared plan", prompt="Do work", system_prompt="System",
                                 context_id=nodes.rig.context.id,
                                 plan=scheduler.TaskPlan(todo=[now - timedelta(minutes=1), now + timedelta(hours=1)]))
    asyncio.run(engine.add_task(task))
    assert nodes.second.sync("try_role", "scheduler")
    asyncio.run(engine.tick())
    assert nodes.first.sync("list_run_headers") == []
    nodes.second.sync("release_role", "scheduler")
    asyncio.run(engine.tick())
    run, = nodes.first.sync("list_run_headers")
    assert RunHandle(nodes.first, run["run_id"]).result_sync(timeout=10) == "Done"
    monkeypatch.setattr(runtime, "_service", nodes.second)
    asyncio.run(engine.tick())
    asyncio.run(engine.reload())
    current = engine.get_task_by_uuid(task.uuid)
    assert current.state == scheduler.TaskState.IDLE and current.durable_status == "completed"
    assert len(current.plan.done) == 1 and len(current.plan.todo) == 1
    assert len(nodes.second.sync("list_run_headers")) == 1 and len(nodes.rig.requests) == 1
    assert not (tmp_path / "unused-host-tasks").exists()

    # Scheduler and integration polling have separate ownership. Two hosts may
    # enter the framework job loop, but only one healthy session polls plugins.
    from helpers import job_loop, extension
    polls = []
    original_extensions = extension.call_extensions_async
    async def poll(point, *args, **kwargs):
        if point == "job_loop":
            polls.append("poll")
        else:
            await original_extensions(point, *args, **kwargs)
    monkeypatch.setattr(extension, "call_extensions_async", poll)
    monkeypatch.setattr(runtime, "_service", nodes.first)
    asyncio.run(job_loop.scheduler_tick())
    monkeypatch.setattr(runtime, "_service", nodes.second)
    asyncio.run(job_loop.scheduler_tick())
    assert polls == ["poll"]

    # A later occurrence must use the retained current head, including a reset
    # fence, after the previous run's recovery payload has expired.
    assert nodes.second.sync("compact", retain_terminal=0)["runs_pruned"] == 1
    nodes.second.sync("control_request", task.context_id, "reset", "reset-scheduled")
    asyncio.run(engine._run_task(current, occurrence_id="manual:after-retention"))
    next_run = max(nodes.second.sync("list_run_headers"), key=lambda row: row["admission_seq"])
    assert RunHandle(nodes.second, next_run["run_id"]).result_sync(timeout=10) == "Done"
    asyncio.run(engine.reload())
    assert len(engine.get_task_by_uuid(task.uuid).plan.done) == 1
    assert len(nodes.rig.requests) == 2


def test_idle_document_command_is_drained_by_real_coordinator_without_model(nodes, monkeypatch):
    import time
    from cryptography.fernet import Fernet
    from helpers.durable import maintenance
    from api.durability import Durability
    import threading
    import json
    monkeypatch.setenv('A0_DURABILITY_RESOURCE_KEY', Fernet.generate_key().decode())
    run = admit(nodes)
    assert nodes.first.sync('claim', run['run_id'])
    nodes.first.sync('transition', run['run_id'], 'completed', status='completed')
    nodes.first.sync('release', run['run_id'])
    info = maintenance.metadata(nodes.second, run['context_id'])
    monkeypatch.setattr(runtime, '_service', nodes.second)
    response = asyncio.run(Durability(None, threading.RLock()).process({
        'action': 'document_update', 'context': run['context_id'], 'run_id': run['run_id'],
        'kind': 'todo', 'value': {'title': 'Applied on owner', 'items': []}, 'expected_revision': 0,
        'request_id': 'idle-plan', 'expected_generation': info['generation'], 'epoch': info['epoch'], 'version': info['version']}, None))
    assert response.status_code == 202, response.get_data(as_text=True)
    assert json.loads(response.data)['queued']
    deadline = time.monotonic() + 10
    while nodes.first.sync('get_command', run['run_id'], 'idle-plan')['status'] == 'pending':
        assert time.monotonic() < deadline
        time.sleep(.02)
    receipt = nodes.first.sync('get_command', run['run_id'], 'idle-plan')
    assert receipt['status'] == 'applied', receipt
    assert nodes.first.sync('read_document', run['context_id'], 'todo')['value']['title'] == 'Applied on owner'
    assert nodes.rig.requests == []


def test_memory_write_recovers_atomic_result_when_worker_loses_body_ack(nodes, monkeypatch, tmp_path):
    from cryptography.fernet import Fernet
    from langchain_core.embeddings import Embeddings
    from plugins._memory.helpers import memory as memory_module
    from plugins._memory.tools.memory_save import MemorySave
    from helpers.tool_execution import execute_tool
    from helpers.durable.runtime import RecoveryHeld, Turn
    monkeypatch.setenv('A0_DURABILITY_RESOURCE_KEY', Fernet.generate_key().decode())
    class Embedder(Embeddings):
        def embed_documents(self, texts):
            embedded.extend(texts); return [[1., 0.] for _ in texts]
        def embed_query(self, text):
            return [1., 0.]
    embedded = []
    monkeypatch.setattr('models.get_embedding_model', lambda *args, **kwargs: Embedder())
    monkeypatch.setattr(memory_module.Memory, '_get_embedding_config', lambda agent=None: SimpleNamespace(provider='synthetic', name='fixed', build_kwargs=lambda: {}))
    monkeypatch.setattr(memory_module, 'get_agent_memory_subdir', lambda agent: 'synthetic-write')
    monkeypatch.setattr(memory_module, 'abs_db_dir', lambda scope: str(tmp_path / 'unused-memory-files'))
    monkeypatch.setattr(memory_module.Memory, 'index', {})
    monkeypatch.setattr(memory_module, 'get_knowledge_subdirs_by_memory_subdir', lambda *args: [])
    agent = nodes.rig.context.agent0
    run = admit(nodes)
    assert nodes.first.sync('claim', run['run_id'])
    agent.loop_data = LoopData(iteration=0)
    nodes.first.contexts[run['run_id']] = agent.context
    nodes.first.sync('transition', run['run_id'], 'tools', checkpoint=codec.checkpoint(agent))
    run = nodes.first.sync('get_run', run['run_id'])
    agent.context._durable_turn = first = Turn(nodes.first, agent, run)
    first.recovered = False
    tool = MemorySave(agent, 'memory_save', None, {'text': 'one durable memory'}, '', agent.loop_data)
    async def crash(*args):
        raise RecoveryHeld('worker ended after memory commit')
    monkeypatch.setattr(first, 'tool_body', crash)
    with pytest.raises(RecoveryHeld):
        asyncio.run(execute_tool(tool, tool.args))
    assert embedded == ['one durable memory']
    assert nodes.first.sync('get_call', run['run_id'], 'tool:0:0')['status'] == 'intent'
    nodes.first.sync('release', run['run_id'])
    assert nodes.second.sync('claim', run['run_id'])
    saved = nodes.second.sync('get_run', run['run_id'])
    restored = nodes.second._restore_claimed(saved)
    restored._durable_turn = second = Turn(nodes.second, restored.agent0, saved)
    codec.restore(restored, saved['checkpoint'])
    monkeypatch.setattr(runtime, '_service', nodes.second)
    recovered = MemorySave(restored.agent0, 'memory_save', None, {'text': 'one durable memory'}, '', restored.agent0.loop_data)
    response = asyncio.run(execute_tool(recovered, recovered.args))
    assert response.break_loop is False
    assert embedded == ['one durable memory']
    assert nodes.second.sync('get_call', run['run_id'], 'tool:0:0:final')['status'] == 'completed'


def test_terminal_hook_cannot_acknowledge_input_that_will_never_be_consumed(nodes, monkeypatch):
    import threading
    from helpers.extension import Extension
    entered, release = threading.Event(), threading.Event()
    class Finishing(Extension):
        async def execute(self, **kwargs):
            entered.set()
            await asyncio.to_thread(release.wait)
    monkeypatch.setattr('helpers.extension._get_extension_classes', lambda point, **kwargs:
                        [Finishing] if point == 'monologue_end' else [])
    run = admit(nodes)
    handle = nodes.first.dispatch_for_run(run['run_id'])
    try:
        assert entered.wait(5)
        assert nodes.second.sync('get_run', run['run_id'])['phase'] == 'finalizing'
        with pytest.raises(ConflictError, match='finishing'):
            nodes.second.communicate_remote(run['context_id'], UserMessage('Next message', id='after-terminal'))
        assert nodes.first.sync('pending_commands', run['run_id']) == []
    finally:
        release.set()
    assert handle.result_sync(timeout=10) == 'Done'
    next_handle = nodes.second.communicate_remote(run['context_id'], UserMessage('Next message', id='after-terminal'))
    assert next_handle.result_sync(timeout=10) == 'Done'
    assert nodes.second.communicate_remote(run['context_id'], UserMessage('Next message', id='after-terminal')).result_sync(timeout=10) == 'Done'
    assert len(nodes.rig.requests) == 2


def test_bad_maintenance_context_does_not_disable_healthy_chat_processing(nodes, monkeypatch):
    import time
    from cryptography.fernet import Fernet
    from helpers.durable import maintenance
    from helpers.durable.resources import ResourceHeld
    monkeypatch.setenv('A0_DURABILITY_RESOURCE_KEY', Fernet.generate_key().decode())
    context = nodes.rig.context
    bad = admit(nodes)
    nodes.first.sync('claim', bad['run_id'])
    nodes.first.sync('transition', bad['run_id'], 'completed', status='completed')
    nodes.first.sync('release', bad['run_id'])
    restore = nodes.second._restore_claimed
    def guarded(run):
        if run['run_id'] == bad['run_id']:
            raise ResourceHeld('synthetic missing private resource')
        return restore(run)
    monkeypatch.setattr(nodes.second, '_restore_claimed', guarded)
    info = maintenance.metadata(nodes.second, context.id)
    maintenance.enqueue(nodes.second, context.id, bad['run_id'], 'maintenance_document',
        {'kind': 'todo', 'value': {'title': 'Held draft', 'items': []}, 'expected_revision': 0}, 'bad-draft',
        generation=info['generation'], epoch=info['epoch'], version=info['version'])
    deadline = time.monotonic() + 10
    while nodes.first.sync('get_command', bad['run_id'], 'bad-draft')['status'] == 'pending':
        assert time.monotonic() < deadline
        time.sleep(.02)
    assert not nodes.second.failed
    assert nodes.first.sync('get_command', bad['run_id'], 'bad-draft')['result']['accepted'] is False
    # Another chat can still claim, construct and execute after that rejection.
    from agent import AgentContext
    fresh = AgentContext(context.config, id='healthy-after-bad-maintenance')
    monkeypatch.setattr(runtime, '_service', nodes.second)
    assert fresh.communicate(UserMessage('Healthy input', id='healthy-input')).result_sync(timeout=10) == 'Done'
