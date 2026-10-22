"""Occurrence-owned, idempotent projections for built-in scheduler tasks.

The run journal owns admission and outcomes. tasks.json/tasks.yaml is a durable
projection with an occurrence receipt; replay never invokes arbitrary callbacks.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid
from urllib.parse import urlparse

from helpers import task_scheduler as scheduler

_BUILTINS = (scheduler.AdHocTask, scheduler.ScheduledTask, scheduler.PlannedTask)
_CALLBACKS = {
    (cls, name): getattr(cls, name)
    for cls in (*_BUILTINS, scheduler.BaseTask)
    for name in ("on_run", "on_success", "on_error", "on_finish")
}


def _held(reason):
    from helpers.durable.runtime import RecoveryHeld
    raise RecoveryHeld(reason)


def implementation_fingerprint():
    return hashlib.sha256(
        Path(__file__).read_bytes() + Path(scheduler.__file__).read_bytes()
    ).hexdigest()


def _audited(task):
    cls = type(task)
    if cls not in _BUILTINS or any(
        getattr(owner, name) is not callback
        or inspect.getsourcefile(callback) != scheduler.__file__
        for (owner, name), callback in _CALLBACKS.items() if owner in cls.__mro__
    ):
        _held("scheduler_callback_adapter_required")


def _configuration(task):
    data = task.model_dump(mode="json", include={
        "type", "name", "system_prompt", "prompt", "attachments", "project_name",
        "project_color", "schedule",
    })
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _utc(value):
    return scheduler._localize_task_datetime(value).astimezone(timezone.utc).isoformat()


def scheduled_occurrence(task):
    """Stable due-window identity; manual submission deliberately gets a new ID."""
    if isinstance(task, scheduler.PlannedTask):
        launch = task.plan.should_launch()
        return "plan:" + _utc(launch) if launch else None
    if isinstance(task, scheduler.ScheduledTask):
        import pytz
        from crontab import CronTab
        zone = pytz.timezone(scheduler.normalize_schedule_timezone(task.schedule.timezone))
        reference = (scheduler._now() - timedelta(seconds=60)).astimezone(zone)
        launch = CronTab(crontab=task.schedule.to_crontab()).next(now=reference, return_datetime=True)
        if launch is not None:
            if launch.tzinfo is None:
                launch = zone.localize(launch)
            return "cron:" + _utc(launch)
    return None


async def submit(engine, task, task_context=None, *, occurrence_id=None):
    """Return False only when the ordinary legacy scheduler remains permitted."""
    from agent import UserMessage
    from helpers.durable.runtime import service
    owner = service()
    if owner is None:
        return False
    if owner.failed:
        raise RuntimeError("Local recovery storage unavailable; scheduler execution is held")
    if not owner.enabled:
        active = owner.sync("list_run_headers", ("running", "blocked", "attention"), context_id=task.context_id)
        if active:
            raise RuntimeError("A durable run owns this scheduler context; execution is held")
        return False
    _audited(task)
    if task.state == scheduler.TaskState.DISABLED:
        raise RuntimeError("Disabled scheduler task cannot be admitted")
    if getattr(owner, "distributed", False):
        return await _submit_shared(owner, engine, task, task_context, occurrence_id)
    context = await engine._get_chat_context(task)
    occurrence_id = occurrence_id or "manual:" + uuid.uuid4().hex
    launch = task.plan.should_launch() if isinstance(task, scheduler.PlannedTask) else None
    origin = {
        "kind": "scheduler", "task_uuid": task.uuid, "context_id": context.id,
        "occurrence_id": occurrence_id, "implementation": implementation_fingerprint(),
        "configuration": _configuration(task), "launch_time": _utc(launch) if launch else None,
    }
    attachments = []
    for item in task.attachments:
        if os.path.exists(item) or urlparse(item).scheme in {"http", "https", "ftp", "ftps", "sftp"}:
            attachments.append(item)
    prompt = f"## Context:\n{task_context}\n\n## Task:\n{task.prompt}" if task_context else f"## Task:\n{task.prompt}"
    context.set_data("scheduler_task_uuid", task.uuid)
    input_id = "scheduler:" + hashlib.sha256((task.uuid + ":" + occurrence_id).encode()).hexdigest()
    message = UserMessage(message=prompt, system_message=[task.system_prompt], attachments=attachments, id=input_id)
    deferred = owner.submit_owned(context, message, origin)
    _register_occurrence(engine, task.uuid, deferred, context.id, input_id)
    return True


async def _submit_shared(owner, engine, task, task_context, occurrence_id):
    """Admit from shared history; host-local chat files never seed an occurrence."""
    from agent import UserMessage
    from helpers.durable import codec
    from helpers.durable.cluster import portable, RunHandle, latest_header, seed_context
    occurrence_id = occurrence_id or "manual:" + uuid.uuid4().hex
    input_id = "scheduler:" + hashlib.sha256((task.uuid + ":" + occurrence_id).encode()).hexdigest()
    headers = owner.sync("list_run_headers", context_id=task.context_id)
    duplicate = next((row for row in headers if row["input_id"] == input_id), None)
    if duplicate:
        handle = RunHandle(owner, duplicate["run_id"])
        _register_occurrence(engine, task.uuid, handle, task.context_id, input_id)
        owner.dispatch_for_run(duplicate["run_id"])
        return True
    if headers:
        latest = latest_header(owner, headers)
        previous = owner.sync("get_run", latest["run_id"])
        data, generation = seed_context(owner, previous, task.context_id)
    else:
        from helpers import settings
        data = codec.context_seed(task.context_id, task.name,
            profile=str(settings.get_settings().get("agent_profile") or ""),
            data={"scheduler_task_uuid": task.uuid, **({"project": task.project_name} if task.project_name else {})})
        generation = owner.sync("document_generation", task.context_id)
    launch = task.plan.should_launch() if isinstance(task, scheduler.PlannedTask) else None
    origin = {"kind": "scheduler", "task_uuid": task.uuid, "context_id": task.context_id,
              "occurrence_id": occurrence_id, "implementation": implementation_fingerprint(),
              "configuration": _configuration(task), "launch_time": _utc(launch) if launch else None}
    data.update(origin=origin, paused=False, terminal=None, intervention=None, result=None, ui_input_pending=False)
    data["context"]["data"]["scheduler_task_uuid"] = task.uuid
    prompt = f"## Context:\n{task_context}\n\n## Task:\n{task.prompt}" if task_context else f"## Task:\n{task.prompt}"
    message = UserMessage(prompt, system_message=[task.system_prompt],
                          attachments=list(task.attachments), id=input_id)
    # Capture immutable resource bytes on the submitting host. Restoration and
    # execution occur only after the coordinator wins the context claim.
    from helpers.durable import resources
    context_data = data["context"]["data"]
    state = dict(data.get("resources") or {"version": 1})
    if task.project_name:
        if context_data.get("project") != task.project_name:
            state.pop("workspace", None)
        context_data["project"] = task.project_name
    projection = SimpleNamespace(id=task.context_id, _durable_resources=state,
                                 get_data=lambda key: context_data.get(key))
    resources.capture_context(owner, projection, message)
    data["resources"] = resources.checkpoint_state(projection)
    data = resources.canonical_value(projection, data)
    payload = resources.canonical_value(projection,
        owner._mask_payload(task.context_id, codec.message_payload(message)))
    if not portable(data, payload):
        _held("distributed_scheduler_resource_adapter_required")
    run = owner.sync("admit", task.context_id, input_id, payload, data, expected_generation=generation)
    handle = RunHandle(owner, run["run_id"])
    _register_occurrence(engine, task.uuid, handle, task.context_id, input_id)
    owner.dispatch_for_run(run["run_id"])
    return True


def _register_occurrence(engine, task_uuid, deferred, context_id, input_id):
    """Register one future/occurrence, not a reusable DeferredTask container."""
    deferred._durable_scheduler_context_id = context_id
    deferred._durable_scheduler_input_id = input_id
    future = getattr(deferred, "_future", None)
    engine._register_running_task(task_uuid, deferred)
    def release(completed):
        if future is not None and (completed is not future or getattr(deferred, "_future", None) is not future):
            return
        if getattr(deferred, "_durable_scheduler_input_id", None) != input_id:
            return
        engine._unregister_running_task(task_uuid, deferred)
    deferred.add_done_callback(release)


def _origin(context, run):
    origin = run["checkpoint"].get("origin") or {}
    if origin.get("kind") != "scheduler" or origin.get("context_id") != context.id or run["context_id"] != context.id:
        _held("scheduler_ownership_changed")
    if not isinstance(origin.get("occurrence_id"), str) or not origin["occurrence_id"]:
        _held("scheduler_occurrence_missing")
    if origin.get("implementation") != implementation_fingerprint():
        _held("scheduler_implementation_changed")
    return origin


def _validate(task, context, origin):
    if task is None or task.context_id != context.id:
        _held("scheduler_task_removed_or_reassigned")
    _audited(task)
    if _configuration(task) != origin["configuration"]:
        _held("scheduler_configuration_changed")
    if task.state == scheduler.TaskState.DISABLED:
        _held("scheduler_task_disabled")


async def _receipt(owner, run, label, origin, result):
    call_id = "scheduler:" + label
    await owner.io("start_call", run["run_id"], call_id, "scheduler_projection", {
        "task_uuid": origin["task_uuid"], "occurrence_id": origin["occurrence_id"],
    }, replay="safe")
    await owner.io("finish_call", run["run_id"], call_id, result)


async def _attention_reopen_allowed(owner, run):
    if run["status"] != "running":
        return False
    approval, attention = 0, 0
    for event in await owner.io("read_events", run["run_id"]):
        payload = event.get("payload") or {}
        if event["kind"] == "transition" and payload.get("status") == "attention":
            attention = event["seq"]
        if event["kind"] == "retry_granted" or (event["kind"] == "operator_resolution" and payload.get("decision") == "resume"):
            approval = event["seq"]
    return approval > attention


async def prepare(owner, context, run):
    """Claim exactly this task occurrence and its planned launch before effects."""
    origin = _origin(context, run)
    engine = scheduler.TaskScheduler.get()
    reopen = await _attention_reopen_allowed(owner, run)

    def project(task):
        _validate(task, context, origin)
        if task.durable_occurrence_id == origin["occurrence_id"]:
            if task.durable_run_id != run["run_id"]:
                _held("scheduler_run_ownership_changed")
            if task.durable_finished_occurrence_id == origin["occurrence_id"]:
                if task.durable_status != "attention" or not reopen:
                    _held("scheduler_occurrence_already_finished")
                # Operator continuation owns the same occurrence. Its plan slot
                # may already be in done; do not claim or advance another slot.
                task.durable_finished_occurrence_id = None
                task.durable_status = "running"
                task.state = scheduler.TaskState.RUNNING
                task.updated_at = scheduler._now()
            return
        if task.state == scheduler.TaskState.RUNNING:
            _held("scheduler_occurrence_already_running")
        launch = datetime.fromisoformat(origin["launch_time"]) if origin.get("launch_time") else None
        if isinstance(task, scheduler.PlannedTask) and launch is not None:
            if task.plan.in_progress is not None:
                _held("scheduler_plan_already_running")
            if launch not in task.plan.todo:
                _held("scheduler_plan_changed")
            task.plan.set_in_progress(launch)
        task.durable_occurrence_id = origin["occurrence_id"]
        task.durable_run_id = run["run_id"]
        task.durable_status = "running"
        task.state = scheduler.TaskState.RUNNING
        task.updated_at = scheduler._now()

    updated = await engine._tasks.update_task_by_uuid(origin["task_uuid"], project)
    if updated is None:
        _held("scheduler_task_removed_or_reassigned")
    if context.task is not None:
        # Recovered tasks do not pass through submit's in-memory registration.
        deferred = context.task
        _register_occurrence(engine, origin["task_uuid"], deferred, context.id, run["input_id"])
    _publish()
    await _receipt(owner, run, "prepare", origin, {"prepared": True})


async def complete(owner, context, run, result):
    """Project built-in success/finish atomically, without rerunning callbacks."""
    from helpers.durable.codec import masked
    origin = _origin(context, run)
    receipt = await owner.io("get_call", run["run_id"], "scheduler:complete")
    if receipt and receipt["status"] == "completed":
        return
    engine = scheduler.TaskScheduler.get()
    result = masked(context.agent0, str(result))
    skipped = False
    reopen = await _attention_reopen_allowed(owner, run)

    def project(task):
        nonlocal skipped
        # A user removal/reassignment/disable wins over historical completion.
        if task.context_id != context.id or task.state == scheduler.TaskState.DISABLED:
            skipped = True
            return
        _validate(task, context, origin)
        if task.durable_occurrence_id != origin["occurrence_id"] or task.durable_run_id != run["run_id"]:
            _held("scheduler_run_ownership_changed")
        if task.durable_finished_occurrence_id == origin["occurrence_id"]:
            if task.durable_status == "completed":
                return
            if task.durable_status != "attention" or not reopen:
                _held("scheduler_occurrence_already_stopped")
        _finish_plan(task, origin)
        task.state = scheduler.TaskState.IDLE
        task.last_run = scheduler._now()
        task.updated_at = task.last_run
        task.last_result = result
        task.durable_finished_occurrence_id = origin["occurrence_id"]
        task.durable_status = "completed"

    updated = await engine._tasks.update_task_by_uuid(origin["task_uuid"], project)
    if updated is not None:
        _publish()
    await _receipt(owner, run, "complete", origin, {"completed": True, "skipped": skipped or updated is None})


def _finish_plan(task, origin):
    if isinstance(task, scheduler.PlannedTask) and origin.get("launch_time"):
        launch = datetime.fromisoformat(origin["launch_time"])
        if task.plan.in_progress == launch:
            task.plan.set_done(launch)
        elif launch not in task.plan.done:
            _held("scheduler_plan_ownership_changed")


async def halted(owner, context, run, status):
    """Project cancellation/attention only for the prepared owning occurrence."""
    origin = _origin(context, run)
    engine = scheduler.TaskScheduler.get()

    def project(task):
        if task.context_id != context.id or task.state == scheduler.TaskState.DISABLED:
            return
        _audited(task)
        if task.durable_occurrence_id != origin["occurrence_id"] or task.durable_run_id != run["run_id"]:
            if status != "cancelled" or task.state == scheduler.TaskState.RUNNING or _configuration(task) != origin["configuration"]:
                return
            # Stop can win before preparation. Consume this admitted planned
            # occurrence so the next scheduler tick cannot revive it or stall
            # forever on its retained todo item.
            launch = datetime.fromisoformat(origin["launch_time"]) if origin.get("launch_time") else None
            if isinstance(task, scheduler.PlannedTask) and launch is not None:
                if task.plan.in_progress is not None or launch not in task.plan.todo:
                    return
                task.plan.set_in_progress(launch)
            task.durable_occurrence_id = origin["occurrence_id"]
            task.durable_run_id = run["run_id"]
        if task.durable_finished_occurrence_id == origin["occurrence_id"]:
            return
        _finish_plan(task, origin)
        task.state = scheduler.TaskState.IDLE if status == "cancelled" else scheduler.TaskState.ERROR
        task.last_run = scheduler._now()
        task.updated_at = task.last_run
        if status != "cancelled":
            task.last_result = "ERROR: Local recovery needs attention; the interrupted action was not retried."
        task.durable_finished_occurrence_id = origin["occurrence_id"]
        task.durable_status = status

    if await engine._tasks.update_task_by_uuid(origin["task_uuid"], project) is not None:
        _publish()


def _publish():
    from helpers.state_monitor_integration import mark_dirty_all
    mark_dirty_all(reason="durability.scheduler_projection")
