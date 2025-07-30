import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, AsyncGenerator
from urllib.parse import urljoin

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse, Response
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.authentication import AuthenticationBackend, AuthCredentials, SimpleUser
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send
import uvicorn

from python.helpers.print_style import PrintStyle
from python.helpers.a2a_handler import A2AHandler, A2AError, A2AErrorType, TaskState, TaskArtifact


class A2AAuthBackend(AuthenticationBackend):
    """Authentication backend for A2A protocol"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.auth_required = config.get("auth_required", True)
        self.auth_schemes = config.get("auth_schemes", ["bearer"])
        self.api_keys = config.get("api_keys", {})
    
    async def authenticate(self, conn):
        """Authenticate incoming request"""
        if not self.auth_required:
            return AuthCredentials(["authenticated"]), SimpleUser("anonymous")
        
        auth_header = conn.headers.get("authorization", "")
        api_key_header = conn.headers.get("x-api-key", "")
        
        # Bearer token authentication
        if "bearer" in self.auth_schemes and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            if self._validate_bearer_token(token):
                return AuthCredentials(["authenticated"]), SimpleUser("bearer_user")
        
        # API Key authentication
        if "api_key" in self.auth_schemes and api_key_header:
            if self._validate_api_key(api_key_header):
                return AuthCredentials(["authenticated"]), SimpleUser("api_user")
        
        # Basic authentication
        if "basic" in self.auth_schemes and auth_header.startswith("Basic "):
            credentials = auth_header[6:]  # Remove "Basic " prefix
            if self._validate_basic_auth(credentials):
                return AuthCredentials(["authenticated"]), SimpleUser("basic_user")
        
        return None
    
    def _validate_bearer_token(self, token: str) -> bool:
        """Validate bearer token (implement your logic here)"""
        # In a real implementation, validate against your token store
        # For now, accept any non-empty token
        return len(token) > 0
    
    def _validate_api_key(self, api_key: str) -> bool:
        """Validate API key"""
        return api_key in self.api_keys
    
    def _validate_basic_auth(self, credentials: str) -> bool:
        """Validate basic auth credentials"""
        # Decode and validate basic auth (simplified)
        return len(credentials) > 0


class A2AServer:
    """
    A2A Protocol Server Implementation
    
    Provides HTTP endpoints for A2A protocol compliance:
    - POST /tasks/submit - Task submission
    - GET /tasks/{id} - Task status polling
    - GET /message/stream - Server-Sent Events stream
    - POST /push/{token} - Webhook endpoints
    - GET /.well-known/agent.json - Agent Card discovery
    """
    
    def __init__(self, config: Dict[str, Any], agent_context: Any):
        self.config = config
        self.agent_context = agent_context
        self.handler = A2AHandler.get_instance()
        self.app = None
        self.server = None
        
        # Initialize handler with config
        self.handler.initialize(config)
        
        # SSE client management
        self.sse_clients: Dict[str, Any] = {}
        self.sent_task_updates: Dict[str, set] = {}  # Track which tasks have been sent to which clients
        
    def create_app(self) -> Starlette:
        """Create and configure Starlette application"""
        
        # Middleware
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=self.config.get("cors_origins", ["*"]),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        ]
        
        # Add authentication middleware if required
        if self.config.get("auth_required", True):
            auth_backend = A2AAuthBackend(self.config)
            middleware.append(
                Middleware(AuthenticationMiddleware, backend=auth_backend)
            )
        
        # Routes
        routes = [
            # A2A Protocol endpoints
            Route("/.well-known/agent.json", self.get_agent_card, methods=["GET"]),
            Route("/tasks/submit", self.submit_task, methods=["POST"]),
            Route("/tasks/{task_id}", self.get_task_status, methods=["GET"]),
            Route("/tasks/{task_id}/cancel", self.cancel_task, methods=["POST"]),
            Route("/tasks/{task_id}/pushNotificationConfig/set", self.set_push_config, methods=["POST"]),
            Route("/message/stream", self.sse_stream, methods=["GET"]),
            Route("/push/{token}", self.webhook_handler, methods=["POST"]),
            
            # Health check
            Route("/health", self.health_check, methods=["GET"]),
            
            # Context info for subordinate registration
            Route("/context/info", self.get_context_info, methods=["GET"]),
            
            # Subordinate registry for peer discovery
            Route("/subordinates/registry", self.get_subordinate_registry, methods=["GET"]),
        ]
        
        app = Starlette(
            routes=routes,
            middleware=middleware,
            exception_handlers={
                HTTPException: self.http_exception_handler
            }
        )
        
        return app
    
    async def http_exception_handler(self, request: Request, exc: HTTPException):
        """Handle HTTP exceptions and format as A2A errors"""
        if exc.status_code == 404:
            error = A2AError(A2AErrorType.TASK_NOT_FOUND, "Resource not found")
        elif exc.status_code == 401:
            error = A2AError(A2AErrorType.UNSUPPORTED_OPERATION, "Authentication required")
        elif exc.status_code == 415:
            error = A2AError(A2AErrorType.CONTENT_TYPE_NOT_SUPPORTED, "Unsupported content type")
        else:
            error = A2AError(A2AErrorType.INVALID_AGENT_RESPONSE, str(exc.detail))
        
        return JSONResponse(
            content=self.handler.format_error_response(error),
            status_code=exc.status_code
        )
    
    # A2A Protocol Endpoints
    
    async def get_agent_card(self, request: Request) -> JSONResponse:
        """GET /.well-known/agent.json - Return agent capabilities"""
        agent_card = self.handler.get_agent_card()
        return JSONResponse(agent_card)
    
    async def submit_task(self, request: Request) -> JSONResponse:
        """POST /tasks/submit - Submit a new task"""
        try:
            # Check authentication
            if self.config.get("auth_required", True) and not request.user.is_authenticated:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Parse request body
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON in request body")
            
            # Validate required fields
            required_fields = ["description", "inputData"]
            for field in required_fields:
                if field not in body:
                    raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
            
            # Extract task data
            task_id = body.get("taskId", str(uuid.uuid4()))
            description = body["description"]
            input_data = body["inputData"]
            input_types = body.get("inputTypes", ["text/plain"])
            output_types = body.get("outputTypes", ["text/plain"])
            metadata = body.get("metadata", {})
            
            # Create task
            created_task_id = await self.handler.create_task(
                description=description,
                input_data=input_data,
                input_types=input_types,
                output_types=output_types,
                metadata=metadata
            )
            
            # Execute task asynchronously with error handling
            async def execute_with_error_handling():
                try:
                    await self.handler.execute_task(created_task_id, self.agent_context)
                except Exception as e:
                    PrintStyle(background_color="red", font_color="white").print(
                        f"Task execution failed: {str(e)}"
                    )
                    self.handler.update_task_state(
                        created_task_id, 
                        TaskState.FAILED, 
                        error=f"Task execution failed: {str(e)}"
                    )
            
            asyncio.create_task(execute_with_error_handling())
            
            return JSONResponse({
                "taskId": created_task_id,
                "state": TaskState.SUBMITTED.value,
                "message": "Task submitted successfully"
            }, status_code=201)
            
        except HTTPException:
            raise
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"Task submission error: {str(e)}"
            )
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def get_task_status(self, request: Request) -> JSONResponse:
        """GET /tasks/{id} - Get task status"""
        try:
            task_id = request.path_params["task_id"]
            
            # Check authentication
            if self.config.get("auth_required", True) and not request.user.is_authenticated:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            task = self.handler.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            return JSONResponse(self.handler.format_task_response(task))
            
        except HTTPException:
            raise
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"Get task status error: {str(e)}"
            )
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def cancel_task(self, request: Request) -> JSONResponse:
        """POST /tasks/{id}/cancel - Cancel a task"""
        try:
            task_id = request.path_params["task_id"]
            
            # Check authentication
            if self.config.get("auth_required", True) and not request.user.is_authenticated:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            task = self.handler.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            # Check if task can be cancelled
            if task.state in [TaskState.COMPLETED, TaskState.FAILED]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Task {task_id} cannot be cancelled (state: {task.state.value})"
                )
            
            # Cancel the task
            self.handler.update_task_state(task_id, TaskState.FAILED, error="Task cancelled by user")
            
            return JSONResponse({
                "taskId": task_id,
                "message": "Task cancelled successfully"
            })
            
        except HTTPException:
            raise
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"Cancel task error: {str(e)}"
            )
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def set_push_config(self, request: Request) -> JSONResponse:
        """POST /tasks/{id}/pushNotificationConfig/set - Configure push notifications"""
        try:
            task_id = request.path_params["task_id"]
            
            # Check authentication
            if self.config.get("auth_required", True) and not request.user.is_authenticated:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            body = await request.json()
            webhook_url = body.get("url")
            events = body.get("events", [])
            
            if not webhook_url:
                raise HTTPException(status_code=400, detail="Missing webhook URL")
            
            task = self.handler.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            # Store webhook configuration (simplified implementation)
            task.metadata["webhook_url"] = webhook_url
            task.metadata["webhook_events"] = events
            
            return JSONResponse({
                "taskId": task_id,
                "message": "Push notification configured successfully"
            })
            
        except HTTPException:
            raise
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"Set push config error: {str(e)}"
            )
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def sse_stream(self, request: Request) -> StreamingResponse:
        """GET /message/stream - Server-Sent Events stream"""
        try:
            # Check authentication
            if self.config.get("auth_required", True) and not request.user.is_authenticated:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            return StreamingResponse(
                self._sse_generator(request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control"
                }
            )
            
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"SSE stream error: {str(e)}"
            )
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _sse_generator(self, request: Request) -> AsyncGenerator[str, None]:
        """Generate Server-Sent Events"""
        client_id = str(uuid.uuid4())
        self.sse_clients[client_id] = {"request": request, "connected": True}
        
        try:
            # Send initial connection event
            yield f"event: ConnectionEstablished\n"
            yield f"data: {json.dumps({'clientId': client_id, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            
            # Keep connection alive and send task updates
            while self.sse_clients.get(client_id, {}).get("connected", False):
                # Check if client is still connected
                if await request.is_disconnected():
                    break

                # Check for task updates to broadcast (more frequently)
                async for update in self._broadcast_task_updates(client_id):
                    yield update

                # Send heartbeat every 5 seconds (more frequent)
                yield f"event: Heartbeat\n"
                yield f"data: {json.dumps({'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

                await asyncio.sleep(5)  # Check more frequently
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"SSE generator error: {str(e)}"
            )
        finally:
            # Clean up client
            self.sse_clients.pop(client_id, None)
            self.sent_task_updates.pop(client_id, None)
    
    async def _broadcast_task_updates(self, client_id: str):
        """Broadcast task status updates to SSE clients"""
        # Initialize tracking for this client if not exists
        if client_id not in self.sent_task_updates:
            self.sent_task_updates[client_id] = set()

        for task_id, task in self.handler.tasks.items():
            if task.state in [TaskState.COMPLETED, TaskState.FAILED]:
                # Only send if we haven't sent this task update to this client yet
                if task_id not in self.sent_task_updates[client_id]:
                    event_data = {
                        "taskId": task_id,
                        "state": task.state.value,
                        "timestamp": task.updated_at.isoformat()
                    }

                    if task.artifacts:
                        event_data["artifacts"] = [
                            {
                                "type": artifact.type,
                                "content": artifact.content,
                                "metadata": artifact.metadata or {}
                            }
                            for artifact in task.artifacts
                        ]

                    # Mark as sent
                    self.sent_task_updates[client_id].add(task_id)

                    # Debug logging
                    PrintStyle(font_color="green").print(
                        f"SSE: Sending task update for {task_id} (state: {task.state.value}) to client {client_id}"
                    )

                    yield f"event: TaskStatusUpdateEvent\n"
                    yield f"data: {json.dumps(event_data)}\n\n"
    
    async def webhook_handler(self, request: Request) -> JSONResponse:
        """POST /push/{token} - Handle webhook notifications"""
        try:
            token = request.path_params["token"]
            
            # Parse webhook data
            try:
                webhook_data = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON in webhook data")
            
            # Handle the webhook
            success = await self.handler.handle_webhook(token, webhook_data)
            
            if success:
                return JSONResponse({"message": "Webhook processed successfully"})
            else:
                return JSONResponse(
                    {"error": "Webhook handler not found"},
                    status_code=404
                )
                
        except HTTPException:
            raise
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"Webhook handler error: {str(e)}"
            )
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def health_check(self, request: Request) -> JSONResponse:
        """GET /health - Health check endpoint"""
        # Get agent info if available
        agent_id = getattr(self.handler, 'agent_id', 'unknown')
        role = getattr(self.handler, 'role', 'unknown')
        
        # Get current task info
        current_task = None
        active_tasks = [t for t in self.handler.tasks.values() if t.state == TaskState.WORKING]
        if active_tasks:
            task = active_tasks[0]  # Get the first active task
            current_task = {
                "task_id": task.task_id,
                "description": task.description[:100] + "..." if len(task.description) > 100 else task.description,
                "state": task.state.value,
                "created_at": task.created_at.isoformat()
            }
        
        return JSONResponse({
            "status": "healthy",
            "agent_id": agent_id,
            "role": role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "tasks_active": len(active_tasks),
            "tasks_total": len(self.handler.tasks),
            "current_task": current_task
        })
    
    async def get_context_info(self, request: Request) -> JSONResponse:
        """GET /context/info - Get context information for registration"""
        try:
            # Get context information from the agent context if available
            context_info = {
                "context_id": getattr(self.context, 'id', 'unknown') if hasattr(self, 'context') else 'unknown',
                "context_name": getattr(self.context, 'name', 'unknown') if hasattr(self, 'context') else 'unknown',
                "context_type": getattr(self.context, 'type', {}).value if hasattr(self, 'context') and hasattr(self.context, 'type') else 'unknown',
                "agent_id": getattr(self.handler, 'agent_id', 'unknown'),
                "role": getattr(self.handler, 'role', 'unknown'),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return JSONResponse({
                "success": True,
                "context_info": context_info
            })
            
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)
    
    async def get_subordinate_registry(self, request: Request) -> JSONResponse:
        """GET /subordinates/registry - Get registry of all subordinate agents for peer discovery"""
        try:
            # Get the agent context to access subordinate manager
            agent_context = getattr(self, 'agent_context', None)
            
            subordinates_registry = {}
            
            # Check if we have access to subordinate manager
            if agent_context and hasattr(agent_context, 'subordinate_manager') and agent_context.subordinate_manager:
                subordinate_manager = agent_context.subordinate_manager
                
                # Get all subordinates from the manager
                for subordinate in subordinate_manager.get_all_subordinates():
                    subordinates_registry[subordinate.agent_id] = {
                        "agent_id": subordinate.agent_id,
                        "role": subordinate.role,
                        "url": subordinate.url,
                        "port": subordinate.port,
                        "status": subordinate.status,
                        "capabilities": subordinate.capabilities,
                        "spawned_at": subordinate.spawned_at.isoformat(),
                        "last_contact": subordinate.last_contact.isoformat()
                    }
                    
            return JSONResponse({
                "success": True,
                "subordinates": subordinates_registry,
                "count": len(subordinates_registry),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e),
                "subordinates": {},
                "count": 0
            }, status_code=500)
    
    # Server Management
    
    async def start_server(
        self, 
        host: str = "0.0.0.0", 
        port: int = 8008,
        ssl_keyfile: Optional[str] = None,
        ssl_certfile: Optional[str] = None
    ):
        """Start the A2A server"""
        self.app = self.create_app()
        
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            log_level="info"
        )
        
        self.server = uvicorn.Server(config)
        
        PrintStyle(font_color="green", bold=True).print(
            f"Starting A2A server on {'https' if ssl_keyfile else 'http'}://{host}:{port}"
        )
        
        try:
            await self.server.serve()
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"A2A server error: {str(e)}"
            )
            raise
    
    async def stop_server(self):
        """Stop the A2A server"""
        if self.server:
            self.server.should_exit = True
            PrintStyle(font_color="yellow").print("A2A server stopping...")
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information"""
        return {
            "name": self.handler.agent_card.name if self.handler.agent_card else "Unknown",
            "version": self.handler.agent_card.version if self.handler.agent_card else "1.0.0",
            "capabilities": self.handler.agent_card.capabilities if self.handler.agent_card else [],
            "tasks_active": len([t for t in self.handler.tasks.values() if t.state == TaskState.WORKING]),
            "tasks_total": len(self.handler.tasks),
            "peers_connected": len(self.handler.peers),
            "sse_clients": len(self.sse_clients)
        }


