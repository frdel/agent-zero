from abc import ABC, abstractmethod
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
from python.helpers import errors
from python.helpers import settings

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
from python.helpers import dirty_json
from python.helpers.print_style import PrintStyle
from python.helpers.tool import Tool, Response


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


def initialize_mcp(mcp_servers_config: str):
    if not MCPConfig.get_instance().is_initialized():
        try:
            MCPConfig.update(mcp_servers_config)
        except Exception as e:
            from agent import AgentContext

            AgentContext.log_to_all(
                type="warning",
                content=f"Failed to update MCP settings: {e}",
                temp=False,
            )

            PrintStyle(
                background_color="black", font_color="red", padding=True
            ).print(f"Failed to update MCP settings: {e}")


class MCPTool(Tool):
    """MCP Tool wrapper"""

    async def execute(self, **kwargs: Any):
        error = ""
        try:
            response: CallToolResult = await MCPConfig.get_instance().call_tool(
                self.name, kwargs
            )
            message = "\n\n".join(
                [item.text for item in response.content if item.type == "text"]
            )
            if response.isError:
                error = message
        except Exception as e:
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

        return Response(message=message, break_loop=False)

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
        raw_tool_response = response.message.strip() if response.message else ""
        if not raw_tool_response:
            PrintStyle(font_color="red").print(
                f"Warning: Tool '{self.name}' returned an empty message."
            )
            # Even if empty, we might still want to provide context for the agent
            raw_tool_response = "[Tool returned no textual content]"

        # Prepare user message context
        user_message_text = (
            "No specific user message context available for this exact step."
        )
        if (
            self.agent
            and self.agent.last_user_message
            and self.agent.last_user_message.content
        ):
            content = self.agent.last_user_message.content
            if isinstance(content, dict):
                # Attempt to get a 'message' field, otherwise stringify the dict
                user_message_text = str(content.get(
                    "message", json.dumps(content, indent=2)
                ))
            elif isinstance(content, str):
                user_message_text = content
            else:
                # Fallback for any other types (e.g. list, if that were possible for content)
                user_message_text = str(content)

        # Ensure user_message_text is a string before length check and slicing
        user_message_text = str(user_message_text)

        # Truncate user message context if it's too long to avoid overwhelming the prompt
        max_user_context_len = 500  # characters
        if len(user_message_text) > max_user_context_len:
            user_message_text = (
                user_message_text[:max_user_context_len] + "... (truncated)"
            )

        final_text_for_agent = raw_tool_response

        self.agent.hist_add_tool_result(self.name, final_text_for_agent)
        (
            PrintStyle(
                font_color="#1B4F72", background_color="white", padding=True, bold=True
            ).print(
                f"{self.agent.agent_name}: Response from tool '{self.name}' (plus context added)"
            )
        )
        # Print only the raw response to console for brevity, agent gets the full context.
        PrintStyle(font_color="#85C1E9").print(
            raw_tool_response
            if raw_tool_response
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
    disabled: bool = Field(default=False)

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
        """Get all tools from the server"""
        with self.__lock:
            return self.__client.tools  # type: ignore

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        with self.__lock:
            return self.__client.has_tool(tool_name)  # type: ignore

    async def call_tool(
        self, tool_name: str, input_data: Dict[str, Any]
    ) -> CallToolResult:
        """Call a tool with the given input data"""
        with self.__lock:
            # We already run in an event loop, dont believe Pylance
            return await self.__client.call_tool(tool_name, input_data)  # type: ignore

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
                ]:
                    if key == "name":
                        value = normalize_name(value)
                    if key == "serverUrl":
                        key = "url"  # remap serverUrl to url

                    setattr(self, key, value)
            # We already run in an event loop, dont believe Pylance
            return asyncio.run(self.__on_update())

    async def __on_update(self) -> "MCPServerRemote":
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
    disabled: bool = Field(default=False)

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
        """Get all tools from the server"""
        with self.__lock:
            return self.__client.tools  # type: ignore

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        with self.__lock:
            return self.__client.has_tool(tool_name)  # type: ignore

    async def call_tool(
        self, tool_name: str, input_data: Dict[str, Any]
    ) -> CallToolResult:
        """Call a tool with the given input data"""
        with self.__lock:
            # We already run in an event loop, dont believe Pylance
            return await self.__client.call_tool(tool_name, input_data)  # type: ignore

    def update(self, config: dict[str, Any]) -> "MCPServerLocal":
        with self.__lock:
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
                ]:
                    if key == "name":
                        value = normalize_name(value)
                    setattr(self, key, value)
            # We already run in an event loop, dont believe Pylance
            return asyncio.run(self.__on_update())

    async def __on_update(self) -> "MCPServerLocal":
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
    __lock: ClassVar[threading.Lock] = PrivateAttr(default=threading.Lock())
    __instance: ClassVar[Any] = PrivateAttr(default=None)
    __initialized: ClassVar[bool] = PrivateAttr(default=False)

    @classmethod
    def get_instance(cls) -> "MCPConfig":
        # with cls.__lock:
        if cls.__instance is None:
            cls.__instance = cls(servers_list=[])
        return cls.__instance

    @classmethod
    def wait_for_lock(cls):
        with cls.__lock:
            return

    @classmethod
    def update(cls, config_str: str) -> Any:
        with cls.__lock:
            servers_data: List[Dict[str, Any]] = []  # Default to empty list

            if (
                config_str and config_str.strip()
            ):  # Only parse if non-empty and not just whitespace
                try:
                    # Try with standard json.loads first, as it should handle escaped strings correctly
                    parsed_value = dirty_json.try_parse(config_str)
                    normalized = cls.normalize_config(parsed_value)

                    if isinstance(normalized, list):
                        valid_servers = []
                        for item in normalized:
                            if isinstance(item, dict):
                                valid_servers.append(item)
                            else:
                                PrintStyle(
                                    background_color="yellow",
                                    font_color="black",
                                    padding=True,
                                ).print(
                                    f"Warning: MCP config item (from json.loads) was not a dictionary and was ignored: {item}"
                                )
                        servers_data = valid_servers
                    else:
                        PrintStyle(
                            background_color="red", font_color="white", padding=True
                        ).print(
                            f"Error: Parsed MCP config (from json.loads) top-level structure is not a list. Config string was: '{config_str}'"
                        )
                        # servers_data remains empty
                except (
                    Exception
                ) as e_json:  # Catch json.JSONDecodeError specifically if possible, or general Exception
                    PrintStyle.error(
                        f"Error parsing MCP config string: {e_json}. Config string was: '{config_str}'"
                    )

                    # # Fallback to DirtyJson or log error if standard json.loads fails
                    # PrintStyle(background_color="orange", font_color="black", padding=True).print(
                    #     f"Standard json.loads failed for MCP config: {e_json}. Attempting DirtyJson as fallback."
                    # )
                    # try:
                    #     parsed_value = DirtyJson.parse_string(config_str)
                    #     if isinstance(parsed_value, list):
                    #         valid_servers = []
                    #         for item in parsed_value:
                    #             if isinstance(item, dict):
                    #                 valid_servers.append(item)
                    #             else:
                    #                 PrintStyle(background_color="yellow", font_color="black", padding=True).print(
                    #                     f"Warning: MCP config item (from DirtyJson) was not a dictionary and was ignored: {item}"
                    #                 )
                    #         servers_data = valid_servers
                    #     else:
                    #         PrintStyle(background_color="red", font_color="white", padding=True).print(
                    #             f"Error: Parsed MCP config (from DirtyJson) top-level structure is not a list. Config string was: '{config_str}'"
                    #         )
                    #         # servers_data remains empty
                    # except Exception as e_dirty:
                    #     PrintStyle(background_color="red", font_color="white", padding=True).print(
                    #         f"Error parsing MCP config string with DirtyJson as well: {e_dirty}. Config string was: '{config_str}'"
                    #     )
                    #     # servers_data remains empty, allowing graceful degradation

            # Initialize/update the singleton instance with the (potentially empty) list of server data
            instance = cls.get_instance()
            # Directly update the servers attribute of the existing instance or re-initialize carefully
            # For simplicity and to ensure __init__ logic runs if needed for setup:
            new_instance_data = {
                "servers": servers_data
            }  # Prepare data for re-initialization or update

            # Option 1: Re-initialize the existing instance (if __init__ is idempotent for other fields)
            instance.__init__(servers_list=servers_data)

            # Option 2: Or, if __init__ has side effects we don't want to repeat,
            # and 'servers' is the primary thing 'update' changes:
            # instance.servers = [] # Clear existing servers first
            # for server_item_data in servers_data:
            #     try:
            #         if server_item_data.get("url", None):
            #             instance.servers.append(MCPServerRemote(server_item_data))
            #         else:
            #             instance.servers.append(MCPServerLocal(server_item_data))
            #     except Exception as e_init:
            #         PrintStyle(background_color="grey", font_color="red", padding=True).print(
            #             f"MCPConfig.update: Failed to create MCPServer from item '{server_item_data.get('name', 'Unknown')}': {e_init}"
            #         )

            cls.__initialized = True
            return instance

    @classmethod
    def normalize_config(cls, servers: Any):
        normalized = []
        if isinstance(servers, list):
            for server in servers:
                if isinstance(server, dict):
                    normalized.append(server)
        elif isinstance(servers, dict):
            if "mcpServers" in servers:
                if isinstance(servers["mcpServers"], dict):
                    for key, value in servers["mcpServers"].items():
                        if isinstance(value, dict):
                            value["name"] = key
                            normalized.append(value)
                elif isinstance(servers["mcpServers"], list):
                    for server in servers["mcpServers"]:
                        if isinstance(server, dict):
                            normalized.append(server)
            else:
                normalized.append(servers)  # single server?
        return normalized

    def __init__(self, servers_list: List[Dict[str, Any]]):
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
                # check if server is connected
                connected = True  # tool_count > 0
                # get error message if any
                error = server.get_error()
                # get log bool
                has_log = server.get_log() != ""

                # add server status to result
                result.append(
                    {
                        "name": name,
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
                        tools = server.get_tools()
                    except Exception:
                        tools = []
                    return {
                        "name": server.name,
                        "description": server.description,
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

    def get_tools_prompt(self, server_name: str = "") -> str:
        """Get a prompt for all tools"""

        # just to wait for pending initialization
        with self.__lock:
            pass

        prompt = '## "Remote (MCP Server) Agent Tools" available:\n\n'
        server_names = []
        for server in self.servers:
            if not server_name or server.name == server_name:
                server_names.append(server.name)

        if server_name and server_name not in server_names:
            raise ValueError(f"Server {server_name} not found")

        for server in self.servers:
            if server.name in server_names:
                server_name = server.name
                prompt += f"### {server_name}\n"
                prompt += f"{server.description}\n"
                tools = server.get_tools()

                for tool in tools:
                    prompt += (
                        f"\n### {server_name}.{tool['name']}:\n"
                        f"{tool['description']}\n\n"
                        # f"#### Categories:\n"
                        # f"* kind: MCP Server Tool\n"
                        # f'* server: "{server_name}" ({server.description})\n\n'
                        # f"#### Arguments:\n"
                    )

                    input_schema = (
                        json.dumps(tool["input_schema"]) if tool["input_schema"] else ""
                    )

                    prompt += f"#### Input schema for tool_args:\n{input_schema}\n"

                    prompt += "\n"

                    prompt += (
                        f"#### Usage:\n"
                        f"{{\n"
                        # f'    "observations": ["..."],\n' # TODO: this should be a prompt file with placeholders
                        f'    "thoughts": ["..."],\n'
                        # f'    "reflection": ["..."],\n' # TODO: this should be a prompt file with placeholders
                        f"    \"tool_name\": \"{server_name}.{tool['name']}\",\n"
                        f'    "tool_args": !follow schema above\n'
                        f"}}\n"
                    )

        return prompt

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        if "." not in tool_name:
            return False
        server_name_part, tool_name_part = tool_name.split(".")
        with self.__lock:
            for server in self.servers:
                if server.name == server_name_part:
                    return server.has_tool(tool_name_part)
            return False

    def get_tool(self, agent: Any, tool_name: str) -> MCPTool | None:
        if not self.has_tool(tool_name):
            return None
        return MCPTool(agent=agent, name=tool_name, method=None, args={}, message="", loop_data=None)

    async def call_tool(
        self, tool_name: str, input_data: Dict[str, Any]
    ) -> CallToolResult:
        """Call a tool with the given input data"""
        if "." not in tool_name:
            raise ValueError(f"Tool {tool_name} not found")
        server_name_part, tool_name_part = tool_name.split(".")
        with self.__lock:
            for server in self.servers:
                if server.name == server_name_part and server.has_tool(tool_name_part):
                    return await server.call_tool(tool_name_part, input_data)
            raise ValueError(f"Tool {tool_name} not found")


T = TypeVar("T")


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
    ) -> T:
        """
        Manages the lifecycle of an MCP session for a single operation.
        Creates a temporary session, executes coro_func with it, and ensures cleanup.
        """
        operation_name = coro_func.__name__  # For logging
        # PrintStyle(font_color="cyan").print(f"MCPClientBase ({self.server.name}): Creating new session for operation '{operation_name}'...")
        # Store the original exception outside the async block
        original_exception = None
        try:
            async with AsyncExitStack() as temp_stack:
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
                    await session.initialize()

                    result = await coro_func(session)

                    return result
                except Exception as e:
                    # Store the original exception and raise a dummy exception
                    excs = getattr(e, "exceptions", None)  # Python 3.11+ ExceptionGroup
                    if excs:
                        original_exception = excs[0]
                    else:
                        original_exception = e
                    # Create a dummy exception to break out of the async block
                    raise RuntimeError("Dummy exception to break out of async block")
        except Exception as e:
            # Check if this is our dummy exception
            if original_exception is not None:
                e = original_exception
            # We have the original exception stored
            PrintStyle(
                background_color="#AA4455", font_color="white", padding=False
            ).print(
                f"MCPClientBase ({self.server.name} - {operation_name}): Error during operation: {type(e).__name__}: {e}"
            )
            raise e  # Re-raise the original exception
        # finally:
        #     PrintStyle(font_color="cyan").print(
        #         f"MCPClientBase ({self.server.name} - {operation_name}): Session and transport will be closed by AsyncExitStack."
        #     )
        # This line should ideally be unreachable if the try/except/finally logic within the 'async with' is exhaustive.
        # Adding it to satisfy linters that might not fully trace the raise/return paths through async context managers.
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
            PrintStyle(font_color="green").print(
                f"MCPClientBase ({self.server.name}): Tools updated. Found {len(self.tools)} tools."
            )

        try:
            set = settings.get_settings()
            await self._execute_with_session(
                list_tools_op,
                read_timeout_seconds=self.server.init_timeout
                or set["mcp_client_init_timeout"],
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
            return self.tools

    async def call_tool(
        self, tool_name: str, input_data: Dict[str, Any]
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

        async def call_tool_op(current_session: ClientSession):
            set = settings.get_settings()
            # PrintStyle(font_color="cyan").print(f"MCPClientBase ({self.server.name}): Executing 'call_tool' for '{tool_name}' via MCP session...")
            response: CallToolResult = await current_session.call_tool(
                tool_name,
                input_data,
                read_timeout_seconds=timedelta(seconds=set["mcp_client_tool_timeout"]),
            )
            # PrintStyle(font_color="green").print(f"MCPClientBase ({self.server.name}): Tool '{tool_name}' call successful via session.")
            return response

        try:
            return await self._execute_with_session(call_tool_op)
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
            env=server.env,
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
        set = settings.get_settings()

        # Use lower timeouts for faster failure detection
        init_timeout = min(server.init_timeout or set["mcp_client_init_timeout"], 5)
        tool_timeout = min(server.tool_timeout or set["mcp_client_tool_timeout"], 10)

        # Check if this is a streaming HTTP type
        if _is_streaming_http_type(server.type):
            # Use streamable HTTP client
            transport_result = await current_exit_stack.enter_async_context(
                streamablehttp_client(
                    url=server.url,
                    headers=server.headers,
                    timeout=timedelta(seconds=init_timeout),
                    sse_read_timeout=timedelta(seconds=tool_timeout),
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
                )
            )
            return stdio_transport

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID if available (for streaming HTTP clients)."""
        if self.session_id_callback is not None:
            return self.session_id_callback()
        return None
