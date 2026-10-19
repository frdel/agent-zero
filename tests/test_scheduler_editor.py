"""Scheduler prompt editing and human-editable task persistence."""
import asyncio
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers import task_scheduler as scheduler
from plugins._scheduler.api.scheduler_task_create import SchedulerTaskCreate


def test_scheduler_json_default_and_optional_yaml():
    common = dict(
        name="Prompt editing", system_prompt="First line\n  Keep indentation: # sì\n",
        prompt="Check these values:\ntrue\n123\n*\n\n", state="disabled",
        created_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        attachments=["/tmp/report.md"], last_result="A result\nwith two lines",
    )
    original = scheduler.SchedulerTaskList(tasks=[
        scheduler.AdHocTask(**common, token="000123"),
        scheduler.ScheduledTask(**common, schedule=scheduler.TaskSchedule(
            minute="30", hour="9", day="*", month="*", weekday="*", timezone="Europe/Rome",
        )),
        scheduler.PlannedTask(**common, plan=scheduler.TaskPlan(
            todo=[datetime(2026, 10, 1, 9, tzinfo=timezone.utc)],
        )),
    ])
    expected = original.model_dump(mode="json")
    for extension in ("json", "yaml"):
        with TemporaryDirectory() as folder, patch.object(scheduler, "SCHEDULER_FOLDER", folder), patch.object(
            scheduler.SchedulerTaskList, "_SchedulerTaskList__instance", None,
        ):
            path = Path(folder, f"tasks.{extension}")
            text = original.model_dump_json() if extension == "json" else scheduler.yaml.dumps(expected)
            path.write_text(text, encoding="utf-8")
            tasks = scheduler.SchedulerTaskList.get()
            assert tasks.model_dump(mode="json") == expected
            assert path.read_text(encoding="utf-8") == text, "loading must not rewrite the file"
            asyncio.run(tasks.save())
            assert list(Path(folder).iterdir()) == [path], "saving must not migrate formats"
            assert yaml.safe_load(path.read_text(encoding="utf-8")) == expected

            path.write_text(path.read_text(encoding="utf-8").replace("First line", "Edited externally"), encoding="utf-8")
            asyncio.run(tasks.reload())
            assert all(task.system_prompt.startswith("Edited externally\n") for task in tasks.tasks)
            before = tasks.model_dump(mode="json")
            for invalid in ("tasks: [", "", '{"tasks":{}}', '{"tasks":[{"type":"unknown"}]}', "!!python/object:builtins.object {}"):
                path.write_text(invalid, encoding="utf-8")
                try:
                    asyncio.run(tasks.reload())
                except (ValueError, yaml.YAMLError):
                    pass
                else:
                    raise AssertionError("Invalid task data was accepted")
                assert tasks.model_dump(mode="json") == before
                assert path.read_text(encoding="utf-8") == invalid

            path.write_text(text, encoding="utf-8")
            json_path, yaml_path = Path(folder, "tasks.json"), Path(folder, "tasks.yaml")
            json_path.write_text(original.model_dump_json(), encoding="utf-8")
            yaml_path.write_text("tasks: []\n", encoding="utf-8")
            with patch.object(scheduler.yaml, "loads", side_effect=AssertionError("JSON must not use YAML parsing")):
                asyncio.run(tasks.reload())
                assert tasks.model_dump(mode="json") == expected
                asyncio.run(tasks.remove_task_by_uuid(tasks.tasks[0].uuid))
            assert len(json.loads(json_path.read_text())["tasks"]) == 2
            assert yaml_path.read_text() == "tasks: []\n", "JSON takes precedence without changing YAML"

    with TemporaryDirectory() as folder, patch.object(scheduler, "SCHEDULER_FOLDER", folder), patch.object(
        scheduler.SchedulerTaskList, "_SchedulerTaskList__instance", None,
    ):
        assert scheduler.SchedulerTaskList.get().tasks == []
        assert json.loads(Path(folder, "tasks.json").read_text()) == {"tasks": []}
        assert not Path(folder, "tasks.yaml").exists()