class DynamicA2AProxy:
    """A dynamic proxy that allows swapping the underlying A2A application on the fly with token-based routing."""
    
    _instance: Optional['DynamicA2AProxy'] = None
    
    def __init__(self):
        from python.helpers import settings
        cfg = settings.get_settings()
        self.app: Optional[ASGIApp] = None
        self._lock = threading.RLock()  # Use RLock to avoid deadlocks
        self.token = cfg.get("a2a_server_token", "")
        self.a2a_server: Optional[A2AServer] = None
        self.agent_context = None
    
    @staticmethod
    def get_instance():
        if DynamicA2AProxy._instance is None:
            DynamicA2AProxy._instance = DynamicA2AProxy()
        return DynamicA2AProxy._instance
    
    def reconfigure(self, token: str):
        """Reconfigure A2A server with new token-based routing"""
        self.token = token
        
        with self._lock:
            if self.agent_context and self.a2a_server:
                # Update routes to include token-based paths
                self.app = self._create_token_app(token)
    
    def initialize_server(self, agent_context: Any, config: Dict[str, Any]):
        """Initialize the A2A server with agent context"""
        with self._lock:
            self.agent_context = agent_context
            self.a2a_server = A2AServer(config, agent_context)
            if self.token:
                self.app = self._create_token_app(self.token)
    
    def _create_token_app(self, token: str) -> ASGIApp:
        """Create Starlette app with both token-based and standard routing"""
        if not self.a2a_server:
            raise RuntimeError("A2A server not initialized")
        
        # Create routes with both token-based and standard endpoints
        all_routes = [
            # Standard A2A Protocol endpoints (for backward compatibility)
            Route("/.well-known/agent.json", self.a2a_server.get_agent_card, methods=["GET"]),
            Route("/tasks/submit", self.a2a_server.submit_task, methods=["POST"]),
            Route("/tasks/{task_id}", self.a2a_server.get_task_status, methods=["GET"]),
            Route("/tasks/{task_id}/cancel", self.a2a_server.cancel_task, methods=["POST"]),
            Route("/tasks/{task_id}/pushNotificationConfig/set", self.a2a_server.set_push_config, methods=["POST"]),
            Route("/message/stream", self.a2a_server.sse_stream, methods=["GET"]),
            Route("/push/{token}", self.a2a_server.webhook_handler, methods=["POST"]),
            Route("/health", self.a2a_server.health_check, methods=["GET"]),
            Route("/context/info", self.a2a_server.get_context_info, methods=["GET"]),
            Route("/subordinates/registry", self.a2a_server.get_subordinate_registry, methods=["GET"]),
            
            # Token-based routes (for enhanced security)
            Route(f"/t-{token}/.well-known/agent.json", self.a2a_server.get_agent_card, methods=["GET"]),
            Route(f"/t-{token}/tasks/submit", self.a2a_server.submit_task, methods=["POST"]),
            Route(f"/t-{token}/tasks/{{task_id}}", self.a2a_server.get_task_status, methods=["GET"]),
            Route(f"/t-{token}/tasks/{{task_id}}/cancel", self.a2a_server.cancel_task, methods=["POST"]),
            Route(f"/t-{token}/tasks/{{task_id}}/pushNotificationConfig/set", self.a2a_server.set_push_config, methods=["POST"]),
            Route(f"/t-{token}/message/stream", self.a2a_server.sse_stream, methods=["GET"]),
            Route(f"/t-{token}/push/{{webhook_token}}", self.a2a_server.webhook_handler, methods=["POST"]),
            Route(f"/t-{token}/health", self.a2a_server.health_check, methods=["GET"]),
            Route(f"/t-{token}/context/info", self.a2a_server.get_context_info, methods=["GET"]),
            
            # Subordinate registry with token
            Route(f"/t-{token}/subordinates/registry", self.a2a_server.get_subordinate_registry, methods=["GET"]),
        ]
        
        # Middleware
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
            Middleware(BaseHTTPMiddleware, dispatch=a2a_token_middleware),
        ]
        
        # Create new app with both standard and token routes
        combined_app = Starlette(
            routes=all_routes,
            middleware=middleware,
            exception_handlers={
                HTTPException: self.a2a_server.http_exception_handler
            }
        )
        
        return combined_app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Forward the ASGI calls to the current app"""
        with self._lock:
            app = self.app
        if app:
            await app(scope, receive, send)
        else:
            # Return 404 if no app is configured
            response = JSONResponse(
                {"error": "A2A server not configured"},
                status_code=404
            )
            await response(scope, receive, send)


async def a2a_token_middleware(request: Request, call_next):
    """A2A token validation middleware"""
    # Check if A2A server is enabled
    from python.helpers import settings
    cfg = settings.get_settings()
    if not cfg.get("a2a_enabled", False):
        PrintStyle.error("[A2A] Access denied: A2A server is disabled in settings.")
        raise HTTPException(
            status_code=403, detail="A2A server is disabled in settings."
        )
    
    return await call_next(request)