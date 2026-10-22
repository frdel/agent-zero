"""Owner-prepared UI messages with durable preparation receipts."""
from __future__ import annotations

import hashlib


# These hooks only gate model configuration or project an idempotently named
# local update notification. Neither sends the user's message to a provider.
UI_PREPARATION_HOOKS = {
    ("UpdateCheck", "52cf96f36419ed2170beeb307a79eb84715557c54645d47861b6eab309af2fd6"),
    ("CheckChatModel", "e14a96f618722e1c72b14483c9225cdf0b27c84a7b813ac3eaa8902b3f7c12fd"),
}


def _can_reprepare(context, expected):
    from helpers import extension
    from helpers.durable.codec import identity
    current = [identity(cls) for cls in extension._get_extension_classes("user_message_ui", agent=context.agent0)]
    if current != expected:
        return False
    for item in current:
        if (item["class"].split(".")[-1], item["source"]) not in UI_PREPARATION_HOOKS:
            return False
    return True


async def prepare(owner, context, run_id, payload, call_id, *, initial=False):
    from helpers import extension
    from helpers.durable import codec
    from helpers.durable.resources import ResourceManager, capture_attachments, materialize_attachments
    from helpers.durable.runtime import RecoveryHeld
    owner.sync("assert_owner", run_id)
    hooks = [codec.identity(cls) for cls in extension._get_extension_classes("user_message_ui", agent=context.agent0)]
    descriptor = {"message": payload, "hooks": hooks}
    previous = owner.sync("get_call", run_id, call_id)
    if previous:
        # Old input_ui records predate the explicit hook descriptor. Their
        # completed results remain authoritative; uncertain old hooks hold.
        if previous["status"] == "completed" and previous.get("result"):
            return previous["result"]
        if previous["payload"] != descriptor or not _can_reprepare(context, hooks):
            raise RecoveryHeld("ui_input_outcome_unknown")
    else:
        owner.sync("start_call", run_id, call_id, "input_ui", descriptor)
    manager = ResourceManager(owner, context.id, run_id)
    local = materialize_attachments(manager, payload, context)
    data = {"message": local["message"], "attachment_paths": local["attachments"]}
    await extension.call_extensions_async("user_message_ui", agent=context.agent0, data=data)
    owner.sync("assert_owner", run_id)
    if (not isinstance(data.get("message"), str) or not isinstance(data.get("attachment_paths"), list)
            or any(not isinstance(path, str) for path in data["attachment_paths"])):
        raise RecoveryHeld("ui_input_adapter_required")
    return_value = {"message": codec.masked(context.agent0, {
        **payload, "message": data["message"],
        "attachments": capture_attachments(manager, data["attachment_paths"])}),
        "model_not_configured": bool(data.get("model_not_configured"))}
    if initial:
        context._durable_ui_input_pending = False
        if not return_value["model_not_configured"]:
            owner._log_input(context, return_value["message"])
        owner.sync("finish_call", run_id, call_id, return_value,
                   checkpoint=codec.checkpoint(context.agent0), phase="ui_input_ready")
    else:
        owner.sync("finish_call", run_id, call_id, return_value)
    return return_value


def intervention(owner, context, run_id, command):
    """Start preparation on the context's loop; return only a committed result."""
    from helpers.defer import DeferredTask
    from helpers.durable.runtime import RecoveryHeld
    key = "ui:" + hashlib.sha256(command["request_id"].encode()).hexdigest()
    previous = owner.sync("get_call", run_id, key)
    if previous and previous["status"] == "completed":
        return previous["result"]
    tasks = getattr(context, "_durable_ui_tasks", None)
    if tasks is None:
        tasks = context._durable_ui_tasks = {}
    task = tasks.get(key)
    if task is None:
        if any(not pending.is_ready() for pending in tasks.values()):
            return None
        thread = context.task.event_loop_thread.thread_name if context.task else "DurableUiInput"
        task = DeferredTask(thread).start_task(prepare, owner, context, run_id, command["payload"]["message"], key)
        tasks[key] = task
        return None
    if not task.is_ready():
        return None
    try:
        return task.result_sync(timeout=0)
    except RecoveryHeld:
        raise
    except Exception:
        raise RecoveryHeld("ui_input_preparation_failed") from None
