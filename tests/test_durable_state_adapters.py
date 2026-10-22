"""Declared plugin state survives recovery without recreating uncertain effects."""
import asyncio
from copy import deepcopy
import hashlib
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from helpers.durable import state_adapters as state


def agent(number=0):
    context = SimpleNamespace(id="synthetic-context", data={})
    loop = SimpleNamespace(**{f"{kind}_{duration}": {} for kind in ("params", "protocol", "extras")
                              for duration in ("persistent", "temporary")})
    result = SimpleNamespace(number=number, context=context, data={}, loop_data=loop,
                             DATA_NAME_SUBORDINATE="_subordinate", DATA_NAME_CTX_WINDOW="ctx_window")
    context.agent0 = result
    result.get_data = lambda key: result.data.get(key)
    result.set_data = lambda key, value: result.data.__setitem__(key, value)
    return result


def known_query(payload):
    return {"known": True, "result": {"receipt": payload["receipt"]}}


class StateAdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry = patch.dict(state._REGISTRY, dict(state._REGISTRY), clear=True)
        self.registry.start()
        self.addCleanup(self.registry.stop)

    def test_actual_bundled_usage_producer_round_trip_preserves_tuples_and_private_counter(self):
        from plugins._context_window.helpers import usage
        from plugins._error_retry.extensions.python._functions.agent.Agent.monologue.start._10_reset_critical_exception_counter import ResetCriticalExceptionCounter, DATA_NAME_COUNTER
        current = agent()
        asyncio.run(ResetCriticalExceptionCounter(current).execute())
        current.data[DATA_NAME_COUNTER] += 2
        current.context.data["chat_naming_manual"] = True
        current.data["_browser_model_active"] = "synthetic-model"
        with patch.object(usage.tokens, "approximate_prompt_tokens", return_value=17):
            usage.reset(current)
            usage.record_prompt(current, "messages", "synthetic prompt")
        current.data["ctx_window"] = {"tokens": 17}
        manifest = state.capture(current, mask=lambda value: value)
        restored = agent()
        state.restore(restored, manifest, guard=lambda: None)
        self.assertEqual(restored.data[DATA_NAME_COUNTER], 2)
        self.assertEqual(restored.context.data, {"chat_naming_manual": True})
        self.assertEqual(restored.data[usage.CACHE_KEY], current.data[usage.CACHE_KEY])
        self.assertEqual(restored.loop_data.params_temporary, current.loop_data.params_temporary)
        manifest["entries"].clear()
        self.assertEqual(restored.data["_browser_model_active"], "synthetic-model")

    def test_known_memory_result_rebinds_loop_and_awaits_without_query_but_pending_model_holds(self):
        async def scenario():
            current = agent()
            current.data.update(_recall_memories_loop=current.loop_data,
                                _recall_memories_iter=2, _recall_memories_result_scope=("profile", "project", "memory"))
            async def result():
                return {"memories": "known memory"}
            task = asyncio.create_task(result())
            await task
            current.data["_recall_memories_task"] = task
            manifest = state.capture(current, mask=lambda value: value)
            restored = agent()
            state.restore(restored, manifest, guard=lambda: None)
            self.assertIs(restored.data["_recall_memories_loop"], restored.loop_data)
            self.assertEqual(await restored.data["_recall_memories_task"], {"memories": "known memory"})
            self.assertEqual(restored.data["_recall_memories_result_scope"], ("profile", "project", "memory"))
            pending = asyncio.create_task(asyncio.Event().wait())
            current.data["_recall_memories_task"] = pending
            try:
                with self.assertRaisesRegex(state.StateHeld, "background_outcome_unknown"):
                    state.capture(current, mask=lambda value: value)
            finally:
                pending.cancel()
                try:
                    await pending
                except asyncio.CancelledError:
                    pass
        asyncio.run(scenario())

    def test_real_infection_checker_reconstructs_known_gate_without_calling_model(self):
        from plugins._infection_check.helpers.checker import InfectionChecker
        from langchain_core.messages import SystemMessage, HumanMessage
        async def scenario():
            current = agent()
            checker = InfectionChecker({"mode": "both", "prompt": "synthetic safety rule"}, 3)
            checker.reasoning_log = "known reasoning"
            checker._check_msgs = [SystemMessage(content="synthetic safety rule"), HumanMessage(content="known reasoning")]
            async def known():
                return "ok", "", "known verdict"
            checker._task = asyncio.create_task(known())
            await checker._task
            current.data.update({"_plugin._infection_check": checker,
                                 "_plugin._infection_check.mono": id(current.loop_data),
                                 "_plugin._infection_check.passed": False})
            manifest = state.capture(current, mask=lambda value: value)
            restored = agent()
            restored.context.log = SimpleNamespace(set_progress=lambda value: None)
            with patch.object(InfectionChecker, "_run_check", side_effect=AssertionError("known model call repeated")):
                state.restore(restored, manifest, guard=lambda: None)
                await restored.data["_plugin._infection_check"].gate(restored)
            self.assertTrue(restored.data["_plugin._infection_check.passed"])
            self.assertEqual(restored.data["_plugin._infection_check.mono"], id(restored.loop_data))
        asyncio.run(scenario())

    def test_source_or_schema_drift_and_stale_claim_do_not_partially_restore_state(self):
        current = agent()
        current.context.data["chat_naming_manual"] = True
        current.data["_browser_model_active"] = "secret model name"
        manifest = state.capture(current, mask=lambda value: value.replace("secret", "masked") if isinstance(value, str) else value)
        changed = deepcopy(manifest)
        changed["entries"][0]["adapter"]["version"] += 1
        restored = agent()
        with self.assertRaises(state.StateHeld):
            state.restore(restored, changed, guard=lambda: self.fail("validation must precede guard"))
        self.assertEqual(restored.context.data, {})
        changed = deepcopy(manifest)
        key = next(iter(changed["entries"][0]["adapter"]["sources"]))
        changed["entries"][0]["adapter"]["sources"][key] = "0" * 64
        with self.assertRaises(state.StateHeld):
            state.validate(changed)
        def stale():
            raise RuntimeError("claim lost")
        with self.assertRaisesRegex(RuntimeError, "claim lost"):
            state.restore(restored, manifest, guard=stale)
        self.assertEqual(restored.context.data, {})
        state.restore(restored, manifest, guard=lambda: None)
        self.assertEqual(restored.data["_browser_model_active"], "masked model name")
        current.context.data["chat_naming_manual"] = object()
        with self.assertRaises(state.StateHeld):
            state.capture(current, mask=lambda value: value)

    def test_declared_kvp_is_context_local_and_inherited_stale_tasks_cannot_write(self):
        from helpers import kvp
        state.register(state.StateAdapter("synthetic_kvp", 1,
            (state.Field("kvp", "persistent:plugin-value"), state.Field("kvp", "runtime:plugin-value")),
            ("tests/test_durable_state_adapters.py",)))
        async def scenario():
            ready = asyncio.Event()
            count = 0
            snapshots = []
            async def worker(value):
                nonlocal count
                values, valid = {}, [True]
                def guard():
                    if not valid[0]:
                        raise RuntimeError("claim lost")
                with kvp.context_scope(value, values, state.handled_keys("kvp"), guard=guard):
                    kvp.set_persistent("plugin-value", {"context": value})
                    kvp.set_runtime("plugin-value", value)
                    with self.assertRaises(RuntimeError):
                        kvp.get_persistent("global-browser-tabs")
                    count += 1
                    if count == 2:
                        ready.set()
                    await ready.wait()
                    self.assertEqual(kvp.get_runtime("plugin-value"), value)
                    self.assertEqual(kvp.find_persistent("*"), ["plugin-value"])
                    current = agent()
                    manifest = state.capture(current, kvp=values, mask=lambda item: item)
                    target = {}
                    state.restore(agent(), manifest, kvp=target, guard=guard)
                    snapshots.append(target)
                    valid[0] = False
                    with self.assertRaises(RuntimeError):
                        kvp.set_persistent("plugin-value", "stale")
            with patch.object(kvp, "_persistent_dir", side_effect=AssertionError("global filesystem accessed")):
                await asyncio.gather(worker("a"), worker("b"))
            self.assertEqual({row["runtime:plugin-value"] for row in snapshots}, {"a", "b"})
        asyncio.run(scenario())

    def test_hooks_validate_explicit_constructor_manifest_without_running_hook(self):
        path = "tests/test_durable_state_adapters.py"
        state.register(state.StateAdapter("synthetic_constructor", 1, (), (path,),
            (state.Hook("agent_init", "synthetic.SafeInitializer", path, "constructor"),)))
        implementation = {"class": "synthetic.SafeInitializer", "source": state._source(path)}
        hooks = {"agent_init": [implementation]}
        manifest = state.capture_hooks(hooks, boundary="constructor")
        state.validate_hooks(manifest, hooks, boundary="constructor")
        with self.assertRaises(state.StateHeld):
            state.capture_hooks(hooks, boundary="continuation")
        implementation["source"] = "0" * 64
        with self.assertRaises(state.StateHeld):
            state.validate_hooks(manifest, hooks, boundary="constructor")

    def test_unknown_callback_queries_never_launch_effect_and_known_receipt_commits_once(self):
        from helpers.durable.store import LocalStore
        import tempfile
        implementation = {"name": known_query.__module__ + "." + known_query.__qualname__,
                          "source": hashlib.sha256(Path(inspect.getsourcefile(known_query)).read_bytes()).hexdigest()}
        with tempfile.TemporaryDirectory() as temporary, LocalStore(Path(temporary).resolve()) as store:
            run = store.admit("context", "input", {}, {})
            call_id = "scheduler:on_success"
            store.start_call(run["run_id"], call_id, "scheduler_callback",
                             {"query_implementation": implementation, "receipt": "external-known"})
            calls = []
            def sync(method, *args):
                calls.append(method)
                if method == "assert_owner":
                    return None
                return getattr(store, method)(*args)
            owner = SimpleNamespace(sync=sync)
            result = state.reconcile_callback(owner, run["run_id"], call_id, known_query,
                                                   implementation=implementation, mask=lambda value: value)
            repeated = state.reconcile_callback(owner, run["run_id"], call_id, known_query,
                                                     implementation=implementation, mask=lambda value: value)
            self.assertEqual(result, repeated)
            self.assertEqual(calls.count("finish_call"), 1)
            self.assertEqual(result["result"], {"receipt": "external-known"})


