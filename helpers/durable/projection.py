"""Read-only WebUI views of shared checkpoints; never construct agent contexts."""
from __future__ import annotations

import hashlib
import json

from helpers.durable.store import IntegrityError, StaleRunError


def _source(owner, header, fallback):
    context_id = header["context_id"] if header else fallback["key"][5:]
    data, checkpoint, revision = {}, {}, 0
    if header:
        run = owner.sync("get_run", header["run_id"])
        header = {**header, **{key: run[key] for key in ("status", "phase", "generation", "checkpoint_seq")}}
        checkpoint = run.get("checkpoint") or {}
        if not checkpoint:
            head = owner.sync("get_context_head", context_id)
            if head and head["run_id"] == run["run_id"]:
                checkpoint = head["checkpoint"]
        data = checkpoint.get("context") or {}
        revision = run.get("checkpoint_seq", header.get("checkpoint_seq", 0))
    else:
        data = fallback["value"]
        revision = fallback["version"]
    if data and data.get("id") != context_id:
        raise ValueError("Shared context identity differs")
    # Reset/delete are database decisions even before a new input is admitted.
    generation = owner.sync("document_generation", context_id)
    reset = bool(header and generation != header["generation"])
    log = {} if reset else data.get("log", {})
    logs = log.get("logs") or []
    if not isinstance(logs, list) or any(not isinstance(item, dict) for item in logs):
        raise ValueError("Invalid shared log projection")
    logs = [{key: value for key, value in item.items() if key in {
        "no", "id", "type", "heading", "content", "kvps", "timestamp", "agentno"}} for item in logs]
    # A serialized log contains current items, not the process-local updates
    # vector. Replay the bounded current log when the checkpoint changes. A
    # stable generation/window GUID keeps ordinary checkpoint updates incremental.
    window = logs[0].get("no", 0) if logs else 0
    guid_data = [context_id, generation, header["run_id"] if header else "genesis",
                 log.get("guid", ""), window]
    guid = hashlib.sha256(json.dumps(guid_data, separators=(",", ":")).encode()).hexdigest()
    return {"id": context_id, "data": data, "log": log, "logs": logs, "guid": guid,
            "revision": revision, "header": header, "reset": reset, "checkpoint": checkpoint}


def inventory(owner, selected=None, *, include_collections=True):
    """Select current admissions by DB sequence; stale chat caches cannot win."""
    latest = {}
    headers = owner.sync("list_run_headers", context_id=selected) if selected and not include_collections else owner.sync("list_run_headers")
    for header in headers:
        previous = latest.get(header["context_id"])
        key = (header.get("admission_seq", 0), header["run_id"])
        if previous is None or key > (previous.get("admission_seq", 0), previous["run_id"]):
            latest[header["context_id"]] = header
    if include_collections:
        fallbacks = {row["key"][5:]: row for row in owner.sync("list_projections", "chat:")}
    elif selected:
        value = owner.sync("get_projection", "chat:" + selected)
        fallbacks = {selected: dict(value, key="chat:" + selected)} if value else {}
    else:
        fallbacks = {}
    result = {}
    for context_id in sorted(latest.keys() | fallbacks.keys()):
        try:
            source = _source(owner, latest.get(context_id), fallbacks.get(context_id))
        except StaleRunError:
            continue  # deleted contexts must never reappear from old headers
        except (IntegrityError, KeyError, ValueError):
            continue
        if source["data"].get("type") != "background":
            result[context_id] = source
    return result


def _row(source, labels, number):
    data, header = source["data"], source["header"]
    status = header["status"] if header and not source["reset"] else "idle"
    profile = str(data.get("agent_profile") or "")
    row = {"id": source["id"], "name": data.get("name") or "", "no": number,
           "created_at": data.get("created_at") or "1970-01-01T00:00:00+00:00",
           "last_message": data.get("last_message") or data.get("created_at") or "1970-01-01T00:00:00+00:00",
           "type": data.get("type") or "user", "log_guid": source["guid"],
           "log_version": source["revision"], "log_length": len(source["logs"]),
           "paused": not source["reset"] and (status == "blocked" or bool(source["checkpoint"].get("paused"))),
           "running": status == "running", "agent_profile": profile,
           "agent_profile_label": labels.get(profile, profile) if profile else ""}
    for key in ("parent_context_id", "parent_agent_number", "parent_context_kind", "parent_context_label", "subordinate_slot"):
        if key in data.get("output_data", {}):
            row[key] = data["output_data"][key]
    if header:
        row["durability"] = {"run_id": header["run_id"], "status": status, "projection": "committed"}
    return row


def build_snapshot(owner, request, *, include_collections=True, labels=None):
    from agent import AgentContext
    from helpers.task_scheduler import SchedulerTaskList, serialize_task
    sources = inventory(owner, request.context, include_collections=include_collections)
    active = sources.get(request.context)
    ctxs, tasks = [], []
    if include_collections:
        saved = owner.sync("get_projection", "scheduler:tasks")
        definitions = SchedulerTaskList.model_validate(saved["value"] if saved else {"tasks": []})
        task_by_context = {task.context_id: task for task in definitions.tasks if task.uuid == task.context_id}
        for index, source in enumerate(sources.values(), 1):
            row = _row(source, labels or {}, index)
            task = task_by_context.get(source["id"])
            if task is None:
                ctxs.append(row)
                continue
            details = serialize_task(task)
            row.update({key: value for key, value in details.items() if key in {
                "uuid", "state", "type", "system_prompt", "prompt", "last_run", "last_result",
                "attachments", "context_id", "schedule", "plan", "token"}})
            row["task_name"] = details["name"]
            tasks.append(row)
        ctxs.sort(key=lambda row: row["created_at"], reverse=True)
        tasks.sort(key=lambda row: row["created_at"], reverse=True)
    logs, guid, version, progress, progress_active, paused = [], "", 0, 0, False, False
    if active:
        guid, version = active["guid"], active["revision"]
        # Equality is the only reusable cursor: a different checkpoint can update
        # existing items without changing their count. Older/newer cursors both
        # receive all current items, and new GUIDs trigger the client's full resync.
        logs = active["logs"] if request.log_from != version or request.log_from == 0 else []
        header = active["header"]
        status = header["status"] if header and not active["reset"] else "idle"
        paused = not active["reset"] and (status == "blocked" or bool(active["checkpoint"].get("paused")))
        progress_active = status == "running" and not paused
        progress = ("Paused" if paused else "Recovery needs attention" if status == "attention"
                    else "Complete" if status == "completed" else "Stopped" if status == "cancelled"
                    else "Waiting for input" if active["reset"] or not header
                    else "Saved progress: " + str(active["log"].get("progress") or "Working"))
    notifications, notifications_guid, notifications_version = AgentContext.get_notification_manager().output_with_state(start=request.notifications_from)
    return {"deselect_chat": bool(request.context) and active is None,
            "context": active["id"] if active else "", "contexts": ctxs if include_collections else None,
            "tasks": tasks if include_collections else None, "logs": logs, "log_guid": guid,
            "log_version": version, "log_progress": progress, "log_progress_active": progress_active,
            "paused": paused, "notifications": notifications, "notifications_guid": notifications_guid,
            "notifications_version": notifications_version}
