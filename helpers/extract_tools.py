
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


def extract_tool_request_final(content: str) -> dict[str, Any] | None:
    """Extract a tool request from a final, completed message.

    Lenient sibling of :func:`extract_tool_request` for non-streaming use:
    accepts trailing non-JSON text after a complete tool request. Preamble
    text before the request, concatenated additional JSON roots, and
    trailing text containing braces or brackets are still rejected so those
    cases keep routing to the repair path instead of executing partially.
    """
    if not content or not isinstance(content, str):
        return None

    content = content.strip()
    if not content.startswith("{"):
        return None

    root = extract_json_root_string(content)
    if root is None or not content.startswith(root):
        return None

    remainder = content[len(root):]
    if "{" in remainder or "[" in remainder or '"' in remainder:
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
