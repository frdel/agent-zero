import json
import math

from .dirty_json import DirtyJson
import regex, re
from helpers.modules import load_classes_from_file, load_classes_from_folder # keep here for backwards compatibility
from typing import Any

def json_parse_dirty(json: str) -> dict[str, Any] | None:
    if not json or not isinstance(json, str):
        return None

    first_data: dict[str, Any] | None = None
    for ext_json in extract_json_root_strings(json.strip()):
        data = _parse_json_root_object(ext_json)
        if data is None:
            continue
        if first_data is None:
            first_data = data
        if _is_tool_request(data):
            return data
    return first_data


def extract_tool_request(content: str) -> dict[str, Any] | None:
    if not content or not isinstance(content, str):
        return None

    content = content.strip()
    if not (content.startswith("{") and content.endswith("}")):
        return None

    root = extract_json_root_string(content)
    if root != content:
        return None

    request = _parse_json_root_object(root)
    return request if request is not None and _is_tool_request(request) else None


def is_misformatted_tool_request(content: str) -> bool:
    if not content or not isinstance(content, str):
        return False

    content = content.strip()
    roots = extract_json_root_strings(content)
    if (
        len(roots) > 1
        and content.startswith("{")
        and content.endswith("}")
        and any(extract_tool_request(root) is not None for root in roots)
    ):
        return True

    for fenced_content in re.findall(
        r"```(?:json)?\s*(.*?)```", content, flags=re.IGNORECASE | re.DOTALL
    ):
        request = json_parse_dirty(fenced_content)
        if isinstance(request, dict) and _is_tool_request(request):
            return True

    if (
        not content.endswith("}")
        or re.match(r'^\{\s*"thoughts"\s*:', content) is None
    ):
        return False

    request = json_parse_dirty(content)
    thoughts = request.get("thoughts") if isinstance(request, dict) else None
    thoughts_text = (
        "\n".join(thought for thought in thoughts if isinstance(thought, str))
        if isinstance(thoughts, list)
        else ""
    )
    return (
        isinstance(thoughts, list)
        and all(
            f'{field}\":' in thoughts_text
            for field in ("headline", "tool_name", "tool_args")
        )
    )


def normalize_tool_request(tool_request: Any) -> tuple[str, dict]:
    if not isinstance(tool_request, dict):
        raise ValueError("Tool request must be a dictionary")
    if (
        not tool_request.get("tool_name")
        and not tool_request.get("tool")
        and "actions" in tool_request
    ):
        actions = tool_request["actions"]
        # Text tool calls allow one request per turn; do not silently discard extras.
        if (
            not isinstance(actions, list)
            or len(actions) != 1
            or not isinstance(actions[0], dict)
        ):
            raise ValueError(
                "Tool request actions wrapper must contain exactly one dictionary"
            )
        tool_request = actions[0]

    tool_name = tool_request.get("tool_name")
    if not tool_name or not isinstance(tool_name, str):
        tool_name = tool_request.get("tool")
    if (
        (not tool_name or not isinstance(tool_name, str))
        and tool_request.get("type") == "function"
    ):
        tool_name = tool_request.get("name")
    if not tool_name or not isinstance(tool_name, str):
        raise ValueError("Tool request must have a tool_name (type string) field")
    tool_args = tool_request.get("tool_args")
    if not isinstance(tool_args, dict):
        tool_args = tool_request.get("args")
    if not isinstance(tool_args, dict) and tool_request.get("type") == "function":
        tool_args = tool_request.get("parameters")
    if not isinstance(tool_args, dict):
        raise ValueError("Tool request must have a tool_args (type dictionary) field")
    tool_args = dict(tool_args)
    if ":" in tool_name:
        tool_name, action = tool_name.split(":", 1)
        if not tool_name or not action:
            raise ValueError("tool_name method suffix must include tool and action")
        tool_args.setdefault("action", action)
    method = tool_args.get("method")
    if "action" not in tool_args and isinstance(method, str) and method:
        tool_args["action"] = method
    return tool_name, tool_args


def extract_json_root_string(content: str) -> str | None:
    first_root: str | None = None
    for root in extract_json_root_strings(content):
        if first_root is None:
            first_root = root
        data = _parse_json_root_object(root)
        if data is not None and _is_tool_request(data):
            return root
    return first_root