if __name__ == "__main__":
    unittest.main()


# Reuse the real shared-service harness for scheduled resource continuation.
try:
    import pytest
except ImportError:
    pytest = None
if pytest is not None:
    from test_durable_cluster import nodes
    from test_durable_runtime import rig

    def test_shared_scheduled_project_and_attachment_survive_next_worker_continuation(nodes, monkeypatch, tmp_path):
        from datetime import datetime, timedelta, timezone
        from cryptography.fernet import Fernet
        from helpers import projects, task_scheduler as scheduler
        from helpers.durable import runtime
        from helpers.durable.cluster import RunHandle
        from helpers.durable.resources import ResourceManager
        from helpers.tool import Response
        from tools.response import ResponseTool
        monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
        monkeypatch.setattr(projects, "PROJECTS_PARENT_DIR", str(tmp_path / "projects"))
        monkeypatch.setattr(scheduler, "SCHEDULER_FOLDER", str(tmp_path / "unused-task-files"))
        monkeypatch.setattr(scheduler.TaskScheduler, "_instance", None)
        monkeypatch.setattr(scheduler.SchedulerTaskList, "_SchedulerTaskList__instance", None)
        monkeypatch.setattr(scheduler, "initialize_agent", lambda: nodes.rig.context.config)
        now = datetime(2026, 10, 22, 10, 0, 20, tzinfo=timezone.utc)
        monkeypatch.setattr(scheduler, "_now", lambda: now)
        project = "scheduled-portable-project"
        root = Path(projects.get_project_folder(project))
        root.mkdir(parents=True)
        (root / "value.txt").write_text("owner checkout")
        attachment = tmp_path / "input.txt"
        attachment.write_text("known attachment input")
        seen = []
        async def edit(self, **kwargs):
            path = Path(projects.get_project_folder(project))
            assert path != root
            seen.append((path / "value.txt").read_text())
            (path / "value.txt").write_text("committed scheduled edit")
            return Response(message="Done", break_loop=True)
        monkeypatch.setattr(ResponseTool, "execute", edit)
        engine = scheduler.TaskScheduler.get()
        task = scheduler.PlannedTask(name="Portable scheduled task", prompt="Do work", system_prompt="System",
            context_id=nodes.rig.context.id, project_name=project, attachments=[str(attachment)],
            plan=scheduler.TaskPlan(todo=[now - timedelta(minutes=1), now + timedelta(hours=1)]))
        asyncio.run(engine.add_task(task))
        asyncio.run(engine.tick())
        first, = nodes.first.sync("list_run_headers")
        assert RunHandle(nodes.first, first["run_id"]).result_sync(timeout=10) == "Done"
        completed = nodes.first.sync("get_run", first["run_id"])
        ref, = completed["checkpoint"]["resources"]["attachments"]
        assert ResourceManager(nodes.first, nodes.rig.context.id).get_bytes(ref) == b"known attachment input"
        # Another host receives the next occurrence with the committed workspace,
        # rather than restoring the submitting host's unchanged owner checkout.
        for node in (nodes.first, nodes.second):
            context = node.contexts.get(first["run_id"])
            if context and context.task:
                context.task.result_sync(timeout=10)
        monkeypatch.setattr(runtime, "_service", nodes.second)
        monkeypatch.setattr(scheduler, "_now", lambda: now + timedelta(hours=2))
        asyncio.run(engine.tick())
        headers = nodes.second.sync("list_run_headers")
        latest = max(headers, key=lambda row: row["admission_seq"])
        assert RunHandle(nodes.second, latest["run_id"]).result_sync(timeout=10) == "Done"
        assert seen == ["owner checkout", "committed scheduled edit"]
        assert (root / "value.txt").read_text() == "owner checkout"
        assert not (tmp_path / "unused-task-files").exists()
