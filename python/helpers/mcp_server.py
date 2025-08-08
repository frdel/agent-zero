import os
from typing import Annotated, Literal, Union
from urllib.parse import urlparse
from openai import BaseModel
from pydantic import Field
from fastmcp import FastMCP

from agent import AgentContext, AgentContextType, UserMessage
from python.helpers.persist_chat import remove_chat
from initialize import initialize_agent
from python.helpers.print_style import PrintStyle
from python.helpers import settings
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Receive, Scope, Send
from fastmcp.server.http import create_sse_app
from starlette.requests import Request
import threading

_PRINTER = PrintStyle(italic=True, font_color="green", padding=False)


mcp_server: FastMCP = FastMCP(
    name="Agent Zero integrated MCP Server",
    instructions="""
    Connect to remote Agent Zero instance.
    Agent Zero is a general AI assistant controlling it's linux environment.
    Agent Zero can install software, manage files, execute commands, code, use internet, etc.
    Agent Zero's environment is isolated unless configured otherwise.
    """,
)


class ToolResponse(BaseModel):
    status: Literal["success"] = Field(
        description="The status of the response", default="success"
    )
    response: str = Field(
        description="The response from the remote Agent Zero Instance"
    )
    chat_id: str = Field(description="The id of the chat this message belongs to.")


class ToolError(BaseModel):
    status: Literal["error"] = Field(
        description="The status of the response", default="error"
    )
    error: str = Field(
        description="The error message from the remote Agent Zero Instance"
    )
    chat_id: str = Field(description="The id of the chat this message belongs to.")


SEND_MESSAGE_DESCRIPTION = """
Send a message to the remote Agent Zero Instance.
This tool is used to send a message to the remote Agent Zero Instance connected remotely via MCP.
"""


@mcp_server.tool(
    name="send_message",
    description=SEND_MESSAGE_DESCRIPTION,
    tags={
        "agent_zero",
        "chat",
        "remote",
        "communication",
        "dialogue",
        "sse",
        "send",
        "message",
        "start",
        "new",
        "continue",
    },
    annotations={
        "remote": True,
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
        "title": SEND_MESSAGE_DESCRIPTION,
    },
)
async def send_message(
    message: Annotated[
        str,
        Field(
            description="The message to send to the remote Agent Zero Instance",
            title="message",
        ),
    ],
    attachments: (
        Annotated[
            list[str],
            Field(
                description="Optional: A list of attachments (file paths or web urls) to send to the remote Agent Zero Instance with the message. Default: Empty list",
                title="attachments",
            ),
        ]
        | None
    ) = None,
    chat_id: (
        Annotated[
            str,
            Field(
                description="Optional: ID of the chat. Used to continue a chat. This value is returned in response to sending previous message. Default: Empty string",
                title="chat_id",
            ),
        ]
        | None
    ) = None,
    persistent_chat: (
        Annotated[
            bool,
            Field(
                description="Optional: Whether to use a persistent chat. If true, the chat will be saved and can be continued later. Default: False.",
                title="persistent_chat",
            ),
        ]
        | None
    ) = None,
) -> Annotated[
    Union[ToolResponse, ToolError],
    Field(
        description="The response from the remote Agent Zero Instance", title="response"
    ),
]:
    context: AgentContext | None = None
    if chat_id:
        context = AgentContext.get(chat_id)
        if not context:
            return ToolError(error="Chat not found", chat_id=chat_id)
        else:
            # If the chat is found, we use the persistent chat flag to determine
            # whether we should save the chat or delete it afterwards
            # If we continue a conversation, it must be persistent
            persistent_chat = True
    else:
        config = initialize_agent()
        context = AgentContext(config=config, type=AgentContextType.BACKGROUND)

    if not message:
        return ToolError(
            error="Message is required", chat_id=context.id if persistent_chat else ""
        )

    try:
        response = await _run_chat(context, message, attachments)
        if not persistent_chat:
            context.reset()
            AgentContext.remove(context.id)
            remove_chat(context.id)
        return ToolResponse(
            response=response, chat_id=context.id if persistent_chat else ""
        )
    except Exception as e:
        return ToolError(error=str(e), chat_id=context.id if persistent_chat else "")