def extract_json_root_strings(content: str) -> list[str]:
    if not content or not isinstance(content, str):
        return []

    if content.lstrip().startswith("["):
        return []

    roots: list[str] = []
    for start in _json_root_object_starts(content):
        parser = DirtyJson()
        try:
            parser.parse(content[start:])
        except Exception:
            continue

        if not parser.completed:
            continue

        roots.append(content[start : start + parser.index])
    return roots


def _json_root_object_starts(content: str) -> list[int]:
    starts: list[int] = []
    depth = 0
    quote: str | None = None
    escaped = False

    for index, char in enumerate(content):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if depth and char in ['"', "'", "`"]:
            quote = char
        elif char == "{":
            if depth == 0:
                starts.append(index)
            depth += 1
        elif depth and char == "[":
            depth += 1
        elif depth and char in ["}", "]"]:
            depth -= 1

    return starts


def _parse_json_root_object(root: str) -> dict[str, Any] | None:
    try:
        data = DirtyJson.parse_string(root)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _is_tool_request(data: dict[str, Any]) -> bool:
    try:
        normalize_tool_request(data)
    except ValueError:
        return False
    return True


def extract_json_object_string(content):
    start = content.find("{")
    if start == -1:
        return ""

    # Find the first '{'
    end = content.rfind("}")
    if end == -1:
        # If there's no closing '}', return from start to the end
        return content[start:]
    else:
        # If there's a closing '}', return the substring from start to end
        return content[start : end + 1]


def extract_json_string(content):
    # Regular expression pattern to match a JSON object
    pattern = r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]|"(?:\\.|[^"\\])*"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'

    # Search for the pattern in the content
    match = regex.search(pattern, content)

    if match:
        # Return the matched JSON string
        return match.group(0)
    else:
        return ""


def fix_json_string(json_string):
    # Function to replace unescaped line breaks within JSON string values
    def replace_unescaped_newlines(match):
        return match.group(0).replace("\n", "\\n")

    # Use regex to find string values and apply the replacement function
    fixed_string = re.sub(
        r'(?<=: ")(.*?)(?=")', replace_unescaped_newlines, json_string, flags=re.DOTALL
    )
    return fixed_string


_TOOL_XML_MARKER = re.compile(
    r"</?(?:tool_call\b|function(?:=|\b)|parameter(?:=|\b)|function_calls\b|"
    r"invoke\b|minimax:tool_call\b)|<\|tool_calls_section_begin\|>"
)
_TOOL_NAME = r"[A-Za-z0-9_.:-]+"
_TOOL_FUNCTION = re.compile(rf"<function=({_TOOL_NAME})>")
_TOOL_PARAMETER = re.compile(rf"<parameter=({_TOOL_NAME})>")
_TOOL_CANONICAL_MARKER = re.compile(r"""(?:["'`]?\btool_(?:name|args)["'`]?)\s*:""")
_TOOL_CODE = re.compile(
    r"(?m)^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}\1[ \t]*(?:\n|$)|\Z)"
    r"|(`+)[^`]*?\2",
    re.DOTALL,
)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise ValueError("nonfinite_json_value")


def _finite_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite_json_value")
    return number


_TOOL_JSON_DECODER = json.JSONDecoder(
    object_pairs_hook=_unique_json_object,
    parse_constant=_reject_json_constant,
    parse_float=_finite_json_float,
)


def _has_tool_marker(text: str) -> bool:
    return bool(
        _TOOL_XML_MARKER.search(text)
        or _TOOL_CANONICAL_MARKER.search(text)
        or (
            re.search(r'"name"\s*:', text)
            and re.search(r'"(?:arguments|parameters)"\s*:', text)
        )
    )


def _has_unclosed_json(text: str) -> bool:
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


def _strict_json_at_start(text: str) -> tuple[Any, int]:
    try:
        return _TOOL_JSON_DECODER.raw_decode(text)
    except json.JSONDecodeError as error:
        if _has_unclosed_json(text):
            raise EOFError("incomplete_json") from error
        raise ValueError("invalid_json") from error


def _coerce_tool_parameter(value: str) -> Any:
    # Preserve file bodies, padding, and prose exactly. Never repair a value.
    if value and not any(char.isspace() for char in value):
        try:
            parsed, end = _TOOL_JSON_DECODER.raw_decode(value)
            if end == len(value):
                return parsed
        except (ValueError, RecursionError):
            pass
    return value