def test_scheduler_due_tasks_and_execution_guards_in_both_formats():
    now = datetime(2026, 9, 24, 8, 30, 30, tzinfo=timezone.utc)
    common = dict(name="Execution check", system_prompt="", prompt="Check scheduler state")
    templates = [
        scheduler.AdHocTask(**common),
        scheduler.ScheduledTask(**common, schedule=scheduler.TaskSchedule(
            minute="30", hour="10", day="*", month="*", weekday="*", timezone="Europe/Rome",
        )),
        scheduler.PlannedTask(**common, plan=scheduler.TaskPlan(todo=[now - timedelta(minutes=1)])),
    ]
    data = scheduler.SchedulerTaskList(tasks=[
        task.__class__.model_validate({**task.model_dump(), "uuid": f"{task.type.value}-{state.value}", "state": state})
        for task in templates for state in scheduler.TaskState
    ])

    async def check(engine):
        due = await engine._tasks.get_due_tasks()
        assert {task.uuid for task in due} == {"scheduled-idle", "planned-idle"}
        for task in list(engine.get_tasks()):
            if task.state in (scheduler.TaskState.DISABLED, scheduler.TaskState.RUNNING):
                try:
                    await engine.run_task_by_uuid(task.uuid)
                except ValueError:
                    pass
                else:
                    raise AssertionError("A disabled or running task was started")
            else:
                await engine.run_task_by_uuid(task.uuid)
                assert engine._run_task.call_args.args[0].state == scheduler.TaskState.IDLE
        assert engine._run_task.await_count == 6

        claim = await engine.update_task_checked(
            "planned-idle", lambda task: task.state == scheduler.TaskState.IDLE, state=scheduler.TaskState.RUNNING,
        )
        assert claim is not None
        assert await engine.update_task_checked(
            "planned-idle", lambda task: task.state == scheduler.TaskState.IDLE, state=scheduler.TaskState.RUNNING,
        ) is None
        await claim.on_run()
        await claim.on_success("Result\nwith preserved line breaks")
        await claim.on_finish()
        await engine.reload()
        finished = engine.get_task_by_uuid("planned-idle")
        assert finished.state == scheduler.TaskState.IDLE
        assert finished.last_run == now
        assert finished.last_result == "Result\nwith preserved line breaks"
        assert finished.plan.todo == [] and finished.plan.in_progress is None
        assert finished.plan.done == [now - timedelta(minutes=1)]
        assert "planned-idle" not in {task.uuid for task in await engine._tasks.get_due_tasks()}

        failed = engine.get_task_by_uuid("adhoc-idle")
        await failed.on_error("Expected failure")
        await engine.reload()
        assert engine.get_task_by_uuid(failed.uuid).state == scheduler.TaskState.ERROR
        assert engine.get_task_by_uuid(failed.uuid).last_result == "ERROR: Expected failure"

    for extension in ("json", "yaml"):
        with TemporaryDirectory() as folder, patch.object(scheduler, "SCHEDULER_FOLDER", folder), patch.object(
            scheduler, "_now", return_value=now,
        ), patch("helpers.state_monitor_integration.mark_dirty_all"):
            content = data.model_dump_json() if extension == "json" else scheduler.yaml.from_json(data.model_dump_json())
            Path(folder, f"tasks.{extension}").write_text(content, encoding="utf-8")
            engine = object.__new__(scheduler.TaskScheduler)
            engine._tasks = asyncio.run(scheduler.SchedulerTaskList().reload())
            engine._run_task = AsyncMock()
            with patch.object(scheduler.TaskScheduler, "get", return_value=engine):
                asyncio.run(check(engine))


