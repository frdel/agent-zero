# noqa: D401 (docstrings) – internal helper
import asyncio
import uuid
import atexit
from typing import Any, List
import contextlib
import threading

from python.helpers import settings
from starlette.requests import Request

# Local imports
from python.helpers.print_style import PrintStyle
from agent import AgentContext, UserMessage, AgentContextType
from initialize import initialize_agent
from python.helpers.persist_chat import remove_chat

# Import FastA2A
try:
    from fasta2a import Worker, FastA2A  # type: ignore
    from fasta2a.broker import InMemoryBroker  # type: ignore
    from fasta2a.storage import InMemoryStorage  # type: ignore
    from fasta2a.schema import Message, Artifact, AgentProvider, Skill  # type: ignore
    FASTA2A_AVAILABLE = True
except ImportError:  # pragma: no cover – library not installed
    FASTA2A_AVAILABLE = False
    # Minimal stubs for type checkers when FastA2A is not available

    class Worker:  # type: ignore
        def __init__(self, **kwargs):
            pass

        async def run_task(self, params):
            pass

        async def cancel_task(self, params):
            pass

        def build_message_history(self, history):
            return []

        def build_artifacts(self, result):
            return []

    class FastA2A:  # type: ignore
        def __init__(self, **kwargs):
            pass

        async def __call__(self, scope, receive, send):
            pass

    class InMemoryBroker:  # type: ignore
        pass

    class InMemoryStorage:  # type: ignore
        async def update_task(self, **kwargs):
            pass

    Message = Artifact = AgentProvider = Skill = Any  # type: ignore

_PRINTER = PrintStyle(italic=True, font_color="purple", padding=False)


class AgentZeroWorker(Worker):  # type: ignore[misc]
    """Agent Zero implementation of FastA2A Worker."""

    def __init__(self, broker, storage):
        super().__init__(broker=broker, storage=storage)
        self.storage = storage

    async def run_task(self, params: Any) -> None:  # params: TaskSendParams
        """Execute a task by processing the message through Agent Zero."""
        context = None
        try:
            task_id = params['id']
            message = params['message']

            _PRINTER.print(f"[A2A] Processing task {task_id} with new temporary context")

            # Convert A2A message to Agent Zero format
            agent_message = self._convert_message(message)

            # Always create new temporary context for this A2A conversation
            cfg = initialize_agent()
            context = AgentContext(cfg, type=AgentContextType.BACKGROUND)

            # Log user message so it appears instantly in UI chat window
            context.log.log(
                type="user",  # type: ignore[arg-type]
                heading="Remote user message",
                content=agent_message.message,
                kvps={"from": "A2A"},
                temp=False,
            )

            # Process message through Agent Zero (includes response)
            task = context.communicate(agent_message)
            result_text = await task.result()

            # Build A2A message from result
            response_message: Message = {  # type: ignore
                'role': 'agent',
                'parts': [{'kind': 'text', 'text': str(result_text)}],
                'kind': 'message',
                'message_id': str(uuid.uuid4())
            }

            await self.storage.update_task(  # type: ignore[attr-defined]
                task_id=task_id,
                state='completed',
                new_messages=[response_message]
            )

            # Clean up context like non-persistent MCP chats
            context.reset()
            AgentContext.remove(context.id)
            remove_chat(context.id)

            _PRINTER.print(f"[A2A] Completed task {task_id} and cleaned up context")

        except Exception as e:
            _PRINTER.print(f"[A2A] Error processing task {params.get('id', 'unknown')}: {e}")
            await self.storage.update_task(
                task_id=params.get('id', 'unknown'),
                state='failed'
            )

            # Clean up context even on failure to prevent resource leaks
            if context:
                context.reset()
                AgentContext.remove(context.id)
                remove_chat(context.id)
                _PRINTER.print(f"[A2A] Cleaned up failed context {context.id}")

    async def cancel_task(self, params: Any) -> None:  # params: TaskIdParams
        """Cancel a running task."""
        task_id = params['id']
        _PRINTER.print(f"[A2A] Cancelling task {task_id}")
        await self.storage.update_task(task_id=task_id, state='canceled')  # type: ignore[attr-defined]

        # Note: No context cleanup needed since contexts are always temporary and cleaned up in run_task

    def build_message_history(self, history: List[Any]) -> List[Message]:  # type: ignore
        # Not used in this simplified implementation
        return []

    def build_artifacts(self, result: Any) -> List[Artifact]:  # type: ignore
        # No artifacts for now
        return []

    def _convert_message(self, a2a_message: Message) -> UserMessage:  # type: ignore
        """Convert A2A message to Agent Zero UserMessage."""
        # Extract text from message parts
        text_parts = [part.get('text', '') for part in a2a_message.get('parts', []) if part.get('kind') == 'text']
        message_text = '\n'.join(text_parts)

        # Extract file attachments
        attachments = []
        for part in a2a_message.get('parts', []):
            if part.get('kind') == 'file':
                file_info = part.get('file', {})
                if 'uri' in file_info:
                    attachments.append(file_info['uri'])

        return UserMessage(
            message=message_text,
            attachments=attachments
        )


