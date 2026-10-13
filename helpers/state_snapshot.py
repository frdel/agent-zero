from __future__ import annotations

import types
from typing import Any, Mapping, TypedDict, Union, get_args, get_origin, get_type_hints

from dataclasses import dataclass, replace

import pytz  # type: ignore[import-untyped]

from agent import AgentContext, AgentContextType

from helpers.dotenv import get_dotenv_value
from helpers.localization import Localization
from helpers.task_scheduler import TaskScheduler


class SnapshotV1(TypedDict):
    deselect_chat: bool
    context: str
    contexts: list[dict[str, Any]] | None
    tasks: list[dict[str, Any]] | None
    logs: list[dict[str, Any]]
    log_guid: str
    log_version: int
    # Historical behavior: when no context is selected, log_progress is 0 (falsy).
    # When a context is active, it is usually a string.
    log_progress: str | int
    log_progress_active: bool
    paused: bool
    notifications: list[dict[str, Any]]
    notifications_guid: str
    notifications_version: int

@dataclass(frozen=True)
class StateRequestV1:
    context: str | None
    log_from: int
    notifications_from: int
    timezone: str
    collections_delta: bool = False


class StateRequestValidationError(ValueError):
    def __init__(
        self,
        *,
        reason: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.details = details or {}


def _annotation_to_isinstance_types(annotation: Any) -> tuple[type, ...]:
    """Convert type annotation to tuple suitable for isinstance()."""
    origin = get_origin(annotation)

    # Handle Union (typing.Union or types.UnionType from X | Y)
    _union_type = getattr(types, "UnionType", None)
    if origin is Union or origin is _union_type:
        result: list[type] = []
        for arg in get_args(annotation):
            result.extend(_annotation_to_isinstance_types(arg))
        return tuple(result)

    # Generic aliases: list[X] -> list, dict[K,V] -> dict
    if origin is not None:
        return (origin,)

    if isinstance(annotation, type):
        return (annotation,)

    return ()


def _build_schema_from_typeddict(td: type) -> dict[str, tuple[type, ...]]:
    """Extract field names and isinstance-compatible types from TypedDict."""
    return {k: _annotation_to_isinstance_types(v) for k, v in get_type_hints(td).items()}


_SNAPSHOT_V1_SCHEMA = _build_schema_from_typeddict(SnapshotV1)
SNAPSHOT_SCHEMA_V1_KEYS: tuple[str, ...] = tuple(_SNAPSHOT_V1_SCHEMA.keys())


def validate_snapshot_schema_v1(snapshot: Mapping[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise TypeError("snapshot must be a dict")
    expected = set(SNAPSHOT_SCHEMA_V1_KEYS)
    actual = set(snapshot.keys())
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        message = "snapshot schema mismatch"
        if missing:
            message += f"; missing={missing}"
        if extra:
            message += f"; unexpected={extra}"
        raise ValueError(message)

    for key, expected_types in _SNAPSHOT_V1_SCHEMA.items():
        if expected_types and not isinstance(snapshot.get(key), expected_types):
            type_desc = " | ".join(t.__name__ for t in expected_types)
            raise TypeError(f"snapshot.{key} must be {type_desc}")


def _coerce_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        as_int = int(value)
    except (TypeError, ValueError):
        return default
    return as_int if as_int >= 0 else default


def _get_agent_profile_labels() -> dict[str, str]:
    try:
        from helpers import subagents

        return {
            str(item.get("key") or ""): str(item.get("label") or item.get("key") or "")
            for item in subagents.get_all_agents_list()
            if item.get("key")
        }
    except Exception:
        return {}


def _apply_agent_profile_metadata(
    context_data: dict[str, Any],
    ctx: AgentContext,
    labels: dict[str, str],
) -> None:
    agent_config = getattr(getattr(ctx, "agent0", None), "config", None)
    profile = str(
        getattr(agent_config, "profile", None)
        or getattr(getattr(ctx, "config", None), "profile", "")
        or ""
    )
    context_data["agent_profile"] = profile
    context_data["agent_profile_label"] = labels.get(profile, profile) if profile else ""


def _prune_missing_saved_contexts() -> None:
    from helpers import persist_chat

    saved_ids = persist_chat.saved_chat_ids()
    for ctx in AgentContext.all():
        if ctx.type == AgentContextType.BACKGROUND or ctx.is_running():
            continue
        if (
            ctx.data.get(persist_chat.SAVED_CHAT_CONTEXT_DATA_KEY)
            and ctx.id not in saved_ids
            # Re-check disk: saved_ids may be stale vs. a concurrent first save.
            and not persist_chat.chat_file_exists(ctx.id)
        ):
            AgentContext.remove(ctx.id)


def parse_state_request_payload(payload: Mapping[str, Any]) -> StateRequestV1:
    context = payload.get("context")
    log_from = payload.get("log_from")
    notifications_from = payload.get("notifications_from")
    timezone = payload.get("timezone")
    collections_delta = payload.get("collections_delta", False)

    if context is not None and not isinstance(context, str):
        raise StateRequestValidationError(
            reason="context_type",
            message="context must be a string or null",
            details={"context_type": type(context).__name__},
        )
    if not isinstance(log_from, int) or log_from < 0:
        raise StateRequestValidationError(
            reason="log_from",
            message="log_from must be an integer >= 0",
            details={"log_from": log_from},
        )
    if not isinstance(notifications_from, int) or notifications_from < 0:
        raise StateRequestValidationError(
            reason="notifications_from",
            message="notifications_from must be an integer >= 0",
            details={"notifications_from": notifications_from},
        )
    if not isinstance(timezone, str) or not timezone.strip():
        raise StateRequestValidationError(
            reason="timezone_empty",
            message="timezone must be a non-empty string",
            details={"timezone": timezone},
        )
    if not isinstance(collections_delta, bool):
        raise StateRequestValidationError(
            reason="collections_delta_type",
            message="collections_delta must be a boolean",
            details={"collections_delta_type": type(collections_delta).__name__},
        )

    tz = timezone.strip()
    try:
        pytz.timezone(tz)
    except pytz.exceptions.UnknownTimeZoneError as exc:
        raise StateRequestValidationError(
            reason="timezone_invalid",
            message="timezone must be a valid IANA timezone name",
            details={"timezone": tz},
        ) from exc

    ctxid: str | None = context.strip() if isinstance(context, str) else None
    if ctxid == "":
        ctxid = None
    return StateRequestV1(
        context=ctxid,
        log_from=log_from,
        notifications_from=notifications_from,
        timezone=tz,
        collections_delta=collections_delta,
    )


def _coerce_state_request_inputs(
    *,
    context: Any,
    log_from: Any,
    notifications_from: Any,
    timezone: Any,
) -> StateRequestV1:
    tz = timezone if isinstance(timezone, str) and timezone else None
    tz = tz or get_dotenv_value("DEFAULT_USER_TIMEZONE", Localization.get().get_timezone())

    ctxid: str | None = context.strip() if isinstance(context, str) else None
    if ctxid == "":
        ctxid = None

    return StateRequestV1(
        context=ctxid,
        log_from=_coerce_non_negative_int(log_from, default=0),
        notifications_from=_coerce_non_negative_int(notifications_from, default=0),
        timezone=tz,
    )


def advance_state_request_after_snapshot(
    request: StateRequestV1,
    snapshot: Mapping[str, Any],
) -> StateRequestV1:
    log_from = request.log_from
    notifications_from = request.notifications_from

    try:
        log_from = int(snapshot.get("log_version", log_from))
    except (TypeError, ValueError):
        pass

    try:
        notifications_from = int(snapshot.get("notifications_version", notifications_from))
    except (TypeError, ValueError):
        pass

    return replace(
        request,
        log_from=log_from,
        notifications_from=notifications_from,
    )


async def build_snapshot_from_request(
    *, request: StateRequestV1, include_collections: bool = True
) -> SnapshotV1:
    """Build a poll-shaped snapshot for both /poll and state_push."""

    localization = Localization.get()
    previous_timezone = localization.get_timezone()
    localization.set_timezone(request.timezone)
    current_timezone = localization.get_timezone()
    if current_timezone != previous_timezone:
        _notify_timezone_changed(previous_timezone, current_timezone)

    ctxid = request.context if isinstance(request.context, str) else ""
    ctxid = ctxid.strip()

    from_no = _coerce_non_negative_int(request.log_from, default=0)
    notifications_from_no = _coerce_non_negative_int(request.notifications_from, default=0)

    if include_collections:
        _prune_missing_saved_contexts()

    active_context = AgentContext.get(ctxid) if ctxid else None

    if active_context:
        log_output = active_context.log.output(start=from_no)
        logs = log_output.items
        log_end = log_output.end
    else:
        logs = []
        log_end = 0

    notification_manager = AgentContext.get_notification_manager()
    notifications, notifications_guid, notifications_version = (
        notification_manager.output_with_state(start=notifications_from_no)
    )

    scheduler = TaskScheduler.get()

    ctxs: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    processed_contexts: set[str] = set()
    agent_profile_labels = _get_agent_profile_labels() if include_collections else {}

    all_ctxs = AgentContext.all() if include_collections else []
    for ctx in all_ctxs:
        if ctx.id in processed_contexts:
            continue

        if ctx.type == AgentContextType.BACKGROUND:
            processed_contexts.add(ctx.id)
            continue

        context_data = ctx.output()
        _apply_agent_profile_metadata(context_data, ctx, agent_profile_labels)

        context_task = scheduler.get_task_by_uuid(ctx.id)
        is_task_context = context_task is not None and context_task.context_id == ctx.id

        if not is_task_context:
            ctxs.append(context_data)
        else:
            task_details = scheduler.serialize_task(ctx.id)
            if task_details:
                context_data.update(
                    {
                        "task_name": task_details.get("name"),
                        "uuid": task_details.get("uuid"),
                        "state": task_details.get("state"),
                        "type": task_details.get("type"),
                        "system_prompt": task_details.get("system_prompt"),
                        "prompt": task_details.get("prompt"),
                        "last_run": task_details.get("last_run"),
                        "last_result": task_details.get("last_result"),
                        "attachments": task_details.get("attachments", []),
                        "context_id": task_details.get("context_id"),
                    }
                )

                if task_details.get("type") == "scheduled":
                    context_data["schedule"] = task_details.get("schedule")
                elif task_details.get("type") == "planned":
                    context_data["plan"] = task_details.get("plan")
                else:
                    context_data["token"] = task_details.get("token")

            tasks.append(context_data)

        processed_contexts.add(ctx.id)

    ctxs.sort(key=lambda x: x["created_at"], reverse=True)
    tasks.sort(key=lambda x: x["created_at"], reverse=True)

    snapshot: SnapshotV1 = {
        "deselect_chat": bool(ctxid) and active_context is None,
        "context": active_context.id if active_context else "",
        "contexts": ctxs if include_collections else None,
        "tasks": tasks if include_collections else None,
        "logs": logs,
        "log_guid": active_context.log.guid if active_context else "",
        "log_version": log_end,
        "log_progress": active_context.log.progress if active_context else 0,
        "log_progress_active": bool(active_context.log.progress_active) if active_context else False,
        "paused": active_context.paused if active_context else False,
        "notifications": notifications,
        "notifications_guid": notifications_guid,
        "notifications_version": notifications_version,
    }

    validate_snapshot_schema_v1(snapshot)
    return snapshot


def _notify_timezone_changed(previous_timezone: str, current_timezone: str) -> None:
    try:
        from helpers import plugins

        plugins.call_plugin_hook(
            "_office",
            "timezone_changed",
            None,
            previous_timezone=previous_timezone,
            timezone=current_timezone,
        )
    except Exception:
        return


async def build_snapshot(
    *,
    context: str | None,
    log_from: int,
    notifications_from: int,
    timezone: str | None,
) -> SnapshotV1:
    request = _coerce_state_request_inputs(
        context=context,
        log_from=log_from,
        notifications_from=notifications_from,
        timezone=timezone,
    )
    return await build_snapshot_from_request(request=request)