def _leaked_function_at_start(text: str) -> tuple[dict[str, Any], int]:
    opening = _TOOL_FUNCTION.match(text)
    if opening is None:
        if ">" not in text:
            raise EOFError("incomplete_function_header")
        raise ValueError("invalid_function_header")
    end = text.find("</function>", opening.end())
    if end < 0:
        raise EOFError("incomplete_function")
    body = text[opening.end() : end]
    args: dict[str, Any] = {}
    position = 0
    while position < len(body):
        while position < len(body) and body[position].isspace():
            position += 1
        if position == len(body):
            break
        parameter = _TOOL_PARAMETER.match(body, position)
        if parameter is None:
            raise ValueError("invalid_parameter_markup")
        close = body.find("</parameter>", parameter.end())
        if close < 0:
            raise ValueError("unclosed_parameter")
        key = parameter.group(1)
        value = body[parameter.end() : close]
        if key in args or _TOOL_XML_MARKER.search(value):
            raise ValueError("ambiguous_parameter")
        args[key] = _coerce_tool_parameter(value)
        position = close + len("</parameter>")
    return {"tool_name": opening.group(1), "tool_args": args}, end + len("</function>")


def _leaked_payload_at_start(text: str) -> tuple[Any, int]:
    if text.startswith("<function="):
        return _leaked_function_at_start(text)
    if text.startswith(("{", "[")):
        return _strict_json_at_start(text)
    raise ValueError("unsupported_tool_syntax")


def _leaked_call_candidate(text: str) -> Any:
    if text.startswith("<tool_call>"):
        inner = text[len("<tool_call>") :].lstrip()
        if not inner:
            raise EOFError("incomplete_tool_call")
        value, end = _leaked_payload_at_start(inner)
        tail = inner[end:].lstrip()
        if not tail.startswith("</tool_call>"):
            if "</tool_call>".startswith(tail):
                raise EOFError("incomplete_tool_call")
            raise ValueError("invalid_tool_call_wrapper")
        tail = tail[len("</tool_call>") :]
    else:
        value, end = _leaked_payload_at_start(text)
        tail = text[end:]
    if tail.strip():
        raise ValueError("multiple_calls_or_surrounding_text")
    if isinstance(value, list):
        if len(value) != 1:
            raise ValueError("multiple_or_empty_calls")
        value = value[0]
    return value


def _normalize_leaked_call(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid_call_object")
    if "tool_name" in value:
        if value.keys() - {"tool_name", "tool_args", "thoughts", "headline"}:
            raise ValueError("ambiguous_call_fields")
        if not isinstance(value.get("tool_args"), dict):
            raise ValueError("arguments_must_be_object")
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
        raise ValueError("ambiguous_call_fields")
    if "arguments" in value and "parameters" in value:
        raise ValueError("ambiguous_arguments")
    args = value.get("arguments", value.get("parameters"))
    if isinstance(args, str):
        encoded_args = args.strip()
        args, end = _strict_json_at_start(encoded_args)
        if end != len(encoded_args):
            raise ValueError("invalid_arguments_json")
    if not isinstance(args, dict):
        raise ValueError("arguments_must_be_object")
    if value.get("type", "function") != "function":
        raise ValueError("unsupported_call_type")
    return {"tool_name": value.get("name"), "tool_args": args}


def extract_leaked_tool_request(response: str) -> tuple[str, dict[str, Any] | None]:
    """Classify completed text; the result hook authorizes any recovered request.

    Return clean, quoted, call, truncated or rejected. The streaming/canonical
    parser retains its existing behavior; recovery never repairs argument values.
    """
    if not isinstance(response, str) or not response.strip():
        return "clean", None
    text = response.strip()
    if extract_tool_request(text) is not None:
        return "clean", None
    if text == "<tool_call":
        return "truncated", None

    # Parse the outer envelope before masking code inside argument strings.
    standalone = text.startswith(("<tool_call>", "<function=", "{", "["))
    visible = text if standalone else _TOOL_CODE.sub("", text)
    if not _has_tool_marker(visible):
        return ("quoted" if _has_tool_marker(text) else "clean"), None
    if not standalone:
        return "rejected", None

    try:
        candidate = _leaked_call_candidate(text)
        if (
            text.startswith("{")
            and isinstance(candidate, dict)
            and not (
                {"tool_name", "tool_args", "actions"} & candidate.keys()
                or ("name" in candidate and {"arguments", "parameters"} & candidate.keys())
            )
        ):
            return "clean", None
        request = _normalize_leaked_call(candidate)
        name = request["tool_name"]
        if not isinstance(name, str) or not name or name != name.strip():
            return "rejected", None
        return "call", request
    except EOFError:
        return "truncated", None
    except (ValueError, RecursionError):
        return "rejected", None
