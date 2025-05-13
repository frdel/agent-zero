from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Union, Literal, Annotated, ClassVar, cast
import threading
import asyncio
from contextlib import AsyncExitStack
from shutil import which
from datetime import timedelta

import os
print(f"DEBUG: Listing /opt/venv/lib/python3.11/site-packages/ before mcp import: {os.listdir('/opt/venv/lib/python3.11/site-packages/')}")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, ListToolsResult, JSONRPCMessage
from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)

from pydantic import BaseModel, Field, Discriminator, Tag, PrivateAttr
from python.helpers.dirty_json import DirtyJson
from python.helpers.print_style import PrintStyle
from python.helpers.tool import Tool, Response


class MCPTool(Tool):
    """MCP Tool wrapper"""
    async def execute(self, **kwargs: Any):
        error = ""
        try:
            response: CallToolResult = await MCPConfig.get_instance().call_tool(self.name, kwargs)
            message = "\n\n".join([item.text for item in response.content if item.type == "text"])
            if response.isError:
                error = message
        except Exception as e:
            error = f"MCP Tool Exception: {str(e)}"
            message = f"ERROR: {str(e)}"

        if error:
            PrintStyle(
                background_color="#CC34C3", font_color="white", bold=True, padding=True
            ).print(f"MCPTool::Failed to call mcp tool {self.name}:")
            PrintStyle(background_color="#AA4455", font_color="white", padding=False).print(error)

            self.agent.context.log.log(
                type="warning",
                content=f"{self.name}: {error}",
            )

        return Response(message=message, break_loop=False)

    async def before_execution(self, **kwargs: Any):
        (
            PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True)
            .print(f"{self.agent.agent_name}: Using tool '{self.name}'")
        )
        self.log = self.get_log_object()

        for key, value in self.args.items():
            PrintStyle(font_color="#85C1E9", bold=True).stream(self.nice_key(key) + ": ")
            PrintStyle(font_color="#85C1E9", padding=isinstance(value, str) and "\n" in value).stream(value)
            PrintStyle().print()

    async def after_execution(self, response: Response, **kwargs: Any):
        # Check if response or message is None
        if not response.message.strip():
            text = ""
            PrintStyle(font_color="red").print(f"Warning: Tool '{self.name}' returned None response or message")
        else:
            text = response.message.strip()

        self.agent.hist_add_tool_result(self.name, text)
        (
            PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True)
            .print(f"{self.agent.agent_name}: Response from tool '{self.name}'")
        )
        PrintStyle(font_color="#85C1E9").print(text)
        self.log.update(content=text)


class MCPServerRemote(BaseModel):
    name: str = Field(default_factory=str)
    description: Optional[str] = Field(default="Remote SSE Server")
    url: str = Field(default_factory=str)
    headers: dict[str, Any] | None = Field(default_factory=dict[str, Any])
    timeout: float = Field(default=5.0)
    sse_read_timeout: float = Field(default=60.0 * 5.0)
    disabled: bool = Field(default=False)

    __lock: ClassVar[threading.Lock] = PrivateAttr(default=threading.Lock())
    __client: Optional["MCPClientRemote"] = PrivateAttr(default=None)

    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.__client = MCPClientRemote(self)
        self.update(config)

    def get_tools(self) -> List[dict[str, Any]]:
        """Get all tools from the server"""
        with self.__lock:
            return self.__client.tools  # type: ignore

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        with self.__lock:
            return self.__client.has_tool(tool_name)  # type: ignore

    async def call_tool(self, tool_name: str, input_data: Dict[str, Any]) -> CallToolResult:
        """Call a tool with the given input data"""
        with self.__lock:
            # We already run in an event loop, dont believe Pylance
            return await self.__client.call_tool(tool_name, input_data)  # type: ignore

    def update(self, config: dict[str, Any]) -> "MCPServerRemote":
        with self.__lock:
            for key, value in config.items():
                if key in ["name", "description", "url", "headers", "timeout", "sse_read_timeout", "disabled"]:
                    if key == "name":
                        value = value.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
                    setattr(self, key, value)
            # We already run in an event loop, dont believe Pylance
            return asyncio.run(self.__on_update())

    async def __on_update(self) -> "MCPServerRemote":
        await self.__client.update_tools()  # type: ignore
        return self