class DynamicA2AProxy:
    """Dynamic proxy for FastA2A server that allows reconfiguration."""

    _instance = None

    def __init__(self):
        self.app = None
        self.token = ""
        self._lock = threading.Lock()  # Use threading.Lock instead of asyncio.Lock
        self._startup_done: bool = False
        self._worker_bg_task: asyncio.Task | None = None
        self._reconfigure_needed: bool = False  # Flag for deferred reconfiguration

        if FASTA2A_AVAILABLE:
            # Initialize with default token
            cfg = settings.get_settings()
            self.token = cfg.get("mcp_server_token", "")
            self._configure()
            self._register_shutdown()
        else:
            _PRINTER.print("[A2A] FastA2A not available, server will return 503")

    @staticmethod
    def get_instance():
        if DynamicA2AProxy._instance is None:
            DynamicA2AProxy._instance = DynamicA2AProxy()
        return DynamicA2AProxy._instance

    def reconfigure(self, token: str):
        """Reconfigure the FastA2A server with new token."""
        self.token = token
        if FASTA2A_AVAILABLE:
            with self._lock:
                # Mark that reconfiguration is needed - will be done on next request
                self._reconfigure_needed = True
                self._startup_done = False  # Force restart on next request
                _PRINTER.print("[A2A] Reconfiguration scheduled for next request")

    def _configure(self):
        """Configure the FastA2A application with Agent Zero integration."""
        try:
            storage = InMemoryStorage()  # type: ignore[arg-type]
            broker = InMemoryBroker()  # type: ignore[arg-type]

            # Define Agent Zero's skills
            skills: List[Skill] = [{  # type: ignore
                "id": "general_assistance",
                "name": "General AI Assistant",
                "description": "Provides general AI assistance including code execution, file management, web browsing, and problem solving",
                "tags": ["ai", "assistant", "code", "files", "web", "automation"],
                "examples": [
                    "Write and execute Python code",
                    "Manage files and directories",
                    "Browse the web and extract information",
                    "Solve complex problems step by step",
                    "Install software and manage systems"
                ],
                "input_modes": ["text/plain", "application/octet-stream"],
                "output_modes": ["text/plain", "application/json"]
            }]

            provider: AgentProvider = {  # type: ignore
                "organization": "Agent Zero",
                "url": "https://github.com/frdel/agent-zero"
            }

            # Create new FastA2A app with proper thread safety
            new_app = FastA2A(  # type: ignore
                storage=storage,
                broker=broker,
                name="Agent Zero",
                description=(
                    "A general AI assistant that can execute code, manage files, browse the web, and "
                    "solve complex problems in an isolated Linux environment."
                ),
                version="1.0.0",
                provider=provider,
                skills=skills,
                lifespan=None,  # We manage lifespan manually
                middleware=[],  # No middleware - we handle auth in wrapper
            )

            # Store for later lazy startup (needs active event-loop)
            self._storage = storage  # type: ignore[attr-defined]
            self._broker = broker  # type: ignore[attr-defined]
            self._worker = AgentZeroWorker(broker=broker, storage=storage)  # type: ignore[attr-defined]

            # Atomic update of the app
            self.app = new_app

            _PRINTER.print("[A2A] FastA2A server configured successfully")

        except Exception as e:
            _PRINTER.print(f"[A2A] Failed to configure FastA2A server: {e}")
            self.app = None
            raise

    # ---------------------------------------------------------------------
    # Shutdown handling
    # ---------------------------------------------------------------------

    def _register_shutdown(self):
        """Register an atexit hook to gracefully stop worker & task manager."""

        def _sync_shutdown():
            try:
                if not self._startup_done or not FASTA2A_AVAILABLE:
                    return
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._async_shutdown())
                loop.close()
            except Exception:
                pass  # ignore errors during interpreter shutdown

        atexit.register(_sync_shutdown)

    async def _async_shutdown(self):
        """Async shutdown: cancel worker task & close task manager."""
        if self._worker_bg_task and not self._worker_bg_task.done():
            self._worker_bg_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_bg_task
        try:
            if hasattr(self, 'app') and self.app:
                await self.app.task_manager.__aexit__(None, None, None)  # type: ignore[attr-defined]
        except Exception:
            pass

    async def _async_reconfigure(self):
        """Perform async reconfiguration with proper lifecycle management."""
        _PRINTER.print("[A2A] Starting async reconfiguration")

        # Shutdown existing components
        await self._async_shutdown()

        # Reset startup state
        self._startup_done = False
        self._worker_bg_task = None

        # Reconfigure with new token
        self._configure()

        # Restart components
        await self._startup()

        # Clear reconfiguration flag
        self._reconfigure_needed = False

        _PRINTER.print("[A2A] Async reconfiguration completed")

    async def _startup(self):
        """Ensure TaskManager and Worker are running inside current event-loop."""
        if self._startup_done or not FASTA2A_AVAILABLE:
            return
        self._startup_done = True

        # Start task manager
        await self.app.task_manager.__aenter__()  # type: ignore[attr-defined]

        async def _worker_loop():
            async with self._worker.run():  # type: ignore[attr-defined]
                await asyncio.Event().wait()

        # fire-and-forget background task – keep reference
        self._worker_bg_task = asyncio.create_task(_worker_loop())
        _PRINTER.print("[A2A] Worker & TaskManager started")

    async def __call__(self, scope, receive, send):
        """ASGI application interface with token-based routing."""
        if not FASTA2A_AVAILABLE:
            # FastA2A not available, return 503
            response = b'HTTP/1.1 503 Service Unavailable\r\n\r\nFastA2A not available'
            await send({
                'type': 'http.response.start',
                'status': 503,
                'headers': [[b'content-type', b'text/plain']],
            })
            await send({
                'type': 'http.response.body',
                'body': response,
            })
            return

        from python.helpers import settings
        cfg = settings.get_settings()
        if not cfg["a2a_server_enabled"]:
            response = b'HTTP/1.1 403 Forbidden\r\n\r\nA2A server is disabled'
            await send({
                'type': 'http.response.start',
                'status': 403,
                'headers': [[b'content-type', b'text/plain']],
            })
            await send({
                'type': 'http.response.body',
                'body': response,
            })
            return

        # Check if reconfiguration is needed
        if self._reconfigure_needed:
            try:
                await self._async_reconfigure()
            except Exception as e:
                _PRINTER.print(f"[A2A] Error during reconfiguration: {e}")
                # Return 503 if reconfiguration failed
                await send({
                    'type': 'http.response.start',
                    'status': 503,
                    'headers': [[b'content-type', b'text/plain']],
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'FastA2A reconfiguration failed',
                })
                return

        if self.app is None:
            # FastA2A not configured, return 503
            response = b'HTTP/1.1 503 Service Unavailable\r\n\r\nFastA2A not configured'
            await send({
                'type': 'http.response.start',
                'status': 503,
                'headers': [[b'content-type', b'text/plain']],
            })
            await send({
                'type': 'http.response.body',
                'body': response,
            })
            return

        # Lazy-start background components the first time we get a request
        if not self._startup_done:
            try:
                _PRINTER.print("[A2A] Starting up FastA2A components")
                await self._startup()
            except Exception as e:
                _PRINTER.print(f"[A2A] Error during startup: {e}")
                # Return 503 if startup failed
                await send({
                    'type': 'http.response.start',
                    'status': 503,
                    'headers': [[b'content-type', b'text/plain']],
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'FastA2A startup failed',
                })
                return

        # Handle token-based routing: /a2a/t-{token}/... or /t-{token}/...
        path = scope.get('path', '')

        # Strip /a2a prefix if present (DispatcherMiddleware doesn't always strip it)
        if path.startswith('/a2a'):
            path = path[4:]  # Remove '/a2a' prefix

        # Check if path matches token pattern /t-{token}/
        if path.startswith('/t-'):
            # Extract token from path
            if '/' in path[3:]:
                path_parts = path[3:].split('/', 1)  # Remove '/t-' prefix
                request_token = path_parts[0]
                remaining_path = '/' + path_parts[1] if len(path_parts) > 1 else '/'
            else:
                request_token = path[3:]
                remaining_path = '/'

            # Validate token
            cfg = settings.get_settings()
            expected_token = cfg.get("mcp_server_token")

            if expected_token and request_token != expected_token:
                # Invalid token, return 401
                await send({
                    'type': 'http.response.start',
                    'status': 401,
                    'headers': [[b'content-type', b'text/plain']],
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'Unauthorized',
                })
                return

            # Update scope with cleaned path
            scope = dict(scope)
            scope['path'] = remaining_path
        else:
            # No token in path, check other auth methods
            request = Request(scope, receive=receive)

            cfg = settings.get_settings()
            expected = cfg.get("mcp_server_token")

            if expected:
                auth_header = request.headers.get("Authorization", "")
                api_key = request.headers.get("X-API-KEY") or request.query_params.get("api_key")

                is_authorized = (
                    (auth_header.startswith("Bearer ") and auth_header.split(" ", 1)[1] == expected) or
                    (api_key == expected)
                )

                if not is_authorized:
                    # No valid auth, return 401
                    await send({
                        'type': 'http.response.start',
                        'status': 401,
                        'headers': [[b'content-type', b'text/plain']],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': b'Unauthorized',
                    })
                    return
            else:
                _PRINTER.print("[A2A] No expected token found in settings")

        # Delegate to FastA2A app with cleaned scope
        with self._lock:
            app = self.app
        if app:
            await app(scope, receive, send)
        else:
            # App not configured, return 503
            await send({
                'type': 'http.response.start',
                'status': 503,
                'headers': [[b'content-type', b'text/plain']],
            })
            await send({
                'type': 'http.response.body',
                'body': b'FastA2A app not configured',
            })
            return


def is_available():
    """Check if FastA2A is available and properly configured."""
    return FASTA2A_AVAILABLE and DynamicA2AProxy.get_instance().app is not None


def get_proxy():
    """Get the FastA2A proxy instance."""
    return DynamicA2AProxy.get_instance()
