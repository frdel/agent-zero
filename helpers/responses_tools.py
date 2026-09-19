from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from typing import Any

from helpers import extract_tools, files, subagents, tool_policy


FUNCTION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TOOL_NAME_EXAMPLE_PATTERN = re.compile(
    r"""["']tool_name["']\s*:\s*["']([A-Za-z0-9_-]{1,64})["']"""
)
TOOL_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)
TOOL_DECLARATION_PATTERN = re.compile(
    r"^\s*-\s+`([A-Za-z0-9_-]{1,64})`:\s+(args?\b.*)$",
    re.IGNORECASE | re.MULTILINE,
)
SIMPLE_ARGS_PATTERN = re.compile(
    r"^\s*args?:\s*`([A-Za-z_][A-Za-z0-9_-]*)`\s*$",
    re.IGNORECASE | re.MULTILINE,
)
TOOL_PROMPT_PREFIX = "agent.system.tool."
TOOL_PROMPT_SUFFIX = ".md"
TOOL_PROMPT_KWARGS_KEY = "_tool_prompt_kwargs"
FENCED_EXAMPLE_PATTERN = re.compile(
    r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<language>[^\r\n]*)\r?\n"
    r"(?P<body>.*?)^[ \t]*(?P=fence)[ \t]*(?:\r?\n|$)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

# Canonical arguments for the resolved bundled implementations, not tool-name aliases.
BUNDLED_TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "tools/response.py": {
        "text": {"type": "string", "minLength": 1},
    },
    "plugins/_search_engine/tools/search_engine.py": {"query": {"type": "string"}},
    "tools/vision_load.py": {
        "paths": {"type": "array", "items": {"type": "string"}},
        "query": {"type": "string"},
    },
    "plugins/_wait/tools/wait.py": {
        "seconds": {"type": "number"},
        "minutes": {"type": "number"},
        "hours": {"type": "number"},
        "days": {"type": "number"},
        "until": {"type": "string"},
    },
    "plugins/_notify_user/tools/notify_user.py": {
        "message": {"type": "string"},
        "title": {"type": "string"},
        "detail": {"type": "string"},
        "type": {"type": "string", "enum": ["info", "success", "warning", "error", "progress"]},
        "priority": {"type": "integer", "enum": [10, 20]},
        "timeout": {"type": "integer"},
    },
    "tools/call_subordinate.py": {
        "message": {"type": "string"},
        "profile": {"type": "string"},
        "name": {"type": "string"},
        "reset": {"type": "boolean"},
        "context_id": {"type": "string"},
        "attachments": {"type": "array", "items": {"type": "string"}},
    },
    "tools/skills_tool.py": {
        "action": {"type": "string", "enum": ["list", "search", "load", "read_file"]},
        "query": {"type": "string"},
        "skill_name": {"type": "string"},
        "file_path": {"type": "string"},
    },
    "plugins/_code_execution/tools/code_execution_tool.py": {
        "runtime": {"type": "string", "enum": ["terminal", "python", "nodejs", "output", "reset"]},
        "code": {"type": "string"},
        "session": {"type": "integer"},
        "reset": {"type": "boolean"},
        "allow_running": {"type": "boolean"},
    },
    "plugins/_code_execution/tools/input.py": {
        "keyboard": {"type": "string"},
        "session": {"type": "integer"},
    },
    "plugins/_a0_connector/tools/code_execution_remote.py": {
        "runtime": {"type": "string", "enum": ["terminal", "python", "nodejs", "output", "reset"]},
        "code": {"type": "string"},
        "session": {"type": "integer"},
        "reset": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "plugins/_a0_connector/tools/input_remote.py": {
        "keyboard": {"type": "string"},
        "session": {"type": "integer"},
    },
    "plugins/_memory/tools/memory_load.py": {
        "query": {"type": "string"},
        "threshold": {"type": "number"},
        "limit": {"type": "integer"},
        "filter": {"type": "string"},
    },
    "plugins/_memory/tools/memory_save.py": {
        "text": {"type": "string"},
        "area": {"type": "string"},
    },
    "plugins/_memory/tools/memory_delete.py": {"ids": {"type": "string"}},
    "plugins/_memory/tools/memory_forget.py": {
        "query": {"type": "string"},
        "threshold": {"type": "number"},
        "filter": {"type": "string"},
    },
    "plugins/_memory/tools/behaviour_adjustment.py": {"adjustments": {"type": "string"}},
    "plugins/_goal/tools/goal.py": {
        "action": {"type": "string", "enum": ["get", "create", "update"]},
        "objective": {"type": "string"},
        "status": {"type": "string", "enum": ["complete", "blocked"]},
        "note": {"type": "string"},
        "token_budget": {"type": "integer", "minimum": 1},
    },
}


