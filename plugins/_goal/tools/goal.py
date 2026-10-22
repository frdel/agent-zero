from __future__ import annotations

import json
import re
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from helpers import files
from helpers.tool import Response, Tool


PLUGIN_NAME = "_goal"
GOALS_DIR = "goals"
ACTIVE_STATUSES = {"active", "paused"}
FINAL_STATUSES = {"complete", "blocked"}
VALID_STATUSES = ACTIVE_STATUSES | FINAL_STATUSES


class GoalTool(Tool):
    async def execute(
        self,
        action: str = "",
        objective: str = "",
        status: str = "",
        note: str = "",
        token_budget: int | None = None,
        **kwargs,
    ) -> Response:
        action = str(action or self.args.get("action") or "get").strip().lower()
        context_id = self.agent.context.id

        try:
            if action in {"get", "show", "status"}:
                return Response(message=summarize_goal(get_goal(context_id)), break_loop=False)
            if action in {"create", "set"}:
                goal = create_goal(
                    context_id,
                    objective,
                    created_by="model",
                    token_budget=token_budget,
                )
                return Response(message=f"Goal created: {goal['objective']}", break_loop=False)
            if action in {"complete", "blocked"}:
                status = action
            if action in {"update", "complete", "blocked"}:
                status = str(status).strip().lower()
                if status not in FINAL_STATUSES:
                    return Response(
                        message="Model-managed goal updates may only mark goals complete or blocked.",
                        break_loop=False,
                    )
                goal = update_goal(
                    context_id,
                    status=status,
                    objective=objective or None,
                    note=note or None,
                )
                return Response(message=summarize_goal(goal), break_loop=False)
        except (FileNotFoundError, ValueError) as error:
            return Response(message=str(error), break_loop=False)

        return Response(
            message="Unknown goal action. Supported actions: get, create, update.",
            break_loop=False,
        )

    def get_log_object(self):
        return self.agent.context.log.log(
            type="goal",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self):
        action = str(self.args.get("action") or "get").strip().lower()
        action = {"show": "get", "status": "get", "set": "create"}.get(action, action)
        status = str(self.args.get("status") or "").strip().lower()
        if action in {"complete", "blocked"} or status in {"complete", "blocked"}:
            verb = "Completing goal" if (action == "complete" or status == "complete") else "Blocking goal"
        else:
            verb = {"get": "Checking goal", "create": "Setting goal"}.get(action, "Updating goal")
        return f"icon://flag {verb}"


def get_goal(context_id: str) -> dict[str, Any] | None:
    context_id = _require_context_id(context_id)
    path = _goal_path(context_id)
    if not Path(path).is_file():
        return None

    try:
        raw = json.loads(files.read_file(path))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None

    goal = _normalize_goal(raw, context_id=context_id)
    return goal if goal.get("objective") else None


def create_goal(
    context_id: str,
    objective: str,
    *,
    created_by: str = "user",
    token_budget: int | None = None,
) -> dict[str, Any]:
    context_id = _require_context_id(context_id)
    objective = _clean_objective(objective)
    if not objective:
        raise ValueError("Goal objective is required")

    now = _now()
    existing = get_goal(context_id)
    goal = {
        "context_id": context_id,
        "objective": objective,
        "status": "active",
        "created_by": _clean_created_by(created_by),
        "token_budget": _clean_token_budget(token_budget),
        "created_at": existing.get("created_at") if existing else now,
        "active_since": now,
        "elapsed_seconds": 0,
        "updated_at": now,
        "note": "",
    }
    _write_goal(goal)
    return goal


def update_goal(
    context_id: str,
    *,
    objective: str | None = None,
    status: str | None = None,
    note: str | None = None,
    token_budget: int | None = None,
) -> dict[str, Any]:
    context_id = _require_context_id(context_id)
    goal = get_goal(context_id)
    if not goal:
        raise FileNotFoundError("Goal not found")

    if objective is not None:
        goal["objective"] = _required_objective(objective)
    if status is not None:
        _apply_status(goal, _normalize_status(status))
    if note is not None:
        goal["note"] = str(note or "").strip()
    if token_budget is not None:
        goal["token_budget"] = _clean_token_budget(token_budget)

    goal["updated_at"] = _now()
    _write_goal(goal)
    return goal


def delete_goal(context_id: str) -> None:
    context_id = _require_context_id(context_id)
    files.delete_file(_goal_path(context_id))
    _notify_goal_changed(context_id)


def public_goal(goal: dict[str, Any] | None) -> dict[str, Any] | None:
    if not goal:
        return None
    return {
        "context_id": str(goal.get("context_id") or ""),
        "objective": str(goal.get("objective") or ""),
        "status": str(goal.get("status") or "active"),
        "created_by": str(goal.get("created_by") or "user"),
        "token_budget": goal.get("token_budget"),
        "created_at": str(goal.get("created_at") or ""),
        "active_since": str(goal.get("active_since") or ""),
        "elapsed_seconds": _clean_elapsed_seconds(goal.get("elapsed_seconds")),
        "updated_at": str(goal.get("updated_at") or ""),
        "note": str(goal.get("note") or ""),
    }