FINISH_CHAT_DESCRIPTION = """
Finish a chat with the remote Agent Zero Instance.
This tool is used to finish a persistent chat (send_message with persistent_chat=True) with the remote Agent Zero Instance connected remotely via MCP.
If you want to continue the chat, use the send_message tool instead.
Always use this tool to finish persistent chat conversations with remote Agent Zero.
"""


@mcp_server.tool(
    name="finish_chat",
    description=FINISH_CHAT_DESCRIPTION,
    tags={
        "agent_zero",
        "chat",
        "remote",
        "communication",
        "dialogue",
        "sse",
        "finish",
        "close",
        "end",
        "stop",
    },
    annotations={
        "remote": True,
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
        "title": FINISH_CHAT_DESCRIPTION,
    },
)
async def finish_chat(
    chat_id: Annotated[
        str,
        Field(
            description="ID of the chat to be finished. This value is returned in response to sending previous message.",
            title="chat_id",
        ),
    ]
) -> Annotated[
    Union[ToolResponse, ToolError],
    Field(
        description="The response from the remote Agent Zero Instance", title="response"
    ),
]:
    if not chat_id:
        return ToolError(error="Chat ID is required", chat_id="")

    context = AgentContext.get(chat_id)
    if not context:
        return ToolError(error="Chat not found", chat_id=chat_id)
    else:
        context.reset()
        AgentContext.remove(context.id)
        remove_chat(context.id)
        return ToolResponse(response="Chat finished", chat_id=chat_id)


async def _run_chat(
    context: AgentContext, message: str, attachments: list[str] | None = None
):
    try:
        _PRINTER.print("MCP Chat message received")

        # Attachment filenames for logging
        attachment_filenames = []
        if attachments:
            for attachment in attachments:
                if os.path.exists(attachment):
                    attachment_filenames.append(attachment)
                else:
                    try:
                        url = urlparse(attachment)
                        if url.scheme in ["http", "https", "ftp", "ftps", "sftp"]:
                            attachment_filenames.append(attachment)
                        else:
                            _PRINTER.print(f"Skipping attachment: [{attachment}]")
                    except Exception:
                        _PRINTER.print(f"Skipping attachment: [{attachment}]")

        _PRINTER.print("User message:")
        _PRINTER.print(f"> {message}")
        if attachment_filenames:
            _PRINTER.print("Attachments:")
            for filename in attachment_filenames:
                _PRINTER.print(f"- {filename}")

        task = context.communicate(
            UserMessage(
                message=message, system_message=[], attachments=attachment_filenames
            )
        )
        result = await task.result()

        # Success
        _PRINTER.print(f"MCP Chat message completed: {result}")

        return result

    except Exception as e:
        # Error
        _PRINTER.print(f"MCP Chat message failed: {e}")

        raise RuntimeError(f"MCP Chat message failed: {e}") from e


