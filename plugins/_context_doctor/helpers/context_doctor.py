"""Repair completed model output and refresh its log entry."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from json_repair import repair_json

from plugins._context_doctor.helpers.json_repair_patch import apply_patch


# One-time, idempotent parser patch on plugin import.
apply_patch()


_A0_SALVAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "thoughts": {"type": "array", "items": {"type": "string"}},
        "headline": {"type": "string"},
        "tool_name": {"type": "string"},
        "tool_args": {"type": "object"},
    },
    "required": [],
}


def _is_tool_call(value: Any) -> bool:
    """Check required tool-call fields and optional display fields."""
    return (
        isinstance(value, dict)
        and isinstance(value.get("tool_name"), str)
        and isinstance(value.get("tool_args"), dict)
        and (
            "thoughts" not in value
            or (
                isinstance(value["thoughts"], list)
                and all(isinstance(item, str) for item in value["thoughts"])
            )
        )
        and ("headline" not in value or isinstance(value["headline"], str))
    )


def _is_partial_response(value: Any) -> bool:
    """Check whether repair found thoughts or a headline without a tool call."""
    return isinstance(value, dict) and any(
        key in value for key in ("thoughts", "headline")
    )


def _objects(value: Any) -> Iterable[dict[str, Any]]:
    """Yield dictionary candidates from one repair result."""
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        yield from (item for item in value if isinstance(item, dict))


def _score_tool_call(value: dict[str, Any]) -> int:
    """Rank candidates by populated A0 tool-call fields."""
    return sum(
        key in value for key in ("thoughts", "headline", "tool_name", "tool_args")
    ) + bool(value.get("tool_args"))


def _repair(response: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Repair response and select its best tool or partial result."""
    try:
        salvage = repair_json(
            response,
            return_objects=True,
            schema=_A0_SALVAGE_SCHEMA,
            schema_repair_mode="salvage",
        )
    except Exception:
        salvage = None
    try:
        unstructured = repair_json(response, return_objects=True)
    except Exception:
        unstructured = None

    candidates = [*_objects(salvage), *_objects(unstructured)]
    tool_calls = [candidate for candidate in candidates if _is_tool_call(candidate)]
    if tool_calls:
        return max(tool_calls, key=_score_tool_call), None
    return None, next(
        (candidate for candidate in candidates if _is_partial_response(candidate)), None
    )


def _compact_json(value: dict[str, Any]) -> str:
    """Serialize JSON without ASCII escaping or whitespace."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _split_thoughts(value: dict[str, Any]) -> None:
    """Expand blank-line-separated thought strings into separate entries in place."""
    thoughts = value.get("thoughts")
    if not isinstance(thoughts, list):
        return
    split: list[str] = []
    for item in thoughts:
        if isinstance(item, str) and "\n\n" in item:
            split.extend(part for part in item.split("\n\n") if part)
        else:
            split.append(item)
    value["thoughts"] = split


def _select_value(response: str) -> dict[str, Any] | None:
    """Pick the repaired tool call or partial result."""
    if response:
        tool_call, partial_response = _repair(response)
        if tool_call is not None:
            return tool_call
        if partial_response is not None:
            return partial_response
    return None


def transform_response(
    response: str, *, suppress_xml: bool, split_thoughts: bool = True
) -> str:
    """Repair model output, falling back to compact thoughts JSON for raw text."""
    value = _select_value(response)
    if value is None:
        if suppress_xml and "<" in response and ">" in response:
            return "{}"
        value = {"thoughts": [response]}
    if split_thoughts:
        _split_thoughts(value)
    return _compact_json(value)


def looks_like_tool_call(response: str, transformed: str) -> bool:
    """Return True if transformed output is a JSON with usable A0 content."""
    if not response or _select_value(response) is None:
        return False
    try:
        parsed = json.loads(transformed)
    except ValueError:
        return False
    if not isinstance(parsed, dict) or not parsed:
        return False

    for key in ("thoughts", "headline", "tool_name", "tool_args"):
        if key not in parsed:
            continue
        value = parsed[key]
        if key == "thoughts":
            if (
                isinstance(value, list)
                and value
                and all(isinstance(item, str) and item.strip() for item in value)
            ):
                return True
        elif key in ("headline", "tool_name"):
            if isinstance(value, str) and value.strip():
                return True
        elif key == "tool_args":
            if isinstance(value, dict) and value:
                return True
    return False


def update_log_item(
    agent: Any,
    log_item: Any,
    response: str,
    *,
    update_log: bool,
    raw_response: str,
) -> None:
    """Update generated log fields while retaining streamed reasoning."""
    try:
        parsed = json.loads(response)
        if not isinstance(parsed, dict):
            return

        current_kvps = getattr(log_item, "kvps", None)
        kvps = {}
        if isinstance(current_kvps, dict):
            if "reasoning" in current_kvps:
                kvps["reasoning"] = current_kvps["reasoning"]
        kvps.update(parsed)

        heading = parsed.get("headline")
        if not isinstance(heading, str) or not heading:
            tool_name = parsed.get("tool_name")
            heading = f"Using {tool_name}" if isinstance(tool_name, str) else ""

        kwargs: dict[str, Any] = {
            "content": response if update_log else raw_response,
            "kvps": kvps,
        }
        if heading:
            kwargs["heading"] = f"{getattr(agent, 'agent_name', 'A0')}: {heading}"
        log_item.update(**kwargs)
    except (AttributeError, TypeError, ValueError):
        pass
