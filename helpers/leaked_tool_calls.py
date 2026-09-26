"""Conservative recovery of complete, standalone text tool-call envelopes."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from helpers.extract_tools import extract_tool_request, normalize_tool_request

_XML_MARKER = re.compile(
    r"</?(?:tool_call\b|function(?:=|\b)|parameter(?:=|\b)|function_calls\b|"
    r"invoke\b|minimax:tool_call\b)|<\|tool_calls_section_begin\|>"
)
_NAME = r"[A-Za-z0-9_.:-]+"
_FUNCTION = re.compile(rf"<function=({_NAME})>")
_PARAMETER = re.compile(rf"<parameter=({_NAME})>")
_CANONICAL_MARKER = re.compile(r"""(?:["'`]?\btool_(?:name|args)["'`]?)\s*:""")
_CODE = re.compile(
    r"(?m)^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}\1[ \t]*(?:\n|$)|\Z)"
    r"|(`+)[^`]*?\2",
    re.DOTALL,
)


@dataclass(frozen=True)
class SalvageResult:
    request: dict[str, Any] | None = None
    status: Literal["clean", "salvaged", "leaked_unsalvageable", "truncated"] = "clean"
    # Stable, content-free reason codes: never include model arguments in diagnostics.
    detail: str = ""


class _InvalidCall(ValueError):
    pass


class _TruncatedCall(_InvalidCall):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidCall("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise _InvalidCall("nonfinite_json_value")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise _InvalidCall("nonfinite_json_value")
    return number


_DECODER = json.JSONDecoder(
    object_pairs_hook=_unique_object,
    parse_constant=_reject_constant,
    parse_float=_finite_float,
)


def _has_marker(text: str) -> bool:
    return bool(
        _XML_MARKER.search(text)
        or _CANONICAL_MARKER.search(text)
        or (
            re.search(r'"name"\s*:', text)
            and re.search(r'"(?:arguments|parameters)"\s*:', text)
        )
    )


def _unclosed_json(text: str) -> bool:
    """Distinguish missing closing delimiters from complete invalid JSON."""
    stack: list[str] = []
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if not stack or stack.pop() != {"}": "{", "]": "["}[char]:
                return False
    return bool(stack or quoted)


def _json_at_start(text: str) -> tuple[Any, int]:
    try:
        return _DECODER.raw_decode(text)
    except json.JSONDecodeError as error:
        if _unclosed_json(text):
            raise _TruncatedCall("incomplete_json") from error
        raise _InvalidCall("invalid_json") from error


def _coerce_parameter(value: str) -> Any:
    # Preserve file bodies, padding, and prose exactly. Never repair a value.
    if value and not any(char.isspace() for char in value):
        try:
            parsed, end = _DECODER.raw_decode(value)
            if end == len(value):
                return parsed
        except (ValueError, RecursionError):
            pass
    return value


def _function_at_start(text: str) -> tuple[dict[str, Any], int]:
    opening = _FUNCTION.match(text)
    if opening is None:
        if ">" not in text:
            raise _TruncatedCall("incomplete_function_header")
        raise _InvalidCall("invalid_function_header")
    end = text.find("</function>", opening.end())
    if end < 0:
        raise _TruncatedCall("incomplete_function")
    body = text[opening.end() : end]
    args: dict[str, Any] = {}
    position = 0
    while position < len(body):
        while position < len(body) and body[position].isspace():
            position += 1
        if position == len(body):
            break
        parameter = _PARAMETER.match(body, position)
        if parameter is None:
            raise _InvalidCall("invalid_parameter_markup")
        close = body.find("</parameter>", parameter.end())
        if close < 0:
            raise _InvalidCall("unclosed_parameter")
        key = parameter.group(1)
        value = body[parameter.end() : close]
        if key in args or _XML_MARKER.search(value):
            raise _InvalidCall("ambiguous_parameter")
        args[key] = _coerce_parameter(value)
        position = close + len("</parameter>")
    return {"tool_name": opening.group(1), "tool_args": args}, end + len("</function>")


def _payload_at_start(text: str) -> tuple[Any, int]:
    if text.startswith("<function="):
        return _function_at_start(text)
    if text.startswith(("{", "[")):
        return _json_at_start(text)
    raise _InvalidCall("unsupported_tool_syntax")


def _candidate(text: str) -> Any:
    if text.startswith("<tool_call>"):
        inner = text[len("<tool_call>") :].lstrip()
        if not inner:
            raise _TruncatedCall("incomplete_tool_call")
        value, end = _payload_at_start(inner)
        tail = inner[end:].lstrip()
        if not tail.startswith("</tool_call>"):
            if "</tool_call>".startswith(tail):
                raise _TruncatedCall("incomplete_tool_call")
            raise _InvalidCall("invalid_tool_call_wrapper")
        tail = tail[len("</tool_call>") :]
    else:
        value, end = _payload_at_start(text)
        tail = text[end:]
    if tail.strip():
        raise _InvalidCall("multiple_calls_or_surrounding_text")
    if isinstance(value, list):
        if len(value) != 1:
            raise _InvalidCall("multiple_or_empty_calls")
        value = value[0]
    return value


def _normalize_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _InvalidCall("invalid_call_object")
    if "tool_name" in value:
        if value.keys() - {"tool_name", "tool_args", "thoughts", "headline"}:
            raise _InvalidCall("ambiguous_call_fields")
        if not isinstance(value.get("tool_args"), dict):
            raise _InvalidCall("arguments_must_be_object")
        return {"tool_name": value["tool_name"], "tool_args": value["tool_args"]}
    if value.keys() - {
        "name",
        "arguments",
        "parameters",
        "type",
        "id",
        "thoughts",
        "headline",
    }:
        raise _InvalidCall("ambiguous_call_fields")
    if "arguments" in value and "parameters" in value:
        raise _InvalidCall("ambiguous_arguments")
    args = value.get("arguments", value.get("parameters"))
    if isinstance(args, str):
        encoded_args = args.strip()
        args, end = _json_at_start(encoded_args)
        if end != len(encoded_args):
            raise _InvalidCall("invalid_arguments_json")
    if not isinstance(args, dict):
        raise _InvalidCall("arguments_must_be_object")
    if value.get("type", "function") != "function":
        raise _InvalidCall("unsupported_call_type")
    return {"tool_name": value.get("name"), "tool_args": args}


def salvage_leaked_tool_call(
    response: str,
    offered_tools: Iterable[str] | None = None,
    *,
    tool_name_map: Mapping[str, str] | None = None,
) -> SalvageResult:
    """Recover one standalone call; missing tool availability fails closed.

    Canonical A0 requests retain their existing parser and dispatch behavior.
    Quoted examples are clean, with a marker preventing downstream JSON repair
    from promoting them to executable calls. Prose around a call is ambiguous.
    """
    if not isinstance(response, str) or not response.strip():
        return SalvageResult()
    text = response.strip()
    if extract_tool_request(text) is not None:
        return SalvageResult()
    if text == "<tool_call":
        return SalvageResult(status="truncated", detail="incomplete_tool_call_header")

    # Do not remove code inside a JSON string or XML parameter value. Parse the
    # complete outer envelope first; only mask code when detecting other text.
    standalone = text.startswith(("<tool_call>", "<function=", "{", "["))
    visible = text if standalone else _CODE.sub("", text)
    if not _has_marker(visible):
        return SalvageResult(detail="quoted_tool_syntax" if _has_marker(text) else "")
    if not standalone:
        return SalvageResult(
            status="leaked_unsalvageable",
            detail="surrounding_text_or_unsupported_syntax",
        )

    try:
        candidate = _candidate(text)
        if (
            text.startswith("{")
            and isinstance(candidate, dict)
            and not (
                {"tool_name", "tool_args", "actions"} & candidate.keys()
                or (
                    "name" in candidate
                    and {"arguments", "parameters"} & candidate.keys()
                )
            )
        ):
            return SalvageResult()
        request = _normalize_candidate(candidate)
        name = request["tool_name"]
        if not isinstance(name, str) or not name or name != name.strip():
            raise _InvalidCall("invalid_tool_name")
        request["tool_name"] = (tool_name_map or {}).get(name, name)
        name, args = normalize_tool_request(request)
        name = (tool_name_map or {}).get(name, name)
        if offered_tools is None:
            raise _InvalidCall("tool_surface_unavailable")
        if name not in set(offered_tools):
            raise _InvalidCall("tool_not_offered")
        return SalvageResult(
            {"tool_name": name, "tool_args": args}, "salvaged", "complete_single_call"
        )
    except _TruncatedCall as error:
        return SalvageResult(status="truncated", detail=str(error))
    except _InvalidCall as error:
        return SalvageResult(status="leaked_unsalvageable", detail=str(error))
    except (ValueError, RecursionError):
        # Keep exception text from parsers and normalizers out of diagnostics.
        return SalvageResult(
            status="leaked_unsalvageable", detail="invalid_or_unavailable_call"
        )