class MCPServerLocal(BaseModel):
    name: str = Field(default_factory=str)
    description: Optional[str] = Field(default="Local StdIO Server")
    command: str = Field(default_factory=str)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = Field(default_factory=dict[str, str])
    encoding: str = Field(default="utf-8")
    encoding_error_handler: Literal["strict", "ignore", "replace"] = Field(default="strict")
    disabled: bool = Field(default=False)

    __lock: ClassVar[threading.Lock] = PrivateAttr(default=threading.Lock())
    __client: Optional["MCPClientLocal"] = PrivateAttr(default=None)

    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.__client = MCPClientLocal(self)
        self.update(config)

    def get_tools(self) -> List[dict[str, Any]]:
        """Get all tools from the server"""
        with self.__lock:
            return self.__client.tools  # type: ignore

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        with self.__lock:
            return self.__client.has_tool(tool_name)  # type: ignore

    async def call_tool(self, tool_name: str, input_data: Dict[str, Any]) -> CallToolResult:
        """Call a tool with the given input data"""
        with self.__lock:
            # We already run in an event loop, dont believe Pylance
            return await self.__client.call_tool(tool_name, input_data)  # type: ignore

    def update(self, config: dict[str, Any]) -> "MCPServerLocal":
        with self.__lock:
            for key, value in config.items():
                if key in ["name", "description", "command", "args", "env", "encoding", "encoding_error_handler", "disabled"]:
                    if key == "name":
                        value = value.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
                    setattr(self, key, value)
            # We already run in an event loop, dont believe Pylance
            return asyncio.run(self.__on_update())

    async def __on_update(self) -> "MCPServerLocal":
        await self.__client.update_tools()  # type: ignore
        return self


MCPServer = Annotated[
    Union[
        Annotated[MCPServerRemote, Tag('MCPServerRemote')],
        Annotated[MCPServerLocal, Tag('MCPServerLocal')]
    ],
    Discriminator(lambda v: "MCPServerRemote" if "url" in v else "MCPServerLocal")
]


class MCPConfig(BaseModel):
    servers: List[MCPServer] = Field(default_factory=list[MCPServer])

    __lock: ClassVar[threading.Lock] = PrivateAttr(default=threading.Lock())

    # Singleton instance
    __instance: ClassVar[Any] = PrivateAttr(default=None)
    __initialized: ClassVar[bool] = PrivateAttr(default=False)

    @classmethod
    def get_instance(cls) -> "MCPConfig":
        if cls.__instance is None:
            cls.__instance = cls(servers_list=[])
        return cls.__instance

    @classmethod
    def update(cls, config_str: str) -> Any:
        """Parse the MCP config string into a MCPConfig object."""
        with cls.__lock:
            try:
                servers = DirtyJson.parse_string(config_str)
            except Exception as e:
                raise ValueError(f"Failed to parse MCP config: {e}") from e
            cls.get_instance().__init__(servers_list=servers)
            cls.__initialized = True
            return cls.get_instance()

    def __init__(self, servers_list: List[Dict[str, Any]]):
        from collections.abc import Mapping, Iterable

        # This empties the servers list
        super().__init__()

        if not isinstance(servers_list, Iterable):
            (
                PrintStyle(background_color="grey", font_color="red", padding=True)
                .print("MCPConfig::__init__::servers_list must be a list")
            )
            return

        for server_item in servers_list:
            if not isinstance(server_item, Mapping):
                (
                    PrintStyle(background_color="grey", font_color="red", padding=True)
                    .print("MCPConfig::__init__::server_item must be a mapping")
                )
                continue

            if server_item.get("disabled", False):
                continue

            server_name = server_item.get("name", "__not__found__")
            if server_name == "__not__found__":
                (
                    PrintStyle(background_color="grey", font_color="red", padding=True)
                    .print("MCPConfig::__init__::server_name is required")
                )
                continue

            try:
                # not generic MCPServer because: "Annotated can not be instatioated"
                if server_item.get("url", None):
                    self.servers.append(MCPServerRemote(server_item))
                else:
                    self.servers.append(MCPServerLocal(server_item))
            except Exception as e:
                (
                    PrintStyle(background_color="grey", font_color="red", padding=True)
                    .print(f"MCPConfig::__init__: Failedto create MCPServer '{server_name}': {e}")
                )
                continue

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
                for tool in server.get_tools():
                    prompt += (
                        f"### {server_name}.{tool['name']}:\n"
                        f"{tool['description']}\n\n"
                        f"#### Categories:\n"
                        f"* kind: MCP Server Tool\n"
                        f'* server: "{server_name}" ({server.description})\n\n'
                        f"#### Arguments:\n"
                    )

                    tool_args = ""
                    properties: dict[str, Any] = tool["input_schema"]["properties"]
                    for key, value in properties.items():
                        tool_args += f"            \"{key}\": \"...\",\n"
                        examples = ""
                        description = ""
                        if "examples" in value:
                            examples = f"(examples: {value['examples']})"
                        if "description" in value:
                            description = f": {value['description']}"
                        prompt += (
                            f" * {key} ({value['type']}){description} {examples}\n"
                        )
                    prompt += "\n"

                    prompt += (
                        f"#### Usage:\n"
                        f"~~~json\n"
                        f"{{\n"
                        f"    \"observations\": [\"...\"],\n"
                        f"    \"thoughts\": [\"...\"],\n"
                        f"    \"reflection\": [\"...\"],\n"
                        f"    \"tool_name\": \"{server_name}.{tool['name']}\",\n"
                        f"    \"tool_args\": {{\n"
                        f"{tool_args}"
                        f"    }}\n"
                        f"}}\n"
                        f"~~~\n"
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
        return MCPTool(agent, tool_name, {}, "", **{})

    async def call_tool(self, tool_name: str, input_data: Dict[str, Any]) -> CallToolResult:
        """Call a tool with the given input data"""
        if "." not in tool_name:
            raise ValueError(f"Tool {tool_name} not found")
        server_name_part, tool_name_part = tool_name.split(".")
        with self.__lock:
            for server in self.servers:
                if server.name == server_name_part and server.has_tool(tool_name_part):
                    return await server.call_tool(tool_name_part, input_data)
            raise ValueError(f"Tool {tool_name} not found")


class MCPClientBase(ABC):
    session: Optional[ClientSession] = None
    exit_stack: AsyncExitStack = AsyncExitStack()
    stdio: Optional[MemoryObjectReceiveStream[JSONRPCMessage | Exception]] = None
    write: Optional[MemoryObjectSendStream[JSONRPCMessage]] = None

    tools: List[dict[str, Any]] = []
    server: Optional[Union[MCPServerLocal, MCPServerRemote]] = None

    __lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, server: Union[MCPServerLocal, MCPServerRemote]):
        self.server = server

    # Protected method
    @abstractmethod
    async def _connect_client(self) -> tuple[MemoryObjectReceiveStream[JSONRPCMessage | Exception], MemoryObjectSendStream[JSONRPCMessage]]:
        """Connect to an MCP server, init client and save stdio/write streams"""
        ...

    async def __connect_to_server(self) -> Any:
        """Connect to an MCP server"""
        with self.__lock:
            self.stdio, self.write = await self._connect_client()

            self.session = (
                await self.exit_stack.enter_async_context(
                    ClientSession(
                        self.stdio,
                        self.write,
                        read_timeout_seconds=timedelta(seconds=15)
                    )
                )
            )

            # Initialize session
            await self.session.initialize()
            return self

    async def update_tools(self) -> Any:
        """List available tools from the server"""
        try:
            await self.__connect_to_server()
            with self.__lock:
                response: ListToolsResult = await self.session.list_tools()
                available_tools = [{
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                } for tool in response.tools]

                self.tools = available_tools
                await self.exit_stack.aclose()
                return self
        except Exception as e:
            PrintStyle(
                background_color="#CC34C3", font_color="white", bold=True, padding=True
            ).print("MCPClientLocal::Failed to update tools:")
            PrintStyle(background_color="#AA4455", font_color="white", padding=False).print(str(e))

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        with self.__lock:
            for tool in self.tools:
                if tool["name"] == tool_name:
                    return True
        return False

    def get_tools(self) -> List[dict[str, Any]]:
        """Get all tools from the server"""
        with self.__lock:
            return self.tools

    async def call_tool(self, tool_name: str, input_data: Dict[str, Any]) -> CallToolResult:
        """Call a tool with the given input data"""
        if not self.has_tool(tool_name):
            await self.update_tools()

        await self.__connect_to_server()

        with self.__lock:
            for tool in self.tools:
                if tool["name"] == tool_name:
                    response: CallToolResult = await self.session.call_tool(tool_name, input_data)
                    # after connect have to close the stack within this function
                    await self.exit_stack.aclose()
                    return response
            raise ValueError(f"Tool {tool_name} not found")


