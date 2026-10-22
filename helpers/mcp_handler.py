from abc import ABC, abstractmethod
from pathlib import Path
import re
from typing import (
    List,
    Dict,
    Optional,
    Any,
    TextIO,
    Union,
    Literal,
    Annotated,
    ClassVar,
    cast,
    Callable,
    Awaitable,
    TypeVar,
)
import threading
import asyncio
from contextlib import AsyncExitStack
from shutil import which
from datetime import timedelta
import json
import shlex
import uuid
from helpers import errors
from helpers import settings
from helpers.log import LogItem

import httpx

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.message import SessionMessage
from mcp.types import CallToolResult, ListToolsResult
from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)

from pydantic import BaseModel, Field, Discriminator, Tag, PrivateAttr
from helpers import dirty_json, files, media_artifacts
from helpers.print_style import PrintStyle
from helpers.tool import Tool, Response
from helpers.defer import DeferredTask
from helpers.responses_tools import original_tool_name


MCP_MEDIA_TOKENS_ESTIMATE = 1500
MAX_MCP_RESOURCE_TEXT_CHARS = 12_000
MCP_SESSION_CLEANUP_TIMEOUT_SECONDS = 5.0
MCP_OPERATION_TIMEOUT_GRACE_SECONDS = MCP_SESSION_CLEANUP_TIMEOUT_SECONDS + 2.0
DEFAULT_MCP_SERVERS_CONFIG = '{\n    "mcpServers": {}\n}'


def _mcp_get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def normalize_name(name: str) -> str:
    # Lowercase and strip whitespace
    name = name.strip().lower()
    # Replace all non-alphanumeric (unicode) chars with underscore
    # \W matches non-alphanumeric, but also matches underscore, so use [^\w] with re.UNICODE
    # To also replace underscores from non-latin chars, use [^a-zA-Z0-9] with re.UNICODE
    name = re.sub(r"[^\w]", "_", name, flags=re.UNICODE)
    return name


def _determine_server_type(config_dict: dict) -> str:
    """Determine the server type based on configuration, with backward compatibility."""
    # First check if type is explicitly specified
    if "type" in config_dict:
        server_type = config_dict["type"].lower()
        if server_type in ["sse", "http-stream", "streaming-http", "streamable-http", "http-streaming"]:
            return "MCPServerRemote"
        elif server_type == "stdio":
            return "MCPServerLocal"
        # For future types, we could add more cases here
        else:
            # For unknown types, fall back to URL-based detection
            # This allows for graceful handling of new types
            pass

    # Backward compatibility: if no type specified, use URL-based detection
    if "url" in config_dict or "serverUrl" in config_dict:
        return "MCPServerRemote"
    else:
        return "MCPServerLocal"


def _is_streaming_http_type(server_type: str) -> bool:
    """Check if the server type is a streaming HTTP variant."""
    return server_type.lower() in ["http-stream", "streaming-http", "streamable-http", "http-streaming"]


def _split_qualified_tool_name(tool_name: str) -> tuple[str, str]:
    """Split Agent Zero's server.tool MCP name while preserving dots in MCP tool names."""
    if "." not in tool_name:
        raise ValueError(f"Tool {tool_name} not found")
    server_name_part, tool_name_part = tool_name.split(".", 1)
    if not server_name_part or not tool_name_part:
        raise ValueError(f"Tool {tool_name} not found")
    return server_name_part, tool_name_part


