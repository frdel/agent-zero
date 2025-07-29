# noqa: D401 (docstrings) – internal helper
import asyncio
import uuid
import atexit
from typing import Any, List
import contextlib

from python.helpers import settings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.middleware import Middleware

# Local imports
from python.helpers.print_style import PrintStyle
from agent import AgentContext, UserMessage
from initialize import initialize_agent

# Attempt to import FastA2A – fall back to stubs so linters stay quiet
try:
    from fasta2a import Worker  # type: ignore
    from fasta2a.broker import InMemoryBroker  # type: ignore
    from fasta2a.storage import InMemoryStorage  # type: ignore
    from fasta2a.schema import Message, Artifact, AgentProvider, Skill  # type: ignore

    FASTA2A_AVAILABLE = True
except ImportError:  # pragma: no cover – library not installed
    FASTA2A_AVAILABLE = False

    class Worker:  # type: ignore
        """Stub so type-checkers don’t complain when FastA2A is absent."""

        pass

    # Minimal stubs for type checkers
    Message = Artifact = AgentProvider = Skill = Any  # type: ignore
    InMemoryBroker = InMemoryStorage = object  # type: ignore

_PRINTER = PrintStyle(italic=True, font_color="purple", padding=False)

if FASTA2A_AVAILABLE:
    class AgentZeroWorker(Worker):  # type: ignore[misc]
        """Agent Zero implementation of FastA2A Worker."""

        async def run_task(self, params: Any) -> None:  # params: TaskSendParams
            """Execute a task by processing the message through Agent Zero."""
            try:
                task_id = params['id']
                context_id = params['context_id']
                message = params['message']

                _PRINTER.print(f"[A2A] Processing task {task_id} in context {context_id}")

                # Convert A2A message to Agent Zero format
                agent_message = self._convert_message(message)

                # Get or create Agent Zero context
                context = AgentContext.get(context_id)
                if not context:
                    # Create new context for this A2A conversation
                    cfg = initialize_agent()
                    context = AgentContext(cfg, id=context_id)

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

                _PRINTER.print(f"[A2A] Completed task {task_id}")

            except Exception as e:
                _PRINTER.print(f"[A2A] Error processing task {params.get('id', 'unknown')}: {e}")
                await self.storage.update_task(
                    task_id=params.get('id', 'unknown'),
                    state='failed'
                )

        async def cancel_task(self, params: Any) -> None:  # params: TaskIdParams
            """Cancel a running task."""
            task_id = params['id']
            _PRINTER.print(f"[A2A] Cancelling task {task_id}")
            await self.storage.update_task(task_id=task_id, state='canceled')  # type: ignore[attr-defined]

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
        self._async_lock = asyncio.Lock()
        self._startup_done: bool = False
        self._worker_bg_task: asyncio.Task | None = None

        if FASTA2A_AVAILABLE:
            self._configure()
            self._register_shutdown()

    @staticmethod
    def get_instance():
        if DynamicA2AProxy._instance is None:
            DynamicA2AProxy._instance = DynamicA2AProxy()
        return DynamicA2AProxy._instance

    def _configure(self):
        """Configure the FastA2A application with Agent Zero integration."""
        try:
            # Import inside the method to handle missing dependencies gracefully
            from fasta2a import FastA2A  # type: ignore
            from fasta2a.broker import InMemoryBroker  # type: ignore
            from fasta2a.storage import InMemoryStorage  # type: ignore

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

            # Authentication middleware (Bearer or X-API-KEY)
            class A2AAuthMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request: Request, call_next):  # type: ignore[override]
                    cfg = settings.get_settings()
                    expected = cfg.get("a2a_token") or cfg.get("mcp_server_token")
                    if not expected:
                        return await call_next(request)  # no auth configured

                    auth_header = request.headers.get("Authorization", "")
                    if auth_header.startswith("Bearer ") and auth_header.split(" ", 1)[1] == expected:
                        return await call_next(request)

                    api_key = request.headers.get("X-API-KEY") or request.query_params.get("api_key")
                    if api_key == expected:
                        return await call_next(request)

                    # Fallback: check token in mount path (root_path contains the prefix stripped by DispatcherMiddleware)
                    root_path = request.scope.get("root_path", "")  # type: ignore[attr-defined]
                    if root_path and f"/t-{expected}" in root_path:
                        return await call_next(request)

                    return PlainTextResponse("Unauthorized", 401)

            middleware_list = [Middleware(A2AAuthMiddleware)]

            self.app = FastA2A(  # type: ignore
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
                middleware=middleware_list,
            )

            # Store for later lazy startup (needs active event-loop)
            self._storage = storage  # type: ignore[attr-defined]
            self._broker = broker  # type: ignore[attr-defined]
            self._worker = AgentZeroWorker(broker=broker, storage=storage)  # type: ignore[attr-defined]

            _PRINTER.print("[A2A] FastA2A server configured successfully")

        except Exception as e:
            _PRINTER.print(f"[A2A] Failed to configure FastA2A server: {e}")
            self.app = None

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
            await self.app.task_manager.__aexit__(None, None, None)  # type: ignore[attr-defined]
        except Exception:
            pass

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

    async def reconfigure(self):
        """Reconfigure the FastA2A server (placeholder for future use)."""
        async with self._async_lock:
            if FASTA2A_AVAILABLE:
                self._configure()

    async def __call__(self, scope, receive, send):
        """ASGI application interface."""
        if self.app is None:
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

        # Lazy-start background components the first time we get a request
        if FASTA2A_AVAILABLE and not self._startup_done:
            await self._startup()

        # Delegate to FastA2A app
        await self.app(scope, receive, send)


def is_available():
    """Check if FastA2A is available and properly configured."""
    return FASTA2A_AVAILABLE and DynamicA2AProxy.get_instance().app is not None


def get_proxy():
    """Get the FastA2A proxy instance."""
    if not FASTA2A_AVAILABLE:
        return None
    return DynamicA2AProxy.get_instance()