class DynamicMcpProxy:
    _instance: "DynamicMcpProxy | None" = None

    """A dynamic proxy that allows swapping the underlying MCP applications on the fly."""

    def __init__(self):
        cfg = settings.get_settings()
        self.token = ""
        self.sse_app: ASGIApp | None = None
        self.http_app: ASGIApp | None = None
        self.http_session_manager = None
        self.http_session_task_group = None
        self._lock = threading.RLock()  # Use RLock to avoid deadlocks
        self.reconfigure(cfg["mcp_server_token"])

    @staticmethod
    def get_instance():
        if DynamicMcpProxy._instance is None:
            DynamicMcpProxy._instance = DynamicMcpProxy()
        return DynamicMcpProxy._instance

    def reconfigure(self, token: str):
        if self.token == token:
            return

        self.token = token
        sse_path = f"/t-{self.token}/sse"
        http_path = f"/t-{self.token}/http"
        message_path = f"/t-{self.token}/messages/"

        # Update settings in the MCP server instance if provided
        mcp_server.settings.message_path = message_path
        mcp_server.settings.sse_path = sse_path

        # Create new MCP apps with updated settings
        with self._lock:
            self.sse_app = create_sse_app(
                server=mcp_server,
                message_path=mcp_server.settings.message_path,
                sse_path=mcp_server.settings.sse_path,
                auth_server_provider=mcp_server._auth_server_provider,
                auth_settings=mcp_server.settings.auth,
                debug=mcp_server.settings.debug,
                routes=mcp_server._additional_http_routes,
                middleware=[Middleware(BaseHTTPMiddleware, dispatch=mcp_middleware)],
            )

            # For HTTP, we need to create a custom app since the lifespan manager
            # doesn't work properly in our Flask/Werkzeug environment
            self.http_app = self._create_custom_http_app(
                http_path,
                mcp_server._auth_server_provider,
                mcp_server.settings.auth,
                mcp_server.settings.debug,
                mcp_server._additional_http_routes,
            )

    def _create_custom_http_app(self, streamable_http_path, auth_server_provider, auth_settings, debug, routes):
        """Create a custom HTTP app that manages the session manager manually."""
        from fastmcp.server.http import setup_auth_middleware_and_routes, create_base_app
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from starlette.routing import Mount
        from mcp.server.auth.middleware.bearer_auth import RequireAuthMiddleware
        import anyio

        server_routes = []
        server_middleware = []

        self.http_session_task_group = None


        # Create session manager
        self.http_session_manager = StreamableHTTPSessionManager(
            app=mcp_server._mcp_server,
            event_store=None,
            json_response=True,
            stateless=False,
        )


        # Custom ASGI handler that ensures task group is initialized
        async def handle_streamable_http(scope, receive, send):
            # Lazy initialization of task group
            if self.http_session_task_group is None:
                self.http_session_task_group = anyio.create_task_group()
                await self.http_session_task_group.__aenter__()
                if self.http_session_manager:
                    self.http_session_manager._task_group = self.http_session_task_group

            if self.http_session_manager:
                await self.http_session_manager.handle_request(scope, receive, send)

        # Get auth middleware and routes
        auth_middleware, auth_routes, required_scopes = setup_auth_middleware_and_routes(
            auth_server_provider, auth_settings
        )

        server_routes.extend(auth_routes)
        server_middleware.extend(auth_middleware)

        # Add StreamableHTTP routes with or without auth
        if auth_server_provider:
            server_routes.append(
                Mount(
                    streamable_http_path,
                    app=RequireAuthMiddleware(handle_streamable_http, required_scopes),
                )
            )
        else:
            server_routes.append(
                Mount(
                    streamable_http_path,
                    app=handle_streamable_http,
                )
            )

        # Add custom routes with lowest precedence
        if routes:
            server_routes.extend(routes)

        # Add middleware
        server_middleware.append(Middleware(BaseHTTPMiddleware, dispatch=mcp_middleware))

        # Create and return the app
        return create_base_app(
            routes=server_routes,
            middleware=server_middleware,
            debug=debug,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Forward the ASGI calls to the appropriate app based on the URL path"""
        with self._lock:
            sse_app = self.sse_app
            http_app = self.http_app

        if not sse_app or not http_app:
            raise RuntimeError("MCP apps not initialized")

        # Route based on path
        path = scope.get("path", "")

        if f"/t-{self.token}/sse" in path or f"t-{self.token}/messages" in path:
            # Route to SSE app
            await sse_app(scope, receive, send)
        elif f"/t-{self.token}/http" in path:
            # Route to HTTP app
            await http_app(scope, receive, send)
        else:
            raise StarletteHTTPException(
                status_code=403, detail="MCP forbidden"
            )


async def mcp_middleware(request: Request, call_next):

    # check if MCP server is enabled
    cfg = settings.get_settings()
    if not cfg["mcp_server_enabled"]:
        PrintStyle.error("[MCP] Access denied: MCP server is disabled in settings.")
        raise StarletteHTTPException(
            status_code=403, detail="MCP server is disabled in settings."
        )

    return await call_next(request)