class MCPClientLocal(MCPClientBase):
    async def _connect_client(self) -> tuple[MemoryObjectReceiveStream[JSONRPCMessage | Exception], MemoryObjectSendStream[JSONRPCMessage]]:
        """Connect to an MCP server, init client and save stdio/write streams"""
        server: MCPServerLocal = cast(MCPServerLocal, self.server)

        if not which(server.command):
            raise ValueError(f"Command {server.command} not found")

        # which_args = 0
        # for arg in server.args:
        #     if which(arg):
        #         which_args = which_args + 1
        # if which_args == 0:
        #     raise ValueError(f"None of the arguments {server.args} is a file")

        server_params = StdioServerParameters(
            command=server.command,
            args=server.args,
            env=server.env,
            encoding=server.encoding,
            encoding_error_handler=server.encoding_error_handler
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        return stdio_transport


class MCPClientRemote(MCPClientBase):
    async def _connect_client(self) -> tuple[MemoryObjectReceiveStream[JSONRPCMessage | Exception], MemoryObjectSendStream[JSONRPCMessage]]:
        """Connect to an MCP server, init client and save stdio/write streams"""
        server: MCPServerRemote = cast(MCPServerRemote, self.server)
        stdio_transport = await self.exit_stack.enter_async_context(
            sse_client(url=server.url, headers=server.headers, timeout=server.timeout, sse_read_timeout=server.sse_read_timeout)
        )
        return stdio_transport