def test_scheduler_creation_applies_state_before_persistence():
    states = []
    fake = SimpleNamespace(
        reload=AsyncMock(), add_task=AsyncMock(side_effect=lambda task: states.append(task.state)),
        get_task_by_uuid=lambda _uuid: fake.add_task.call_args.args[0],
    )
    with patch.object(scheduler.TaskScheduler, "get", return_value=fake):
        for config in ({}, {"schedule": "0 9 * * *"}, {"plan": {"todo": ["2026-10-01T09:00:00+00:00"]}}):
            for state in ({}, {"state": "disabled"}):
                result = asyncio.run(SchedulerTaskCreate(None, None).process({
                    "name": "Initial state", "prompt": "Keep disabled until enabled", **config, **state,
                }, None))
                assert result["ok"]
                assert states[-1] == state.get("state", "idle") == result["task"]["state"]


def test_scheduler_editor_preserves_drafts_until_save_succeeds():
    source = (PROJECT_ROOT / "plugins/_scheduler/webui/scheduler/scheduler-store.js").read_text()
    source = re.sub(r"^import\b[\s\S]*?;\n", "", source, flags=re.M)
    source = source.replace("export { store };", "")
    script = r'''
import assert from 'node:assert/strict';
const window = { localStorage: { getItem: () => null }, alert: assert.fail };
const createStore = (_name, model) => model;
const getUserTimezone = () => 'Europe/Rome';
let response, sent, destroyed = 0;
const errors = [], opened = [], closed = [];
const openModal = async path => opened.push(path);
const closeModal = async path => closed.push(path);
const notificationsStore = { frontendError: message => errors.push(message), frontendSuccess() {} };
const fetchApi = async (_endpoint, options) => {
  sent = JSON.parse(options.body);
  if (response instanceof Error) throw response;
  return response;
};
''' + source + r'''
store.destroyFlatpickr = () => destroyed++;
for (const isCreating of [true, false]) {
  store.isCreating = isCreating;
  store.isEditing = !isCreating;
  store.editingTask = defaultEditingTask({
    uuid: 'task-id', type: 'adhoc', name: 'Task', token: '123',
    system_prompt: 'Keep\nall instructions', prompt: 'A long prompt\nwith edits\n',
  });
  const draft = store.editingTask;
  for (const failure of [
    { ok: true, json: async () => ({ error: 'Invalid task' }) },
    { ok: false, json: async () => ({ error: 'Save failed' }) },
    new Error('Network unavailable'),
  ]) {
    response = failure;
    await store.saveTask();
    assert.equal(store.editingTask, draft);
    assert.equal(store.isCreating, isCreating);
    assert.equal(store.isEditing, !isCreating);
    assert.equal(sent.prompt, draft.prompt);
  }
  for (const field of ['system_prompt', 'prompt']) {
    await store.openPromptEditor(field);
    assert.equal(store.promptField, field);
    store.editingTask[store.promptField] += '\nExpanded edit';
    await store.closePromptEditor();
    assert.ok(draft[field].endsWith('\nExpanded edit'));
    assert.equal(opened.at(-1), closed.at(-1));
  }
  response = { ok: true, json: async () => ({ ok: true, task: { ...draft } }) };
  await store.saveTask();
  assert.equal(store.isCreating, false);
  assert.equal(store.isEditing, false);
  assert.equal(store.editingTask.prompt, '');
  assert.equal(store.tasks.find(task => task.uuid === draft.uuid).prompt, draft.prompt);
}
assert.equal(errors.length, 6);
assert.equal(destroyed, 2, 'failed saves must leave the editor and date picker intact');
await store.openPromptEditor('name');
assert.equal(opened.length, 4, 'only prompt fields can be expanded');
store.refreshProjectOptions = async () => {};
store.projectOptions = [{ name: 'unrelated-project' }];
store.deriveActiveProject = () => null;
await store.startCreateTask();
assert.equal(store.selectedProjectSlug, '');
assert.equal(store.editingTask.project, null, 'no active project must not select an unrelated project');
'''
    subprocess.run(["node", "--input-type=module"], input=script, text=True, check=True)