def summarize_goal(goal: dict[str, Any] | None) -> str:
    if not goal:
        return "No goal is set for this chat."

    lines = [
        f"Status: {goal.get('status') or 'active'}",
        f"Goal: {str(goal.get('objective') or '').strip()}",
        f"Active time: {_format_elapsed(_elapsed_seconds(goal))}",
    ]
    if updated := str(goal.get("updated_at") or "").strip():
        lines.append(f"Updated: {updated}")
    if note := str(goal.get("note") or "").strip():
        lines.append(f"Note: {note}")
    return "\n".join(lines)


def _write_goal(goal: dict[str, Any]) -> None:
    files.write_file(
        _goal_path(str(goal["context_id"])),
        json.dumps(public_goal(goal), indent=2, ensure_ascii=False) + "\n",
    )
    _notify_goal_changed(str(goal["context_id"]))


def _notify_goal_changed(context_id: str) -> None:
    from agent import AgentContext

    context = AgentContext.get(context_id)
    if context is None:
        return
    context.set_output_data("_goal_revision", time.time())

    try:
        from helpers.state_monitor_integration import mark_dirty_for_context

        mark_dirty_for_context(context_id, reason="plugins._goal")
    except Exception:
        pass


def _normalize_goal(raw: dict[str, Any], *, context_id: str) -> dict[str, Any]:
    status = str(raw.get("status") or "active").strip().lower()
    status = status if status in VALID_STATUSES else "active"
    created_at = str(raw.get("created_at") or "")
    updated_at = str(raw.get("updated_at") or "")
    active_since = str(raw.get("active_since") or "")
    elapsed_seconds = _clean_elapsed_seconds(raw.get("elapsed_seconds"))
    if "elapsed_seconds" not in raw and status != "active":
        elapsed_seconds = _seconds_between(created_at, updated_at)
    if status == "active" and not active_since:
        active_since = created_at or updated_at

    return {
        "context_id": context_id,
        "objective": _clean_objective(str(raw.get("objective") or "")),
        "status": status,
        "created_by": _clean_created_by(str(raw.get("created_by") or "user")),
        "token_budget": _clean_token_budget(raw.get("token_budget")),
        "created_at": created_at,
        "active_since": active_since,
        "elapsed_seconds": elapsed_seconds,
        "updated_at": updated_at,
        "note": str(raw.get("note") or "").strip(),
    }


def _goal_path(context_id: str) -> str:
    directory = files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, PLUGIN_NAME, GOALS_DIR)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", context_id).strip("._")[:180]
    if not safe:
        raise ValueError("A chat context is required")
    return files.get_abs_path(directory, f"{safe}.json")


def _require_context_id(context_id: str) -> str:
    context_id = str(context_id or "").strip()
    if not context_id:
        raise ValueError("A chat context is required")
    return context_id


def _required_objective(value: str) -> str:
    objective = _clean_objective(value)
    if not objective:
        raise ValueError("Goal objective is required")
    return objective


def _clean_objective(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_status(status: str) -> str:
    status = str(status or "").strip().lower()
    if status not in VALID_STATUSES:
        raise ValueError("Goal status must be active, paused, complete, or blocked")
    return status


def _clean_created_by(created_by: str) -> str:
    created_by = str(created_by or "").strip().lower()
    return created_by if created_by in {"user", "model"} else "user"


def _clean_token_budget(token_budget: Any) -> int | None:
    try:
        token_budget = int(token_budget)
    except (TypeError, ValueError):
        return None
    return token_budget if token_budget > 0 else None


def _apply_status(goal: dict[str, Any], status: str) -> None:
    current = str(goal.get("status") or "active")
    if current == "active" and status != "active":
        goal["elapsed_seconds"] = _elapsed_seconds(goal)
        goal["active_since"] = ""
    elif current != "active" and status == "active":
        goal["active_since"] = _now()
    goal["status"] = status


def _elapsed_seconds(goal: dict[str, Any]) -> int:
    elapsed = _clean_elapsed_seconds(goal.get("elapsed_seconds"))
    if str(goal.get("status") or "active") == "active":
        elapsed += _seconds_between(str(goal.get("active_since") or ""), _now())
    return elapsed


def _clean_elapsed_seconds(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _seconds_between(start: str, end: str) -> int:
    start_dt, end_dt = _parse_time(start), _parse_time(end)
    return max(0, int((end_dt - start_dt).total_seconds())) if start_dt and end_dt else 0


def _parse_time(value: str) -> datetime | None:
    value = str(value or "").strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _format_elapsed(seconds: int) -> str:
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m {seconds}s" if minutes else f"{seconds}s"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