def register_prompt(agent: Any, loop_data: Any, section: str, prompt: str) -> None:
    """Record request-only alternatives without changing the rendered text prompt."""
    replacements = loop_data.params_temporary.setdefault("responses_prompt_replacements", {})
    if section == "main":
        communication = agent.read_prompt("agent.system.main.communication.md")
        if communication in prompt:
            replacements[communication] = agent.read_prompt("agent.system.main.communication.native.md")
    elif section == "tools":
        replacements[prompt] = ""
    elif section == "mcp" and prompt:
        from helpers.mcp_handler import MCPConfig

        servers = MCPConfig.get_for_agent(agent).get_tools_prompt(agent=agent, include_tools=False)
        replacements[prompt] = agent.read_prompt("agent.system.mcp_tools.native.md", tools=servers) if servers else ""


def build_responses_function_tools(agent: Any) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Build Responses function tools from available implementations and prompt/MCP schemas."""

    tools: list[dict[str, Any]] = []
    name_map: dict[str, str] = {}
    policy = tool_policy.get_policy(agent)

    local_prompts = _local_tool_prompts(agent)
    descriptions = tool_policy.filter_tool_prompts(
        agent,
        [(f"{TOOL_PROMPT_PREFIX}{name}{TOOL_PROMPT_SUFFIX}", prompt) for name, prompt in local_prompts],
        _policy=policy,
    )
    for (tool_name, prompt), description in zip(local_prompts, descriptions):
        if not tool_policy.resolve_tool(agent, tool_name, _policy=policy).allowed:
            continue
        native_name = _native_tool_name(tool_name)
        name_map[native_name] = tool_name
        tools.append(
            {
                "type": "function",
                "name": native_name,
                "strict": False,
                "description": _native_tool_description(description, tool_name),
                "parameters": _schema_for_tool(agent, tool_name, prompt),
            }
        )

    for tool_name, tool in _mcp_tools(agent):
        if not tool_policy.resolve_tool(
            agent,
            tool_name,
            canonical_id=tool_policy.canonical_mcp_id(tool_name),
            _policy=policy,
        ).allowed:
            continue
        native_name = _native_tool_name(tool_name)
        name_map[native_name] = tool_name
        tools.append(
            {
                "type": "function",
                "name": native_name,
                "strict": False,
                "description": str(tool.get("description") or tool_name),
                "parameters": _schema_from_any(tool.get("input_schema")),
            }
        )

    return _dedupe_tools(tools), name_map


def original_tool_name(native_name: str, name_map: dict[str, str] | None) -> str:
    if not name_map:
        return native_name
    return name_map.get(native_name, native_name)


def project_system_prompt(
    items: list[dict[str, Any]], replacements: dict[str, str] | None,
) -> list[dict[str, Any]]:
    if not replacements:
        return items
    pairs = []
    for source, target in replacements.items():
        source = files.remove_code_fences(source, language="json")
        if source.strip():
            pairs.append((source, files.remove_code_fences(target, language="json")))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)

    def replace(text: str) -> str:
        for source, target in pairs:
            text = text.replace(source, target)
        return text

    projected = deepcopy(items)
    for item in projected:
        if item.get("role") not in {"system", "developer"}:
            continue
        content = item.get("content")
        if isinstance(content, str):
            item["content"] = replace(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    block["text"] = replace(block["text"])
    return projected


def _local_tool_prompts(agent: Any) -> list[tuple[str, str]]:
    prompt_dirs = subagents.get_paths(agent, "prompts")
    tool_files = files.get_unique_filenames_in_dirs(
        prompt_dirs, f"{TOOL_PROMPT_PREFIX}*{TOOL_PROMPT_SUFFIX}"
    )
    get_data = getattr(agent, "get_data", None)
    tool_kwargs = get_data(TOOL_PROMPT_KWARGS_KEY) if callable(get_data) else {}
    tool_kwargs = tool_kwargs if isinstance(tool_kwargs, dict) else {}
    result: list[tuple[str, str]] = []
    for tool_file in tool_files:
        basename = os.path.basename(tool_file)
        fallback_name = _tool_name_from_prompt_basename(basename)
        if not fallback_name:
            continue
        try:
            prompt = agent.read_prompt(basename, **tool_kwargs.get(basename, {}))
        except Exception:
            try:
                prompt = files.read_file(tool_file)
            except Exception:
                prompt = ""
        for tool_name in _tool_names_from_prompt(prompt, fallback=fallback_name):
            if _include_local_tool_prompt(agent, tool_name):
                result.append((tool_name, prompt))

    vision_prompt = _vision_tool_prompt(agent)
    if vision_prompt:
        result.append(("vision_load", vision_prompt))
    return result


def _vision_tool_prompt(agent: Any) -> str:
    try:
        from plugins._model_config.helpers.model_config import (
            get_chat_model_config,
            get_vision_model_config,
        )

        if not (
            get_vision_model_config(agent)
            or get_chat_model_config(agent).get("vision", False)
        ):
            return ""
        return agent.read_prompt("agent.system.tools_vision.md")
    except Exception:
        return ""


def _include_local_tool_prompt(agent: Any, tool_name: str) -> bool:
    try:
        from plugins._a0_connector.helpers.remote_tool_prompts import (
            should_include_remote_tool_prompt,
        )
    except Exception:
        return True

    return should_include_remote_tool_prompt(agent, tool_name)


def _mcp_tools(agent: Any) -> list[tuple[str, dict[str, Any]]]:
    try:
        import helpers.mcp_handler as mcp_helper

        raw_tools = mcp_helper.MCPConfig.get_for_agent(agent).get_tools()
    except Exception:
        return []

    result: list[tuple[str, dict[str, Any]]] = []
    for entry in raw_tools or []:
        if not isinstance(entry, dict):
            continue
        for tool_name, tool in entry.items():
            if isinstance(tool, dict):
                result.append((str(tool_name), tool))
    return result


def _tool_name_from_prompt_basename(basename: str) -> str:
    if not basename.startswith(TOOL_PROMPT_PREFIX) or not basename.endswith(
        TOOL_PROMPT_SUFFIX
    ):
        return ""
    name = basename[len(TOOL_PROMPT_PREFIX) : -len(TOOL_PROMPT_SUFFIX)]
    if not name or name in {"tools", "tools_vision"}:
        return ""
    return name


def _tool_name_from_prompt(prompt: str, *, fallback: str) -> str:
    for match in TOOL_NAME_EXAMPLE_PATTERN.finditer(prompt or ""):
        name = match.group(1).strip()
        if FUNCTION_NAME_PATTERN.fullmatch(name):
            return name

    for match in TOOL_HEADING_PATTERN.finditer(prompt or ""):
        name = _tool_name_from_heading(match.group(1))
        if name:
            return name

    return fallback


def _tool_names_from_prompt(prompt: str, *, fallback: str) -> list[str]:
    declarations = [
        match.group(1) for match in TOOL_DECLARATION_PATTERN.finditer(prompt or "")
    ]
    if declarations:
        return list(dict.fromkeys(declarations))
    return [_tool_name_from_prompt(prompt, fallback=fallback)]


def _tool_name_from_heading(heading: str) -> str:
    token = (heading or "").strip().split(None, 1)[0] if heading else ""
    name = token.strip("`'\" :")
    if FUNCTION_NAME_PATTERN.fullmatch(name):
        return name
    return ""


def _native_tool_name(tool_name: str) -> str:
    if FUNCTION_NAME_PATTERN.fullmatch(tool_name):
        return tool_name
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", tool_name).strip("_")
    digest = hashlib.sha1(tool_name.encode("utf-8")).hexdigest()[:8]
    native = f"{slug[:52]}_{digest}" if slug else f"a0_tool_{digest}"
    return native[:64]


def _schema_from_prompt(prompt: str) -> dict[str, Any]:
    schema = _schema_from_embedded_json(prompt)
    if schema:
        return schema
    match = SIMPLE_ARGS_PATTERN.search(prompt or "")
    if match:
        return {
            "type": "object",
            "properties": {match.group(1): {"type": "string"}},
            "additionalProperties": True,
        }
    return _permissive_schema()


def _schema_for_tool(agent: Any, tool_name: str, prompt: str) -> dict[str, Any]:
    if schema := _schema_from_embedded_json(prompt):
        return schema
    for path in subagents.get_paths(agent, "tools", tool_name + ".py"):
        if not files.exists(path):
            continue
        relative = os.path.relpath(os.path.realpath(path), files.get_abs_path())
        properties = BUNDLED_TOOL_PARAMETERS.get(relative)
        if properties is not None:
            return {
                "type": "object",
                "properties": deepcopy(properties),
                "additionalProperties": True,
            }
        break  # A custom implementation shadows the bundled contract.
    return _schema_from_prompt(prompt)


def _schema_from_embedded_json(prompt: str) -> dict[str, Any]:
    marker = "Input schema for tool_args:"
    index = (prompt or "").find(marker)
    if index == -1:
        return {}
    tail = prompt[index + len(marker) :].strip()
    candidate = _balanced_json_object(tail)
    if not candidate:
        return {}
    try:
        return _schema_from_any(json.loads(candidate))
    except Exception:
        return {}


def _schema_from_any(schema: Any) -> dict[str, Any]:
    if isinstance(schema, dict):
        normalized = dict(schema)
        normalized.setdefault("type", "object")
        if normalized.get("type") == "object" and not isinstance(
            normalized.get("properties"), dict
        ):
            normalized["properties"] = {}
        normalized.setdefault("additionalProperties", True)
        return normalized
    return _permissive_schema()


def _permissive_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "additionalProperties": True}


def _balanced_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return ""
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _dedupe_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for tool in tools:
        name = str(tool.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(tool)
    return result


def _native_tool_description(prompt: str, tool_name: str) -> str:
    def arguments_examples(text: str) -> str:
        for root in extract_tools.extract_json_root_strings(text):
            request = extract_tools.extract_tool_request(root)
            if request is None:
                continue
            name = request.get("tool_name") or request.get("tool")
            args = request.get("tool_args", request.get("args"))
            if not isinstance(name, str) or not isinstance(args, dict):
                continue
            label = "Arguments example" if name == tool_name else f"Call {name} with arguments"
            example = f"{label}:\n```json\n{json.dumps(args, ensure_ascii=False)}\n```"
            text = text.replace(root, example)
        return text

    parts = []
    end = 0
    for match in FENCED_EXAMPLE_PATTERN.finditer(prompt):
        parts.append(arguments_examples(prompt[end:match.start()]))
        body = match.group("body")
        projected = arguments_examples(body) if match.group("language").strip().lower() == "json" else body
        parts.append(projected + "\n" if projected != body else match.group(0))
        end = match.end()
    parts.append(arguments_examples(prompt[end:]))
    return "".join(parts).strip() or tool_name