def _normalize_disabled_tools(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _split_stdio_command(command: Any) -> tuple[str, list[str]]:
    text = str(command or "").strip()
    if not text:
        return "", []
    try:
        parts = shlex.split(text)
    except ValueError:
        return text, []
    if not parts:
        return "", []
    return parts[0], parts[1:]


def _split_stdio_arg_fragment(arg: str) -> list[str]:
    try:
        parts = shlex.split(arg)
    except ValueError:
        return [arg]
    if len(parts) <= 1:
        return parts or []
    if parts[0].startswith("-") and "=" not in parts[0]:
        return parts
    if any(part.startswith("-") for part in parts[1:]):
        return parts
    return [arg]


def _normalize_stdio_args(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    args: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            args.extend(_split_stdio_arg_fragment(text))
    return args


def initialize_mcp(mcp_servers_config: str):
    if not MCPConfig.get_instance().is_initialized():
        try:
            MCPConfig.update(mcp_servers_config)
        except Exception as e:
            from agent import AgentContext

            AgentContext.log_to_all(
                type="warning",
                content=f"Failed to update MCP settings: {e}",
            )

            PrintStyle(
                background_color="black", font_color="red", padding=True
            ).print(f"Failed to update MCP settings: {e}")


class MCPTool(Tool):
    """MCP Tool wrapper"""

    def get_log_object(self) -> LogItem:
        return self.agent.context.log.log(
            type="mcp",
            heading=f"icon://extension {self.agent.agent_name}: Using MCP tool '{self.name}'",
            content="",
            kvps={"tool_name": self.name, **self.args},
            id=str(uuid.uuid4()),
        )

    def _context_id(self) -> str:
        return str(getattr(getattr(self.agent, "context", None), "id", "") or "").strip()

    def _raw_tool_response(self, response: Response) -> str:
        raw_tool_response = response.message.strip() if response.message else ""
        if not raw_tool_response:
            PrintStyle(font_color="red").print(
                f"Warning: Tool '{self.name}' returned an empty message."
            )
            raw_tool_response = "[Tool returned no textual content]"
        return raw_tool_response

    def _coerce_media_token_estimate(self, value: object) -> int:
        try:
            estimate = int(value or 0)
        except (TypeError, ValueError):
            estimate = 0
        return estimate if estimate > 0 else MCP_MEDIA_TOKENS_ESTIMATE

    def _format_image_content(
        self,
        *,
        encoded: str,
        mime_type: str,
        label: str,
        index: int,
        preferred_name: str = "",
    ) -> tuple[str, dict[str, Any] | None, str]:
        try:
            safe_mime = media_artifacts.normalize_mime(
                mime_type,
                default="image/png",
                required_prefix="image/",
            )
            artifact = media_artifacts.save_base64_artifact(
                encoded,
                mime_type=safe_mime,
                directory_parts=self._artifact_directory_parts(),
                preferred_name=preferred_name,
                default_filename=self._default_artifact_filename(
                    label=label,
                    index=index,
                    mime_type=safe_mime,
                ),
            )
        except media_artifacts.EmptyBase64Data:
            return f"MCP returned an empty {label} attachment.", None, ""
        except media_artifacts.InvalidBase64Data:
            return (
                f"MCP returned a {label} attachment that could not be decoded.",
                None,
                "",
            )

        return (
            (
                f"Saved MCP {label} attachment "
                f"({artifact.mime}, {artifact.size} bytes) to {artifact.path}."
            ),
            {
                "type": "image_url",
                "image_url": {"url": artifact.path},
            },
            artifact.path,
        )

    def _materialize_binary_content(
        self,
        *,
        encoded: str,
        mime_type: str,
        label: str,
        index: int,
        preferred_name: str = "",
    ) -> str:
        try:
            safe_mime = media_artifacts.normalize_mime(mime_type)
            artifact = media_artifacts.save_base64_artifact(
                encoded,
                mime_type=safe_mime,
                directory_parts=self._artifact_directory_parts(),
                preferred_name=preferred_name,
                default_filename=self._default_artifact_filename(
                    label=label,
                    index=index,
                    mime_type=safe_mime,
                ),
            )
        except media_artifacts.EmptyBase64Data:
            return f"MCP returned an empty {label} attachment."
        except media_artifacts.InvalidBase64Data:
            return f"MCP returned a {label} attachment that could not be decoded."

        return f"Saved MCP {label} attachment ({artifact.mime}, {artifact.size} bytes) to {artifact.path}."

    def _artifact_directory_parts(self) -> tuple[str, ...]:
        context_id = normalize_name(self._context_id() or "shared") or "shared"
        tool_name = normalize_name(self.name or "mcp_tool") or "mcp_tool"
        return ("tmp", "mcp", context_id, tool_name)

    def _default_artifact_filename(self, *, label: str, index: int, mime_type: str) -> str:
        tool_name = normalize_name(self.name or "mcp_tool") or "mcp_tool"
        ext = media_artifacts.guess_extension(mime_type, ".bin")
        return f"{tool_name}_{label}_{index}{ext}"

    def _format_resource_text(self, text: str, uri: str = "") -> str:
        body = str(text or "").strip()
        if not body:
            return ""
        if len(body) > MAX_MCP_RESOURCE_TEXT_CHARS:
            body = body[:MAX_MCP_RESOURCE_TEXT_CHARS].rstrip() + "\n...[truncated]"
        if uri:
            return f"Resource {uri}:\n{body}"
        return body

    def _content_item_dump(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return dict(item)
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="python")
            if isinstance(dumped, dict):
                return dumped
        item_vars = getattr(item, "__dict__", None)
        if isinstance(item_vars, dict):
            return dict(item_vars)
        return {}

    def _summarize_unknown_item(self, item: Any, item_type: str) -> str:
        dumped = self._content_item_dump(item)
        if dumped:
            dumped.pop("data", None)
            resource = dumped.get("resource")
            if isinstance(resource, dict):
                resource.pop("blob", None)
            summary = json.dumps(dumped, ensure_ascii=False)
            if len(summary) > 600:
                summary = summary[:600] + "...[truncated]"
            return f"MCP returned unsupported content item type '{item_type}': {summary}"
        return f"MCP returned unsupported content item type '{item_type}'."

    def _format_tool_result(
        self, response: CallToolResult
    ) -> tuple[str, dict[str, Any] | None]:
        text_parts: list[str] = []
        notes: list[str] = []
        raw_images: list[dict[str, Any]] = []
        image_paths: list[str] = []
        content_items = list(getattr(response, "content", []) or [])

        for index, item in enumerate(content_items, start=1):
            item_type = str(_mcp_get(item, "type", "") or "").strip().lower()

            if item_type == "text":
                text = str(_mcp_get(item, "text", "") or "").strip()
                if text:
                    text_parts.append(text)
                continue

            if item_type == "image":
                note, raw_content, path = self._format_image_content(
                    encoded=str(_mcp_get(item, "data", "") or ""),
                    mime_type=str(_mcp_get(item, "mimeType", "") or "image/png"),
                    label="image",
                    index=index,
                )
                notes.append(note)
                if raw_content:
                    raw_images.append(raw_content)
                if path:
                    image_paths.append(path)
                continue

            if item_type == "audio":
                note = self._materialize_binary_content(
                    encoded=str(_mcp_get(item, "data", "") or ""),
                    mime_type=str(_mcp_get(item, "mimeType", "") or "audio/wav"),
                    label="audio",
                    index=index,
                )
                notes.append(note)
                continue

            if item_type == "resource":
                resource = _mcp_get(item, "resource", None)
                uri = str(_mcp_get(resource, "uri", "") or "").strip()
                text = _mcp_get(resource, "text", None)
                if isinstance(text, str) and text.strip():
                    text_parts.append(self._format_resource_text(text, uri))
                    continue

                blob = str(_mcp_get(resource, "blob", "") or "").strip()
                if blob:
                    mime_type = str(
                        _mcp_get(resource, "mimeType", "") or "application/octet-stream"
                    ).strip().lower()
                    if mime_type.startswith("image/"):
                        note, raw_content, path = self._format_image_content(
                            encoded=blob,
                            mime_type=mime_type,
                            label="resource image",
                            index=index,
                            preferred_name=uri,
                        )
                    else:
                        note = self._materialize_binary_content(
                            encoded=blob,
                            mime_type=mime_type,
                            label="resource",
                            index=index,
                            preferred_name=uri,
                        )
                        raw_content = None
                        path = ""
                    notes.append(note)
                    if raw_content:
                        raw_images.append(raw_content)
                    if path:
                        image_paths.append(path)
                    continue

                if uri:
                    mime_type = str(_mcp_get(resource, "mimeType", "") or "").strip()
                    details = f" ({mime_type})" if mime_type else ""
                    notes.append(f"MCP returned a resource reference: {uri}{details}.")
                    continue

                notes.append("MCP returned a resource item without text or binary data.")
                continue

            if item_type:
                notes.append(self._summarize_unknown_item(item, item_type))
                continue

            notes.append(self._summarize_unknown_item(item, "unknown"))

        message = "\n\n".join(part for part in [*text_parts, *notes] if part.strip())
        if not message and content_items:
            message = "MCP tool returned content that could not be rendered as text."

        additional = None
        if raw_images:
            additional = {
                "raw_content": raw_images,
                "preview": f"<MCP image attachments: {len(raw_images)}>",
                "_tokens": MCP_MEDIA_TOKENS_ESTIMATE * len(raw_images),
                "attachments": image_paths,
                "media_paths": image_paths,
            }

        return message, additional

    async def execute(self, **kwargs: Any):
        from helpers.tool_policy import canonical_mcp_id, ensure_tool_allowed

        if "." in self.name:
            ensure_tool_allowed(
                self.agent,
                self.name,
                canonical_id=canonical_mcp_id(self.name),
            )
        error = ""
        additional: dict[str, Any] | None = None
        try:
            turn = getattr(self.agent.context, "_durable_turn", None)
            turn = turn if turn and turn.agent is self.agent else None
            if turn and not hasattr(self, "_durable_session_manager"):
                from helpers.durable import sessions
                await sessions.prepare(self, kwargs)
            config = MCPConfig.get_for_agent(self.agent)
            if turn and getattr(turn.owner, "distributed", False):
                from helpers.durable.mcp_broker import invoke
                response = await invoke(self, config, kwargs)
            else:
                response = await config.call_tool(self.name, kwargs, durable_tool=self) if turn else await config.call_tool(self.name, kwargs)
            message, additional = self._format_tool_result(response)
            if response.isError:
                error = message or "MCP tool returned an error without textual content."
        except Exception as e:
            if getattr(self, "_durable_session_manager", None) is not None:
                from helpers.durable.runtime import RecoveryHeld
                raise RecoveryHeld("mcp_call_outcome_unknown") from None
            error = f"MCP Tool Exception: {str(e)}"
            message = f"ERROR: {str(e)}"

        if error:
            PrintStyle(
                background_color="#CC34C3", font_color="white", bold=True, padding=True
            ).print(f"MCPTool::Failed to call mcp tool {self.name}:")
            PrintStyle(
                background_color="#AA4455", font_color="white", padding=False
            ).print(error)

            self.agent.context.log.log(
                type="warning",
                content=f"{self.name}: {error}",
            )

        return Response(message=message, break_loop=False, additional=additional)

    async def before_execution(self, **kwargs: Any):
        (
            PrintStyle(
                font_color="#1B4F72", padding=True, background_color="white", bold=True
            ).print(f"{self.agent.agent_name}: Using tool '{self.name}'")
        )
        self.log = self.get_log_object()

        for key, value in self.args.items():
            PrintStyle(font_color="#85C1E9", bold=True).stream(
                self.nice_key(key) + ": "
            )
            PrintStyle(
                font_color="#85C1E9", padding=isinstance(value, str) and "\n" in value
            ).stream(value)
            PrintStyle().print()

    async def after_execution(self, response: Response, **kwargs: Any):
        final_text_for_agent = self._raw_tool_response(response)
        additional = dict(response.additional or {})
        raw_content = additional.pop("raw_content", None)
        preview = str(additional.pop("preview", "") or "").strip()
        token_estimate = self._coerce_media_token_estimate(additional.pop("_tokens", 0))

        self.agent.hist_add_tool_result(
            self.name,
            final_text_for_agent,
            id=self.log.id if self.log else "",
            **additional,
        )
        if raw_content:
            from helpers import history

            self.agent.hist_add_message(
                False,
                content=history.RawMessage(
                    raw_content=raw_content,
                    preview=preview or final_text_for_agent,
                ),
                tokens=token_estimate,
            )
        (
            PrintStyle(
                font_color="#1B4F72", background_color="white", padding=True, bold=True
            ).print(
                f"{self.agent.agent_name}: Response from tool '{self.name}' (plus context added)"
            )
        )
        # Print only the raw response to console for brevity, agent gets the full context.
        PrintStyle(font_color="#85C1E9").print(
            final_text_for_agent
            if final_text_for_agent
            else "[No direct textual output from tool]"
        )
        if self.log:
            self.log.update(
                content=final_text_for_agent
            )  # Log includes the full context


class MCPServerRemote(BaseModel):
    name: str = Field(default_factory=str)
    description: Optional[str] = Field(default="Remote SSE Server")
    type: str = Field(default="sse", description="Server connection type")
    url: str = Field(default_factory=str)
    headers: dict[str, Any] | None = Field(default_factory=dict[str, Any])
    init_timeout: int = Field(default=0)
    tool_timeout: int = Field(default=0)
    verify: bool = Field(default=True, description="Verify SSL certificates")
    disabled: bool = Field(default=False)
    disabled_tools: list[str] = Field(default_factory=list)
    scope: str = Field(default="global")

    __lock: ClassVar[threading.Lock] = PrivateAttr(default=threading.Lock())
    __client: Optional["MCPClientRemote"] = PrivateAttr(default=None)

    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.__client = MCPClientRemote(self)
        self.update(config)

    def get_error(self) -> str:
        with self.__lock:
            return self.__client.error  # type: ignore

    def get_log(self) -> str:
        with self.__lock:
            return self.__client.get_log()  # type: ignore

    def get_tools(self) -> List[dict[str, Any]]:
        """Get enabled tools from the server"""
        with self.__lock:
            tools = self.__client.get_tools()  # type: ignore
            disabled = set(self.disabled_tools)
            return [tool for tool in tools if tool.get("name") not in disabled]

    def get_all_tools(self) -> List[dict[str, Any]]:
        """Get all tools from the server and mark disabled tools for UI detail views."""
        with self.__lock:
            tools = self.__client.get_tools()  # type: ignore
            disabled = set(self.disabled_tools)
            return [
                {**tool, "disabled": tool.get("name") in disabled}
                for tool in tools
            ]

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        if tool_name in self.disabled_tools:
            return False
        with self.__lock:
            return self.__client.has_tool(tool_name)  # type: ignore

    async def call_tool(
        self, tool_name: str, input_data: Dict[str, Any], *, durable_tool=None
    ) -> CallToolResult:
        """Call a tool with the given input data"""
        client = self.__client
        if client is None:
            raise RuntimeError("MCP remote client is not initialized")
        if tool_name in self.disabled_tools:
            raise ValueError(f"Tool {tool_name} is disabled for server {self.name}.")
        return await client.call_tool(tool_name, input_data, **({"durable_tool": durable_tool} if durable_tool is not None else {}))

    async def validate_durable_session(self, tool_name, durable_tool):
        if self.disabled or tool_name in self.disabled_tools or self.__client is None:
            raise ValueError("MCP server/tool is unavailable")
        return await self.__client.validate_durable_session(durable_tool)

    def update(self, config: dict[str, Any]) -> "MCPServerRemote":
        with self.__lock:
            for key, value in config.items():
                if key in [
                    "name",
                    "description",
                    "type",
                    "url",
                    "serverUrl",
                    "headers",
                    "init_timeout",
                    "tool_timeout",
                    "disabled",
                    "disabled_tools",
                    "verify",
                    "scope",
                ]:
                    if key == "name":
                        value = normalize_name(value)
                    if key == "serverUrl":
                        key = "url"  # remap serverUrl to url
                    if key == "disabled_tools":
                        value = _normalize_disabled_tools(value)

                    setattr(self, key, value)
            return self

    async def initialize(self) -> "MCPServerRemote":
        await self.__client.update_tools()  # type: ignore
        return self


class MCPServerLocal(BaseModel):
    name: str = Field(default_factory=str)
    description: Optional[str] = Field(default="Local StdIO Server")
    type: str = Field(default="stdio", description="Server connection type")
    command: str = Field(default_factory=str)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = Field(default_factory=dict[str, str])
    encoding: str = Field(default="utf-8")
    encoding_error_handler: Literal["strict", "ignore", "replace"] = Field(
        default="strict"
    )
    init_timeout: int = Field(default=0)
    tool_timeout: int = Field(default=0)
    verify: bool = Field(default=True, description="Verify SSL certificates")
    disabled: bool = Field(default=False)
    disabled_tools: list[str] = Field(default_factory=list)
    scope: str = Field(default="global")

    __lock: ClassVar[threading.Lock] = PrivateAttr(default=threading.Lock())
    __client: Optional["MCPClientLocal"] = PrivateAttr(default=None)

    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.__client = MCPClientLocal(self)
        self.update(config)

    def get_error(self) -> str:
        with self.__lock:
            return self.__client.error  # type: ignore

    def get_log(self) -> str:
        with self.__lock:
            return self.__client.get_log()  # type: ignore

    def get_tools(self) -> List[dict[str, Any]]:
        """Get enabled tools from the server"""
        with self.__lock:
            tools = self.__client.get_tools()  # type: ignore
            disabled = set(self.disabled_tools)
            return [tool for tool in tools if tool.get("name") not in disabled]

    def get_all_tools(self) -> List[dict[str, Any]]:
        """Get all tools from the server and mark disabled tools for UI detail views."""
        with self.__lock:
            tools = self.__client.get_tools()  # type: ignore
            disabled = set(self.disabled_tools)
            return [
                {**tool, "disabled": tool.get("name") in disabled}
                for tool in tools
            ]

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        if tool_name in self.disabled_tools:
            return False
        with self.__lock:
            return self.__client.has_tool(tool_name)  # type: ignore

    async def call_tool(
        self, tool_name: str, input_data: Dict[str, Any], *, durable_tool=None
    ) -> CallToolResult:
        """Call a tool with the given input data"""
        client = self.__client
        if client is None:
            raise RuntimeError("MCP local client is not initialized")
        if tool_name in self.disabled_tools:
            raise ValueError(f"Tool {tool_name} is disabled for server {self.name}.")
        return await client.call_tool(tool_name, input_data, **({"durable_tool": durable_tool} if durable_tool is not None else {}))

    async def validate_durable_session(self, tool_name, durable_tool):
        if self.disabled or tool_name in self.disabled_tools or self.__client is None:
            raise ValueError("MCP server/tool is unavailable")
        return await self.__client.validate_durable_session(durable_tool)

    def update(self, config: dict[str, Any]) -> "MCPServerLocal":
        with self.__lock:
            command = self.command
            command_args: list[str] = []
            args = list(self.args)
            if "command" in config:
                command, command_args = _split_stdio_command(config.get("command"))
                args = [*command_args, *args]
            if "args" in config:
                args = [*command_args, *_normalize_stdio_args(config.get("args"))]

            for key, value in config.items():
                if key in [
                    "name",
                    "description",
                    "type",
                    "command",
                    "args",
                    "env",
                    "encoding",
                    "encoding_error_handler",
                    "init_timeout",
                    "tool_timeout",
                    "disabled",
                    "disabled_tools",
                    "scope",
                ]:
                    if key in ["command", "args"]:
                        continue
                    if key == "name":
                        value = normalize_name(value)
                    if key == "disabled_tools":
                        value = _normalize_disabled_tools(value)
                    setattr(self, key, value)
            self.command = command
            self.args = args
            return self

    async def initialize(self) -> "MCPServerLocal":
        await self.__client.update_tools()  # type: ignore
        return self


MCPServer = Annotated[
    Union[
        Annotated[MCPServerRemote, Tag("MCPServerRemote")],
        Annotated[MCPServerLocal, Tag("MCPServerLocal")],
    ],
    Discriminator(_determine_server_type),
]


class MCPConfig(BaseModel):
    servers: list[MCPServer] = Field(default_factory=list)
    disconnected_servers: list[dict[str, Any]] = Field(default_factory=list)
    config_scope: str = Field(default="global")
    __lock: ClassVar[threading.Lock] = PrivateAttr(default=threading.Lock())
    __instance: ClassVar[Any] = PrivateAttr(default=None)
    __initialized: ClassVar[bool] = PrivateAttr(default=False)
    __project_instances: ClassVar[dict[str, tuple[str, "MCPConfig"]]] = {}

    @classmethod
    def get_instance(cls) -> "MCPConfig":
        with cls.__lock:
            if cls.__instance is None:
                cls.__instance = cls(servers_list=[], config_scope="global")
            return cls.__instance

    @classmethod
    def clear_project_instances(cls):
        with cls.__lock:
            cls.__project_instances = {}

    @classmethod
    def parse_config_string(cls, config_str: str) -> List[Dict[str, Any]]:
        servers_data: List[Dict[str, Any]] = []

        if not (config_str and config_str.strip()):
            return servers_data

        try:
            parsed_value = dirty_json.try_parse(config_str)
            normalized = cls.normalize_config(parsed_value)

            if isinstance(normalized, list):
                for item in normalized:
                    if isinstance(item, dict):
                        servers_data.append(dict(item))
                    else:
                        PrintStyle(
                            background_color="yellow",
                            font_color="black",
                            padding=True,
                        ).print(
                            f"Warning: MCP config item was not a dictionary and was ignored: {item}"
                        )
            else:
                PrintStyle(
                    background_color="red", font_color="white", padding=True
                ).print(
                    f"Error: Parsed MCP config top-level structure is not a list. Config string was: '{config_str}'"
                )
        except Exception as e_json:
            PrintStyle.error(
                f"Error parsing MCP config string: {e_json}. Config string was: '{config_str}'"
            )

        return servers_data

    @classmethod
    def merge_config_strings(
        cls, global_config: str, project_config: str
    ) -> tuple[list[dict[str, Any]], str]:
        merged: dict[str, dict[str, Any]] = {}
        unnamed: list[dict[str, Any]] = []

        def add_servers(config_str: str, scope: str):
            for server in cls.parse_config_string(config_str):
                server_copy = dict(server)
                server_copy["scope"] = scope
                name = str(server_copy.get("name", "") or "").strip()
                if not name:
                    unnamed.append(server_copy)
                    continue
                normalized_name = normalize_name(name)
                server_copy["name"] = normalized_name
                merged[normalized_name] = server_copy

        add_servers(global_config or DEFAULT_MCP_SERVERS_CONFIG, "global")
        add_servers(project_config or DEFAULT_MCP_SERVERS_CONFIG, "project")

        servers = [*unnamed, *merged.values()]
        cache_key = dirty_json.stringify(
            {
                "mcpServers": {
                    s.get("name", f"unnamed_{i}"): s
                    for i, s in enumerate(servers)
                }
            }
        )
        return servers, cache_key

    @classmethod
    def get_project_instance(cls, project_name: str | None, *, force: bool = False) -> "MCPConfig":
        project_key = str(project_name or "").strip()
        if not project_key:
            return cls.get_instance()

        from helpers import projects
        project_key = projects.validate_project_name(project_key)

        global_config = settings.get_settings().get(
            "mcp_servers", DEFAULT_MCP_SERVERS_CONFIG
        )
        project_config = projects.load_project_mcp_servers(project_key)
        servers_data, cache_key = cls.merge_config_strings(global_config, project_config)

        with cls.__lock:
            cached = cls.__project_instances.get(project_key)
            if cached and cached[0] == cache_key and not force:
                return cached[1]

        instance = cls(servers_list=servers_data, config_scope=f"project:{project_key}")
        with cls.__lock:
            cls.__project_instances[project_key] = (cache_key, instance)
        return instance

    @classmethod
    def refresh_project(cls, project_name: str) -> "MCPConfig":
        project_key = str(project_name or "").strip()
        with cls.__lock:
            cls.__project_instances.pop(project_key, None)
        return cls.get_project_instance(project_key, force=True)

    @classmethod
    def get_for_agent(cls, agent: Any) -> "MCPConfig":
        try:
            from helpers import projects

            project_name = projects.get_context_project_name(agent.context)
            if project_name:
                return cls.get_project_instance(project_name)
        except Exception:
            pass
        return cls.get_instance()

    @classmethod
    def wait_for_lock(cls):
        with cls.__lock:
            return

    @classmethod
    def update(cls, config_str: str) -> Any:
        servers_data = cls.parse_config_string(config_str)
        new_instance = cls(servers_list=servers_data, config_scope="global")
        with cls.__lock:
            # Build and initialize outside the class lock so a slow or wedged MCP
            # server cannot freeze status reads, prompts, or later tool calls.
            instance = cls.__instance
            if instance is None:
                instance = new_instance
                cls.__instance = instance
            else:
                instance.servers = new_instance.servers
                instance.disconnected_servers = new_instance.disconnected_servers
                instance.config_scope = new_instance.config_scope
            cls.__project_instances = {}
            cls.__initialized = True
            return instance

    @classmethod
    def normalize_config(cls, servers: Any):
        normalized = []
        if isinstance(servers, list):
            for server in servers:
                if isinstance(server, dict):
                    normalized.append(dict(server))
        elif isinstance(servers, dict):
            if "mcpServers" in servers:
                if isinstance(servers["mcpServers"], dict):
                    for key, value in servers["mcpServers"].items():
                        if isinstance(value, dict):
                            server = dict(value)
                            server["name"] = key
                            normalized.append(server)
                elif isinstance(servers["mcpServers"], list):
                    for server in servers["mcpServers"]:
                        if isinstance(server, dict):
                            normalized.append(dict(server))
            else:
                normalized.append(dict(servers))  # single server?
        return normalized

    def __init__(self, servers_list: List[Dict[str, Any]], config_scope: str = "global"):
        from collections.abc import Mapping, Iterable

        # # DEBUG: Print the received servers_list
        # if servers_list:
        #     PrintStyle(background_color="blue", font_color="white", padding=True).print(
        #         f"MCPConfig.__init__ received servers_list: {servers_list}"
        #     )

        # This empties the servers list if MCPConfig is a Pydantic model and servers is a field.
        # If servers is a field like `servers: List[MCPServer] = Field(default_factory=list)`,
        # then super().__init__() might try to initialize it.
        # We are re-assigning self.servers later in this __init__.
        super().__init__()

        # Clear any servers potentially initialized by super().__init__() before we populate based on servers_list
        self.servers = []
        self.config_scope = config_scope
        # initialize failed servers list
        self.disconnected_servers = []

        if not isinstance(servers_list, Iterable):
            (
                PrintStyle(
                    background_color="grey", font_color="red", padding=True
                ).print("MCPConfig::__init__::servers_list must be a list")
            )
            return

        for server_item in servers_list:
            if not isinstance(server_item, Mapping):
                # log the error
                error_msg = "server_item must be a mapping"
                (
                    PrintStyle(
                        background_color="grey", font_color="red", padding=True
                    ).print(f"MCPConfig::__init__::{error_msg}")
                )
                # add to failed servers with generic name
                self.disconnected_servers.append(
                    {
                        "config": (
                            server_item
                            if isinstance(server_item, dict)
                            else {"raw": str(server_item)}
                        ),
                        "error": error_msg,
                        "name": "invalid_server_config",
                    }
                )
                continue

            server_item = dict(server_item)
            server_item["disabled_tools"] = _normalize_disabled_tools(
                server_item.get("disabled_tools")
            )

            if server_item.get("disabled", False):
                # get server name if available
                server_name = server_item.get("name", "unnamed_server")
                # normalize server name if it exists
                if server_name != "unnamed_server":
                    server_name = normalize_name(server_name)

                # add to failed servers
                self.disconnected_servers.append(
                    {
                        "config": server_item,
                        "error": "Disabled in config",
                        "name": server_name,
                    }
                )
                continue

            server_name = server_item.get("name", "__not__found__")
            if server_name == "__not__found__":
                # log the error
                error_msg = "server_name is required"
                (
                    PrintStyle(
                        background_color="grey", font_color="red", padding=True
                    ).print(f"MCPConfig::__init__::{error_msg}")
                )
                # add to failed servers
                self.disconnected_servers.append(
                    {
                        "config": server_item,
                        "error": error_msg,
                        "name": "unnamed_server",
                    }
                )
                continue

            try:
                # not generic MCPServer because: "Annotated can not be instatioated"
                if server_item.get("url", None) or server_item.get("serverUrl", None):
                    self.servers.append(MCPServerRemote(server_item))
                else:
                    self.servers.append(MCPServerLocal(server_item))
            except Exception as e:
                # log the error
                error_msg = str(e)
                (
                    PrintStyle(
                        background_color="grey", font_color="red", padding=True
                    ).print(
                        f"MCPConfig::__init__: Failed to create MCPServer '{server_name}': {error_msg}"
                    )
                )
                # add to failed servers
                self.disconnected_servers.append(
                    {"config": server_item, "error": error_msg, "name": server_name}
                )

        # Initialize all servers in parallel (fetch tools concurrently)
        if self.servers:
            async def _init_server(server):
                try:
                    await server.initialize()
                except Exception as e:
                    error_msg = str(e)
                    PrintStyle(
                        background_color="grey", font_color="red", padding=True
                    ).print(
                        f"MCPConfig::__init__: Failed to initialize MCPServer '{server.name}': {error_msg}"
                    )

            async def _init_all():
                await asyncio.gather(*[_init_server(s) for s in self.servers])

            asyncio.run(_init_all())

    def get_server_log(self, server_name: str) -> str:
        with self.__lock:
            for server in self.servers:
                if server.name == server_name:
                    return server.get_log()  # type: ignore
            return ""

    def get_servers_status(self) -> list[dict[str, Any]]:
        """Get status of all servers"""
        result = []
        with self.__lock:
            # add connected/working servers
            for server in self.servers:
                # get server name
                name = server.name
                # get tool count
                tool_count = len(server.get_tools())
                # get error message if any
                error = server.get_error()
                # A server object can exist while its initialization failed.
                connected = not bool(error)
                # get log bool
                has_log = server.get_log() != ""

                # add server status to result
                result.append(
                    {
                        "name": name,
                        "scope": getattr(server, "scope", self.config_scope),
                        "type": getattr(server, "type", ""),
                        "description": getattr(server, "description", ""),
                        "connected": connected,
                        "error": error,
                        "tool_count": tool_count,
                        "has_log": has_log,
                    }
                )

            # add failed servers
            for disconnected in self.disconnected_servers:
                result.append(
                    {
                        "name": disconnected["name"],
                        "scope": disconnected.get("config", {}).get("scope", self.config_scope),
                        "type": disconnected.get("config", {}).get("type", ""),
                        "description": disconnected.get("config", {}).get("description", ""),
                        "connected": False,
                        "error": disconnected["error"],
                        "tool_count": 0,
                        "has_log": False,
                    }
                )

        return result

    def get_server_detail(self, server_name: str) -> dict[str, Any]:
        with self.__lock:
            for server in self.servers:
                if server.name == server_name:
                    try:
                        get_all_tools = getattr(server, "get_all_tools", None)
                        tools = get_all_tools() if callable(get_all_tools) else server.get_tools()
                    except Exception:
                        tools = []
                    return {
                        "name": server.name,
                        "description": server.description,
                        "scope": getattr(server, "scope", self.config_scope),
                        "type": getattr(server, "type", ""),
                        "tools": tools,
                    }
            return {}

    def is_initialized(self) -> bool:
        """Check if the client is initialized"""
        with self.__lock:
            return self.__initialized

    def get_tools(self) -> List[dict[str, dict[str, Any]]]:
        """Get all tools from all servers"""
        with self.__lock:
            tools = []
            for server in self.servers:
                for tool in server.get_tools():
                    tool_copy = tool.copy()
                    tool_copy["server"] = server.name
                    tools.append({f"{server.name}.{tool['name']}": tool_copy})
            return tools

    def get_tools_prompt(self, server_name: str = "", agent: Any | None = None, *, include_tools: bool = True) -> str:
        """Get a prompt for all tools"""

        # just to wait for pending initialization
        with self.__lock:
            pass

        def render(file: str, **kwargs: Any) -> str:
            if agent is not None:
                return agent.read_prompt(file, **kwargs).strip()
            return files.read_prompt_file(
                file,
                _directories=[str(Path(__file__).resolve().parents[1] / "prompts")],
                **kwargs,
            ).strip()

        server_names = []
        for server in self.servers:
            if not server_name or server.name == server_name:
                server_names.append(server.name)

        if server_name and server_name not in server_names:
            raise ValueError(f"Server {server_name} not found")

        policy = None
        if agent is not None:
            from helpers import tool_policy

        server_prompts: list[str] = []
        for server in self.servers:
            if server.name in server_names:
                selected_server_name = server.name
                tool_prompts: list[str] = []

                for tool in server.get_tools():
                    qualified_name = f"{selected_server_name}.{tool['name']}"
                    if agent is not None:
                        if policy is None:
                            policy = tool_policy.get_policy(agent)
                        if not tool_policy.resolve_tool(
                            agent,
                            qualified_name,
                            canonical_id=tool_policy.canonical_mcp_id(qualified_name),
                            _policy=policy,
                        ).allowed:
                            continue
                    if not include_tools:
                        tool_prompts.append("")
                        continue
                    input_schema = (
                        json.dumps(tool["input_schema"]) if tool["input_schema"] else ""
                    )
                    tool_prompts.append(
                        render(
                            "agent.system.mcp_tool.md",
                            qualified_name=qualified_name,
                            description=tool["description"],
                            input_schema=input_schema,
                        )
                    )

                if tool_prompts:
                    server_prompts.append(
                        render(
                            "agent.system.mcp_server.md",
                            server_name=selected_server_name,
                            server_description=server.description,
                            tools="\n\n".join(tool_prompts),
                        )
                    )

        if not server_prompts:
            return ""
        servers = "\n".join(server_prompts)
        if not include_tools:
            return servers
        return render("agent.system.mcp_tools.md", tools=servers) + "\n"

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        try:
            server_name_part, tool_name_part = _split_qualified_tool_name(tool_name)
        except ValueError:
            return False
        with self.__lock:
            for server in self.servers:
                if server.name == server_name_part:
                    return server.has_tool(tool_name_part)
            return False

    def get_tool(self, agent: Any, tool_name: str) -> MCPTool | None:
        effective_config = MCPConfig.get_for_agent(agent)
        if effective_config is not self:
            return effective_config.get_tool(agent, tool_name)
        if not self.has_tool(tool_name):
            get_data = getattr(agent, "get_data", None)
            name_map_key = getattr(agent, "DATA_NAME_RESPONSES_TOOL_NAME_MAP", "")
            tool_name = original_tool_name(
                tool_name,
                get_data(name_map_key)
                if name_map_key and callable(get_data)
                else None,
            )
            if not self.has_tool(tool_name):
                return None
        return MCPTool(agent=agent, name=tool_name, method=None, args={}, message="", loop_data=None)

    async def validate_durable_session(self, tool):
        server_name, tool_name = _split_qualified_tool_name(tool.name)
        with self.__lock:
            server = next((item for item in self.servers if item.name == server_name and item.has_tool(tool_name)), None)
        if server is None:
            raise ValueError("MCP server/tool is unavailable")
        return await server.validate_durable_session(tool_name, tool)

    async def call_tool(
        self, tool_name: str, input_data: Dict[str, Any], *, durable_tool=None
    ) -> CallToolResult:
        """Call a tool with the given input data"""
        server_name_part, tool_name_part = _split_qualified_tool_name(tool_name)
        matched_server = None
        with self.__lock:
            for server in self.servers:
                if server.name == server_name_part and server.has_tool(tool_name_part):
                    matched_server = server
                    break
        if matched_server is None:
            raise ValueError(f"Tool {tool_name} not found")
        return await matched_server.call_tool(tool_name_part, input_data, **({"durable_tool": durable_tool} if durable_tool is not None else {}))


T = TypeVar("T")


class _MCPRecoveryHold(Exception):
    """Carry a hold through DeferredTask's Exception-only worker boundary."""


class MCPClientBase(ABC):
    # server: Union[MCPServerLocal, MCPServerRemote] # Defined in __init__
    # tools: List[dict[str, Any]] # Defined in __init__
    # No self.session, self.exit_stack, self.stdio, self.write as persistent instance fields

    __lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, server: Union[MCPServerLocal, MCPServerRemote]):
        self.server = server
        self.tools: List[dict[str, Any]] = []  # Tools are cached on the client instance
        self.error: str = ""
        self.log: List[str] = []
        self.log_file: Optional[TextIO] = None

    def _operation_timeout_seconds(self, read_timeout_seconds: float) -> float:
        try:
            seconds = float(read_timeout_seconds)
        except (TypeError, ValueError):
            seconds = 60.0
        if seconds <= 0:
            seconds = 60.0
        return seconds + MCP_OPERATION_TIMEOUT_GRACE_SECONDS

    def _operation_thread_name(self, operation_name: str) -> str:
        server_name = normalize_name(str(getattr(self.server, "name", "") or "server"))
        return f"MCPClient-{server_name[:32] or 'server'}-{operation_name}-{uuid.uuid4().hex[:8]}"

    async def _run_isolated_operation(
        self,
        operation_name: str,
        operation: Callable[[], Awaitable[T]],
        timeout_seconds: float,
    ) -> T:
        worker = DeferredTask(thread_name=self._operation_thread_name(operation_name))
        timed_out = False
        try:
            return await asyncio.wait_for(
                worker.execute_inside(operation),
                timeout=timeout_seconds,
            )
        except _MCPRecoveryHold as exc:
            from helpers.durable.runtime import RecoveryHeld
            raise RecoveryHeld(str(exc)) from None
        except asyncio.TimeoutError as exc:
            timed_out = True
            message = (
                f"MCPClientBase ({self.server.name} - {operation_name}): "
                f"operation did not finish within {timeout_seconds:.1f}s; "
                "abandoning the isolated worker so Agent Zero can continue."
            )
            PrintStyle.warning(message)
            with self.__lock:
                self.error = message
            raise TimeoutError(message) from exc
        finally:
            if timed_out:
                worker.kill(terminate_thread=False)
            else:
                worker.kill(terminate_thread=True)

    # Protected method
    @abstractmethod
    async def _create_stdio_transport(
        self, current_exit_stack: AsyncExitStack
    ) -> tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
    ]:
        """Create stdio/write streams using the provided exit_stack."""
        ...

    async def _execute_with_session(
        self,
        coro_func: Callable[[ClientSession], Awaitable[T]],
        read_timeout_seconds=60,
        session_validator=None,
    ) -> T:
        """
        Manages the lifecycle of an MCP session for a single operation.
        Creates a temporary session, executes coro_func with it, and ensures cleanup.
        """
        operation_name = coro_func.__name__  # For logging
        # PrintStyle(font_color="cyan").print(f"MCPClientBase ({self.server.name}): Creating new session for operation '{operation_name}'...")
        original_exception = None
        result: T | None = None
        has_result = False
        temp_stack = AsyncExitStack()
        try:
            stdio, write = await self._create_stdio_transport(temp_stack)
            # PrintStyle(font_color="cyan").print(f"MCPClientBase ({self.server.name} - {operation_name}): Transport created. Initializing session...")
            session = await temp_stack.enter_async_context(
                ClientSession(
                    stdio,  # type: ignore
                    write,  # type: ignore
                    read_timeout_seconds=timedelta(
                        seconds=read_timeout_seconds
                    ),
                )
            )
            initialized = await session.initialize()
            if session_validator is not None:
                await session_validator(session, initialized)

            result = await coro_func(session)
            has_result = True
        except BaseException as e:
            excs = getattr(e, "exceptions", None)  # Python 3.11+ ExceptionGroup
            if excs:
                original_exception = excs[0]
            else:
                original_exception = e
        try:
            await asyncio.wait_for(
                temp_stack.aclose(),
                timeout=MCP_SESSION_CLEANUP_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            PrintStyle.warning(
                f"MCPClientBase ({self.server.name} - {operation_name}): "
                f"session cleanup exceeded {MCP_SESSION_CLEANUP_TIMEOUT_SECONDS:.1f}s."
            )
        except Exception as cleanup_exception:
            PrintStyle.warning(
                f"MCPClientBase ({self.server.name} - {operation_name}): "
                f"session cleanup failed: {type(cleanup_exception).__name__}: {cleanup_exception}"
            )
        if original_exception is not None:
            if not isinstance(original_exception, Exception):
                from helpers.durable.runtime import RecoveryHeld
                if isinstance(original_exception, RecoveryHeld):
                    raise _MCPRecoveryHold(str(original_exception)) from None
                raise original_exception
            PrintStyle(
                background_color="#AA4455", font_color="white", padding=False
            ).print(
                f"MCPClientBase ({self.server.name} - {operation_name}): Error during operation: {type(original_exception).__name__}: {original_exception}"
            )
            raise original_exception
        if has_result:
            return cast(T, result)
        raise RuntimeError(
            f"MCPClientBase ({self.server.name} - {operation_name}): _execute_with_session exited 'async with' block unexpectedly."
        )

    async def update_tools(self) -> "MCPClientBase":
        # PrintStyle(font_color="cyan").print(f"MCPClientBase ({self.server.name}): Starting 'update_tools' operation...")

        async def list_tools_op(current_session: ClientSession):
            response: ListToolsResult = await current_session.list_tools()
            with self.__lock:
                self.tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema,
                    }
                    for tool in response.tools
                ]
                self.error = ""
            PrintStyle(font_color="green").print(
                f"MCPClientBase ({self.server.name}): Tools updated. Found {len(self.tools)} tools."
            )

        try:
            current_settings = settings.get_settings()
            init_timeout = (
                self.server.init_timeout
                or current_settings.get("mcp_client_init_timeout", 10)
                or 10
            )
            await self._run_isolated_operation(
                "update_tools",
                lambda: self._execute_with_session(
                    list_tools_op,
                    read_timeout_seconds=init_timeout,
                ),
                timeout_seconds=self._operation_timeout_seconds(init_timeout),
            )
        except Exception as e:
            # e = eg.exceptions[0]
            error_text = errors.format_error(e, 0, 0)
            # Error already logged by _execute_with_session, this is for specific handling if needed
            PrintStyle(
                background_color="#CC34C3", font_color="white", bold=True, padding=True
            ).print(
                f"MCPClientBase ({self.server.name}): 'update_tools' operation failed: {error_text}"
            )
            with self.__lock:
                self.tools = []  # Ensure tools are cleared on failure
                self.error = f"Failed to initialize. {error_text[:200]}{'...' if len(error_text) > 200 else ''}"  # store error from tools fetch
        return self

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available (uses cached tools)"""
        with self.__lock:
            for tool in self.tools:
                if tool["name"] == tool_name:
                    return True
        return False

    def get_tools(self) -> List[dict[str, Any]]:
        """Get all tools from the server (uses cached tools)"""
        with self.__lock:
            return [dict(tool) for tool in self.tools]

    def _durable_validator(self, durable_tool):
        async def validate_session(session, initialized):
            from helpers.durable.sessions import validate_mcp
            advertised = await session.list_tools()
            await validate_mcp(
                durable_tool, self.server,
                initialized.model_dump(mode="json", by_alias=True, exclude_none=True),
                [item.model_dump(mode="json", by_alias=True, exclude_none=True)
                 for item in advertised.tools],
            )

        return validate_session

    async def validate_durable_session(self, durable_tool):
        async def probe(session):
            return None
        timeout = self.server.init_timeout or settings.get_settings().get("mcp_client_init_timeout", 10) or 10
        return await self._run_isolated_operation(
            "durable_validate", lambda: self._execute_with_session(
                probe, read_timeout_seconds=timeout,
                session_validator=self._durable_validator(durable_tool)),
            timeout_seconds=self._operation_timeout_seconds(timeout))

    async def call_tool(
        self, tool_name: str, input_data: Dict[str, Any], *, durable_tool=None
    ) -> CallToolResult:
        # PrintStyle(font_color="cyan").print(f"MCPClientBase ({self.server.name}): Preparing for 'call_tool' operation for tool '{tool_name}'.")
        if not self.has_tool(tool_name):
            PrintStyle(font_color="orange").print(
                f"MCPClientBase ({self.server.name}): Tool '{tool_name}' not in cache for 'call_tool', refreshing tools..."
            )
            await self.update_tools()  # This will use its own properly managed session
            if not self.has_tool(tool_name):
                PrintStyle(font_color="red").print(
                    f"MCPClientBase ({self.server.name}): Tool '{tool_name}' not found after refresh. Raising ValueError."
                )
                raise ValueError(
                    f"Tool {tool_name} not found after refreshing tool list for server {self.server.name}."
                )
            PrintStyle(font_color="green").print(
                f"MCPClientBase ({self.server.name}): Tool '{tool_name}' found after updating tools."
            )

        current_settings = settings.get_settings()
        tool_timeout = (
            self.server.tool_timeout
            or current_settings.get("mcp_client_tool_timeout", 120)
            or 120
        )


        async def call_tool_op(current_session: ClientSession):
            # PrintStyle(font_color="cyan").print(f"MCPClientBase ({self.server.name}): Executing 'call_tool' for '{tool_name}' via MCP session...")
            response: CallToolResult = await current_session.call_tool(
                tool_name,
                input_data,
                read_timeout_seconds=timedelta(seconds=tool_timeout),
            )
            # PrintStyle(font_color="green").print(f"MCPClientBase ({self.server.name}): Tool '{tool_name}' call successful via session.")
            return response

        try:
            response = await self._run_isolated_operation(
                "call_tool",
                lambda: self._execute_with_session(
                    call_tool_op,
                    read_timeout_seconds=tool_timeout,
                    **({"session_validator": self._durable_validator(durable_tool)} if durable_tool is not None else {}),
                ),
                timeout_seconds=self._operation_timeout_seconds(tool_timeout),
            )
            with self.__lock:
                self.error = ""
            return response
        except Exception as e:
            # Error logged by _execute_with_session. Re-raise a specific error for the caller.
            PrintStyle(
                background_color="#AA4455", font_color="white", padding=True
            ).print(
                f"MCPClientBase ({self.server.name}): 'call_tool' operation for '{tool_name}' failed: {type(e).__name__}: {e}"
            )
            raise ConnectionError(
                f"MCPClientBase::Failed to call tool '{tool_name}' on server '{self.server.name}'. Original error: {type(e).__name__}: {e}"
            )

    def get_log(self):
        # read and return lines from self.log_file, do not close it
        if not hasattr(self, "log_file") or self.log_file is None:
            return ""
        self.log_file.seek(0)
        try:
            log = self.log_file.read()
        except Exception:
            log = ""
        return log


class MCPClientLocal(MCPClientBase):
    def __del__(self):
        # close the log file if it exists
        if hasattr(self, "log_file") and self.log_file is not None:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

    async def _create_stdio_transport(
        self, current_exit_stack: AsyncExitStack
    ) -> tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
    ]:
        """Connect to an MCP server, init client and save stdio/write streams"""
        server: MCPServerLocal = cast(MCPServerLocal, self.server)

        if not server.command:
            raise ValueError("Command not specified")
        if not which(server.command):
            raise ValueError(f"Command '{server.command}' not found")

        server_params = StdioServerParameters(
            command=server.command,
            args=server.args,
            env={key: value for key, value in (server.env or {}).items()
                 if not key.startswith("A0_DURABILITY_")},
            encoding=server.encoding,
            encoding_error_handler=server.encoding_error_handler,
        )
        # create a custom error log handler that will capture error output
        import tempfile

        # use a temporary file for error logging (text mode) if not already present
        if not hasattr(self, "log_file") or self.log_file is None:
            self.log_file = tempfile.TemporaryFile(mode="w+", encoding="utf-8")

        # use the stdio_client with our error log file
        stdio_transport = await current_exit_stack.enter_async_context(
            stdio_client(server_params, errlog=self.log_file)
        )
        # do not read or close the file here, as stdio is async
        return stdio_transport

class CustomHTTPClientFactory(ABC):
    def __init__(self, verify: bool = True):
        self.verify = verify

    def __call__(
        self,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        # Set MCP defaults
        kwargs: dict[str, Any] = {
            "follow_redirects": True,
        }

        # Handle timeout
        if timeout is None:
            kwargs["timeout"] = httpx.Timeout(30.0)
        else:
            kwargs["timeout"] = timeout

        # Handle headers
        if headers is not None:
            kwargs["headers"] = headers

        # Handle authentication
        if auth is not None:
            kwargs["auth"] = auth

        return httpx.AsyncClient(**kwargs, verify=self.verify)

class MCPClientRemote(MCPClientBase):

    def __init__(self, server: Union[MCPServerLocal, MCPServerRemote]):
        super().__init__(server)
        self.session_id: Optional[str] = None  # Track session ID for streaming HTTP clients
        self.session_id_callback: Optional[Callable[[], Optional[str]]] = None

    async def _create_stdio_transport(
        self, current_exit_stack: AsyncExitStack
    ) -> tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
    ]:
        """Connect to an MCP server, init client and save stdio/write streams"""
        server: MCPServerRemote = cast(MCPServerRemote, self.server)
        current_settings = settings.get_settings()

        # Resolve timeout: check server config first, then settings, defaulting to 5s/10s
        init_timeout = (
            server.init_timeout
            or current_settings.get("mcp_client_init_timeout", 10)
            or 10
        )
        tool_timeout = (
            server.tool_timeout
            or current_settings.get("mcp_client_tool_timeout", 120)
            or 120
        )

        client_factory = CustomHTTPClientFactory(verify=server.verify)
        # Check if this is a streaming HTTP type
        if _is_streaming_http_type(server.type):
            # Use streamable HTTP client
            transport_result = await current_exit_stack.enter_async_context(
                streamablehttp_client(
                    url=server.url,
                    headers=server.headers,
                    timeout=timedelta(seconds=init_timeout),
                    sse_read_timeout=timedelta(seconds=tool_timeout),
                    httpx_client_factory=client_factory,
                )
            )
            # streamablehttp_client returns (read_stream, write_stream, get_session_id_callback)
            read_stream, write_stream, get_session_id_callback = transport_result

            # Store session ID callback for potential future use
            self.session_id_callback = get_session_id_callback

            return read_stream, write_stream
        else:
            # Use traditional SSE client (default behavior)
            stdio_transport = await current_exit_stack.enter_async_context(
                sse_client(
                    url=server.url,
                    headers=server.headers,
                    timeout=init_timeout,
                    sse_read_timeout=tool_timeout,
                    httpx_client_factory=client_factory,
                )
            )
            return stdio_transport

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID if available (for streaming HTTP clients)."""
        if self.session_id_callback is not None:
            return self.session_id_callback()
        return None
