import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, AsyncGenerator
from urllib.parse import urljoin

import httpx
from httpx_sse import aconnect_sse

from python.helpers.print_style import PrintStyle
from python.helpers.a2a_handler import A2AError, A2AErrorType, TaskState


class A2AClient:
    """
    A2A Protocol Client
    
    Handles outbound communication with A2A-compliant agents.
    Supports all three interaction patterns:
    - Polling: Submit task and poll for results
    - Server-Sent Events (SSE): Real-time streaming updates  
    - Webhook Push: Callback-based notifications
    """
    
    def __init__(
        self, 
        auth_token: Optional[str] = None,
        auth_scheme: str = "bearer",
        url_token: Optional[str] = None,  # New: URL-based token authentication
        timeout: float = 30.0,
        max_retries: int = 5,  # Increased retries for subordinate startup
        retry_delay: float = 0.5  # Reduced initial delay for faster retries
    ):
        self.auth_token = auth_token
        self.auth_scheme = auth_scheme.lower()
        self.url_token = url_token  # Store URL token for path-based auth
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._close_client()
    
    async def _ensure_client(self):
        """Ensure HTTP client is initialized"""
        if self._client is None:
            headers = self._get_auth_headers()
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=headers,
                verify=True  # Always verify SSL certificates
            )
    
    async def _close_client(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers based on scheme"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Agent-Zero-A2A-Client/1.0"
        }
        
        if self.auth_token:
            if self.auth_scheme == "bearer":
                headers["Authorization"] = f"Bearer {self.auth_token}"
            elif self.auth_scheme == "api_key":
                headers["X-API-Key"] = self.auth_token
            elif self.auth_scheme == "basic":
                headers["Authorization"] = f"Basic {self.auth_token}"
    
        return headers
    
    def _build_token_url(self, base_url: str, endpoint: str) -> str:
        """Build URL with token-based routing if url_token is provided"""
        if self.url_token:
            # Use token-based routing: /t-{token}/endpoint
            return urljoin(base_url, f"/t-{self.url_token}{endpoint}")
        else:
            # Use standard routing
            return urljoin(base_url, endpoint)
    
    async def _make_request(
        self, 
        method: str, 
        url: str, 
        data: Optional[Dict[str, Any]] = None,
        retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        await self._ensure_client()
        
        if retries is None:
            retries = self.max_retries
        
        last_exception = None
        
        for attempt in range(retries + 1):
            try:
                if method.upper() == "GET":
                    response = await self._client.get(url)
                elif method.upper() == "POST":
                    response = await self._client.post(url, json=data)
                elif method.upper() == "PUT":
                    response = await self._client.put(url, json=data)
                elif method.upper() == "DELETE":
                    response = await self._client.delete(url)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Handle different response status codes
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 201:
                    return response.json()
                elif response.status_code == 204:
                    return {}
                elif response.status_code == 400:
                    error_data = response.json() if response.content else {}
                    raise A2AError(
                        A2AErrorType.INVALID_AGENT_RESPONSE,
                        f"Bad request: {error_data.get('message', 'Unknown error')}"
                    )
                elif response.status_code == 401:
                    raise A2AError(
                        A2AErrorType.UNSUPPORTED_OPERATION,
                        "Authentication failed"
                    )
                elif response.status_code == 404:
                    raise A2AError(
                        A2AErrorType.TASK_NOT_FOUND,
                        f"Resource not found: {url}"
                    )
                elif response.status_code == 415:
                    raise A2AError(
                        A2AErrorType.CONTENT_TYPE_NOT_SUPPORTED,
                        "Unsupported content type"
                    )
                else:
                    response.raise_for_status()
                    
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < retries:
                    PrintStyle(font_color="yellow").print(
                        f"A2A request timeout, retrying {attempt + 1}/{retries}"
                    )
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                continue
                
            except httpx.ConnectError as e:
                last_exception = e
                if attempt < retries:
                    PrintStyle(font_color="yellow").print(
                        f"A2A connection error, retrying {attempt + 1}/{retries}"
                    )
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                continue
                
            except A2AError:
                # Don't retry A2A protocol errors
                raise
                
            except Exception as e:
                last_exception = e
                if attempt < retries:
                    PrintStyle(font_color="yellow").print(
                        f"A2A request failed, retrying {attempt + 1}/{retries}: {str(e)}"
                    )
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                continue
        
        # All retries exhausted
        raise A2AError(
            A2AErrorType.INVALID_AGENT_RESPONSE,
            f"Request failed after {retries + 1} attempts: {str(last_exception)}"
        )
    
    # Core A2A Protocol Methods
    
    async def discover_agent(self, base_url: str) -> Dict[str, Any]:
        """Discover agent capabilities by fetching AgentCard"""
        agent_card_url = self._build_token_url(base_url, "/.well-known/agent.json")
        
        try:
            # Try health endpoint first as a quick connectivity check
            health_url = self._build_token_url(base_url, "/health")
            try:
                health_response = await self._make_request("GET", health_url, retries=2)
                if health_response:
                    PrintStyle(font_color="green").print(f"Agent health check passed: {base_url}")
            except Exception:
                # Health check failed, but still try agent card
                PrintStyle(font_color="yellow").print(f"Health check failed, trying agent card: {base_url}")
            
            return await self._make_request("GET", agent_card_url)
        except Exception as e:
            raise A2AError(
                A2AErrorType.INVALID_AGENT_RESPONSE,
                f"Failed to discover agent at {base_url}: {str(e)}"
            )
    
    async def submit_task(
        self, 
        peer_url: str, 
        task_data: Dict[str, Any]
    ) -> str:
        """Submit a task to a peer agent and return task ID"""
        submit_url = self._build_token_url(peer_url, "/tasks/submit")
        
        # Prepare A2A protocol request
        request_data = {
            "taskId": task_data.get("taskId", str(uuid.uuid4())),
            "description": task_data["description"],
            "inputData": task_data["inputData"],
            "inputTypes": task_data.get("inputTypes", ["text/plain"]),
            "outputTypes": task_data.get("outputTypes", ["text/plain"]),
            "metadata": task_data.get("metadata", {})
        }
        
        response = await self._make_request("POST", submit_url, request_data)
        
        task_id = response.get("taskId")
        if not task_id:
            raise A2AError(
                A2AErrorType.INVALID_AGENT_RESPONSE,
                "Task submission response missing taskId"
            )
        
        PrintStyle(font_color="green").print(
            f"A2A task submitted successfully: {task_id}"
        )
        
        return task_id
    
    async def get_task_status(self, peer_url: str, task_id: str) -> Dict[str, Any]:
        """Get the status of a submitted task"""
        status_url = self._build_token_url(peer_url, f"/tasks/{task_id}")
        
        response = await self._make_request("GET", status_url)
        
        # Validate response structure
        required_fields = ["taskId", "state"]
        for field in required_fields:
            if field not in response:
                raise A2AError(
                    A2AErrorType.INVALID_AGENT_RESPONSE,
                    f"Task status response missing required field: {field}"
                )
        
        return response
    
    async def cancel_task(self, peer_url: str, task_id: str) -> bool:
        """Cancel a submitted task"""
        cancel_url = self._build_token_url(peer_url, f"/tasks/{task_id}/cancel")
        
        try:
            await self._make_request("POST", cancel_url)
            return True
        except A2AError as e:
            if e.error_type == A2AErrorType.TASK_NOT_CANCELABLE:
                return False
            raise
    
    # Server-Sent Events (SSE) Methods
    
    async def submit_task_with_sse(
        self,
        peer_url: str,
        task_data: Dict[str, Any],
        timeout: int = 1800  # Increased to 30 minutes for complex tasks
    ) -> Dict[str, Any]:
        """Submit task and listen for updates via SSE"""
        # First submit the task
        task_id = await self.submit_task(peer_url, task_data)
        # Note: submit_task already prints success message, don't duplicate

        # Connect to SSE stream
        stream_url = self._build_token_url(peer_url, "/message/stream")
        PrintStyle(font_color="cyan").print(f"Connecting to SSE stream: {stream_url}")
        
        try:
            await self._ensure_client()
            
            async with aconnect_sse(
                self._client, "GET", stream_url,
                timeout=httpx.Timeout(timeout, read=timeout, write=30.0, connect=30.0),
                headers=self._get_auth_headers()
            ) as event_source:
                
                start_time = datetime.now()
                last_meaningful_event = datetime.now()
                heartbeat_count = 0
                max_heartbeats_without_progress = 60  # Max 60 heartbeats (5 minutes) without task progress

                async for sse_event in event_source.aiter_sse():
                    current_time = datetime.now()
                    elapsed_seconds = (current_time - start_time).seconds

                    # Check overall timeout
                    if elapsed_seconds > timeout:
                        raise A2AError(
                            A2AErrorType.INVALID_AGENT_RESPONSE,
                            f"SSE stream timed out after {timeout} seconds"
                        )

                    # Check for too many heartbeats without progress
                    if sse_event.event == "Heartbeat":
                        heartbeat_count += 1
                        if heartbeat_count > max_heartbeats_without_progress:
                            time_since_meaningful = (current_time - last_meaningful_event).seconds
                            raise A2AError(
                                A2AErrorType.INVALID_AGENT_RESPONSE,
                                f"Task appears stuck - received {heartbeat_count} heartbeats without progress for {time_since_meaningful} seconds"
                            )
                    else:
                        # Reset heartbeat count on meaningful events
                        heartbeat_count = 0
                        last_meaningful_event = current_time

                    # Debug: Log all SSE events
                    PrintStyle(font_color="yellow").print(
                        f"SSE Event received: {sse_event.event} - {sse_event.data[:100] if sse_event.data else 'No data'}..."
                    )

                    if sse_event.event == "TaskStatusUpdateEvent":
                        try:
                            event_data = json.loads(sse_event.data)
                            if event_data.get("taskId") == task_id:
                                state = event_data.get("state")
                                
                                if state == TaskState.COMPLETED.value:
                                    artifacts = event_data.get("artifacts", [])
                                    # Extract the main response content from artifacts with improved logic
                                    response_content = ""
                                    if artifacts:
                                        # First try to get text/plain artifact
                                        for artifact in artifacts:
                                            if artifact.get("type") == "text/plain" and artifact.get("content"):
                                                response_content = artifact.get("content", "")
                                                break
                                        
                                        # If no text/plain found, try other text types
                                        if not response_content:
                                            for artifact in artifacts:
                                                artifact_type = artifact.get("type", "")
                                                if artifact_type.startswith("text/") and artifact.get("content"):
                                                    response_content = artifact.get("content", "")
                                                    break
                                        
                                        # If still no content, take any artifact with content
                                        if not response_content:
                                            for artifact in artifacts:
                                                if artifact.get("content"):
                                                    response_content = artifact.get("content", "")
                                                    break
                                    
                                    # Also check for direct response content in event data
                                    if not response_content and event_data.get("result"):
                                        response_content = event_data.get("result", "")
                                    
                                    return {
                                        "status": event_data,
                                        "artifacts": artifacts,
                                        "response": response_content,
                                        "content": response_content  # Backwards compatibility
                                    }
                                elif state == TaskState.FAILED.value:
                                    error_msg = event_data.get("error", "Task failed")
                                    raise A2AError(
                                        A2AErrorType.INVALID_AGENT_RESPONSE,
                                        f"Task failed: {error_msg}",
                                        task_id
                                    )
                        except json.JSONDecodeError:
                            PrintStyle(font_color="yellow").print(
                                f"Invalid JSON in SSE event: {sse_event.data}"
                            )
                            continue
                    
                    elif sse_event.event == "TaskArtifactUpdateEvent":
                        # Task artifact was updated, continue listening
                        continue
                        
        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            # Handle specific connection errors with retry logic
            error_msg = str(e)
            if "peer closed connection" in error_msg or "incomplete chunked read" in error_msg:
                PrintStyle(font_color="yellow").print(
                    f"SSE connection lost, attempting to fall back to polling: {error_msg}"
                )
                # Fall back to polling for task completion
                return await self._poll_for_completion(peer_url, task_id, timeout)
            else:
                raise A2AError(
                    A2AErrorType.INVALID_AGENT_RESPONSE,
                    f"SSE connection error: {error_msg}"
                )
        except Exception as e:
            error_msg = str(e)
            if "peer closed connection" in error_msg or "incomplete chunked read" in error_msg:
                PrintStyle(font_color="yellow").print(
                    f"SSE stream interrupted, falling back to polling: {error_msg}"
                )
                # Fall back to polling for task completion
                return await self._poll_for_completion(peer_url, task_id, timeout)
            else:
                raise A2AError(
                    A2AErrorType.INVALID_AGENT_RESPONSE,
                    f"SSE stream error: {error_msg}"
                )
        
        # If we get here, the stream ended without completion
        raise A2AError(
            A2AErrorType.INVALID_AGENT_RESPONSE,
            "SSE stream ended without task completion"
        )
    
    # Webhook Methods
    
    async def submit_task_with_webhook(
        self, 
        peer_url: str, 
        task_data: Dict[str, Any],
        webhook_url: str,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Submit task with webhook notification setup"""
        # First submit the task
        task_id = await self.submit_task(peer_url, task_data)
        
        # Configure push notification
        push_config_url = self._build_token_url(peer_url, f"/tasks/{task_id}/pushNotificationConfig/set")
        
        push_config = {
            "url": webhook_url,
            "events": ["TaskStatusUpdateEvent", "TaskArtifactUpdateEvent"]
        }
        
        try:
            await self._make_request("POST", push_config_url, push_config)
        except A2AError as e:
            if e.error_type == A2AErrorType.PUSH_NOT_SUPPORTED:
                # Fall back to polling
                PrintStyle(font_color="yellow").print(
                    "Webhook not supported by peer, falling back to polling"
                )
                return await self._poll_for_completion(peer_url, task_id, timeout)
            raise
        
        # Set up webhook listener and wait for completion
        return await self._wait_for_webhook(task_id, timeout)
    
    async def _poll_for_completion(
        self, 
        peer_url: str, 
        task_id: str, 
        timeout: int
    ) -> Dict[str, Any]:
        """Poll for task completion (fallback method)"""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            status = await self.get_task_status(peer_url, task_id)
            
            state = status.get("state")
            if state == TaskState.COMPLETED.value:
                return {
                    "status": status,
                    "artifacts": status.get("artifacts", [])
                }
            elif state == TaskState.FAILED.value:
                error_msg = status.get("error", "Task failed")
                raise A2AError(
                    A2AErrorType.INVALID_AGENT_RESPONSE,
                    f"Task failed: {error_msg}",
                    task_id
                )
            
            # Wait before next poll
            await asyncio.sleep(2.0)
        
        raise A2AError(
            A2AErrorType.INVALID_AGENT_RESPONSE,
            f"Task polling timed out after {timeout} seconds"
        )
    
    async def _wait_for_webhook(self, task_id: str, timeout: int) -> Dict[str, Any]:
        """Wait for webhook notification using proper async event coordination"""
        # Create an asyncio event for webhook completion
        webhook_event = asyncio.Event()
        webhook_result = {"status": None, "error": None}
        
        # Register webhook handler with A2A handler
        from python.helpers.a2a_handler import A2AHandler
        handler = A2AHandler.get_instance()
        
        # Generate unique webhook token for this task
        webhook_token = f"webhook_{task_id}_{uuid.uuid4().hex[:8]}"
        
        async def webhook_callback(data: Dict[str, Any]):
            """Callback function for webhook notifications"""
            try:
                if data.get("taskId") == task_id:
                    state = data.get("state")
                    if state in [TaskState.COMPLETED.value, TaskState.FAILED.value]:
                        webhook_result["status"] = data
                        if state == TaskState.FAILED.value:
                            webhook_result["error"] = data.get("error", "Task failed")
                        webhook_event.set()
            except Exception as e:
                webhook_result["error"] = f"Webhook callback error: {str(e)}"
                webhook_event.set()
        
        # Register the webhook handler
        handler.register_webhook_handler(webhook_token, webhook_callback)
        
        try:
            # Wait for webhook notification or timeout
            try:
                await asyncio.wait_for(webhook_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                raise A2AError(
                    A2AErrorType.INVALID_AGENT_RESPONSE,
                    f"Webhook notification timeout after {timeout} seconds",
                    task_id
                )
            
            # Check result
            if webhook_result["error"]:
                raise A2AError(
                    A2AErrorType.INVALID_AGENT_RESPONSE,
                    webhook_result["error"],
                    task_id
                )
            
            if webhook_result["status"]:
                status_data = webhook_result["status"]
                return {
                    "status": status_data,
                    "artifacts": status_data.get("artifacts", [])
                }
            else:
                raise A2AError(
                    A2AErrorType.INVALID_AGENT_RESPONSE,
                    "Webhook completed without valid status data",
                    task_id
                )
                
        finally:
            # Always clean up webhook handler
            handler.webhook_handlers.pop(webhook_token, None)
    
    # Utility Methods
    
    async def ping_peer(self, peer_url: str) -> bool:
        """Ping a peer agent to check connectivity"""
        try:
            agent_card = await self.discover_agent(peer_url)
            return bool(agent_card.get("name"))
        except Exception:
            return False
    
    async def list_peer_capabilities(self, peer_url: str) -> List[str]:
        """Get list of capabilities from a peer agent"""
        try:
            agent_card = await self.discover_agent(peer_url)
            return agent_card.get("capabilities", [])
        except Exception:
            return []
    
    def __del__(self):
        """Cleanup on deletion with proper async handling"""
        if self._client:
            # Properly schedule cleanup in the event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule cleanup as a task if loop is running
                    loop.create_task(self._close_client())
                else:
                    # Run cleanup directly if no loop is running
                    loop.run_until_complete(self._close_client())
            except RuntimeError:
                # No event loop available, create a new one for cleanup
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(self._close_client())
                    new_loop.close()
                except Exception:
                    # Last resort: force close without async
                    if hasattr(self._client, '_transport'):
                        try:
                            self._client._transport.close()
                        except Exception:
                            pass
            except Exception:
                # Graceful degradation - log but don't fail
                PrintStyle(font_color="yellow").print(
                    "Warning: Failed to properly cleanup A2A client connection"
                )