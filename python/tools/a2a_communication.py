from typing import Any, Dict, Optional, Union
import json
import asyncio
import uuid
from datetime import datetime, timezone

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers import errors


class A2ACommunication(Tool):
    """
    A2A (Agent-to-Agent) Communication Tool
    
    Enables Agent Zero to communicate with other A2A-compliant agents
    using the standard A2A protocol (JSON-RPC 2.0 over HTTP/HTTPS).
    
    Supports three interaction patterns:
    - Polling: Submit task and poll for results
    - Server-Sent Events (SSE): Real-time streaming updates
    - Webhook Push: Callback-based notifications
    """

    async def execute(
        self,
        peer_url: str = "",
        task_description: str = "",
        interaction_type: str = "polling",
        timeout: int = 60,
        auth_token: str = "",
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Response:
        """
        Execute A2A communication with a peer agent.
        
        Args:
            peer_url: URL of the target A2A-compliant agent
            task_description: Description of the task to delegate
            interaction_type: "polling", "sse", or "webhook"
            timeout: Timeout in seconds for the operation
            auth_token: Authentication token for the peer agent
            context: Additional context to include with the task
        """
        error = ""
        result_message = ""
        
        try:
            # Validate required parameters
            if not peer_url:
                raise ValueError("peer_url is required for A2A communication")
            if not task_description:
                raise ValueError("task_description is required for A2A communication")
            
            # Ensure peer_url uses HTTPS for security
            if not peer_url.startswith("https://") and not peer_url.startswith("http://localhost"):
                if peer_url.startswith("http://"):
                    peer_url = peer_url.replace("http://", "https://", 1)
                else:
                    peer_url = f"https://{peer_url}"
            
            # Get A2A handler instance
            from python.helpers.a2a_handler import A2AHandler
            a2a_handler = A2AHandler.get_instance()
            
            # Prepare task data following A2A protocol
            task_data = {
                "taskId": str(uuid.uuid4()),
                "description": task_description,
                "inputData": {
                    "message": task_description,
                    "context": context or {},
                    "agent_context": {
                        "agent_name": self.agent.agent_name,
                        "agent_number": self.agent.number,
                        "superior_agent": self.agent.get_data("superior") is not None
                    }
                },
                "inputTypes": ["text/plain", "application/json"],
                "outputTypes": ["text/plain", "application/json"],
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_agent": self.agent.agent_name,
                    "interaction_type": interaction_type,
                    "timeout": timeout
                }
            }
            
            # Execute communication based on interaction type
            if interaction_type.lower() == "polling":
                result_message = await self._execute_polling(
                    a2a_handler, peer_url, task_data, auth_token, timeout
                )
            elif interaction_type.lower() == "sse":
                result_message = await self._execute_sse(
                    a2a_handler, peer_url, task_data, auth_token, timeout
                )
            elif interaction_type.lower() == "webhook":
                result_message = await self._execute_webhook(
                    a2a_handler, peer_url, task_data, auth_token, timeout
                )
            else:
                raise ValueError(f"Unsupported interaction type: {interaction_type}")
                
        except Exception as e:
            error = f"A2A Communication Error: {str(e)}"
            result_message = f"Failed to communicate with peer agent at {peer_url}: {error}"
            
            # Log the error
            self.agent.context.log.log(
                type="error",
                content=f"A2A communication failed: {error}",
            )

        if error:
            PrintStyle(
                background_color="#CC34C3", font_color="white", bold=True, padding=True
            ).print(f"A2A Communication::Failed to communicate with peer:")
            PrintStyle(
                background_color="#AA4455", font_color="white", padding=False
            ).print(error)

        return Response(message=result_message, break_loop=False)

    async def _execute_polling(
        self, 
        a2a_handler: Any, 
        peer_url: str, 
        task_data: Dict[str, Any], 
        auth_token: str,
        timeout: int
    ) -> str:
        """Execute A2A communication using polling pattern."""
        from python.helpers.a2a_client import A2AClient
        
        client = A2AClient(auth_token=auth_token)
        
        # Submit task to peer agent
        task_id = await client.submit_task(peer_url, task_data)
        
        # Poll for completion
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout:
            task_status = await client.get_task_status(peer_url, task_id)
            
            if task_status["state"] == "COMPLETED":
                artifacts = task_status.get("artifacts", [])
                if artifacts:
                    return self._format_task_result(task_status, artifacts)
                else:
                    return f"Task completed successfully on peer agent {peer_url}"
                    
            elif task_status["state"] == "FAILED":
                error_msg = task_status.get("error", "Unknown error")
                raise Exception(f"Task failed on peer agent: {error_msg}")
                
            elif task_status["state"] == "INPUT_REQUIRED":
                # Handle input required scenario
                input_request = task_status.get("inputRequest", {})
                return f"Peer agent requires input: {input_request.get('prompt', 'Input needed')}"
            
            # Wait before next poll
            await asyncio.sleep(2)
        
        raise Exception(f"Task timed out after {timeout} seconds")

    async def _execute_sse(
        self, 
        a2a_handler: Any, 
        peer_url: str, 
        task_data: Dict[str, Any], 
        auth_token: str,
        timeout: int
    ) -> str:
        """Execute A2A communication using Server-Sent Events (SSE) pattern."""
        from python.helpers.a2a_client import A2AClient
        
        client = A2AClient(auth_token=auth_token)
        
        # Submit task and get SSE stream
        result = await client.submit_task_with_sse(peer_url, task_data, timeout)
        
        return self._format_task_result(result.get("status", {}), result.get("artifacts", []))

    async def _execute_webhook(
        self, 
        a2a_handler: Any, 
        peer_url: str, 
        task_data: Dict[str, Any], 
        auth_token: str,
        timeout: int
    ) -> str:
        """Execute A2A communication using webhook pattern."""
        from python.helpers.a2a_client import A2AClient
        
        client = A2AClient(auth_token=auth_token)
        
        # Register webhook endpoint and submit task
        webhook_url = a2a_handler.get_webhook_url()
        result = await client.submit_task_with_webhook(peer_url, task_data, webhook_url, timeout)
        
        return self._format_task_result(result.get("status", {}), result.get("artifacts", []))

    def _format_task_result(self, task_status: Dict[str, Any], artifacts: list) -> str:
        """Format the task result from A2A response into a readable message."""
        result_parts = []
        
        # Add basic status info
        state = task_status.get("state", "UNKNOWN")
        result_parts.append(f"Task completed with state: {state}")
        
        # Add artifacts content
        if artifacts:
            result_parts.append("Results:")
            for artifact in artifacts:
                artifact_type = artifact.get("type", "unknown")
                content = artifact.get("content", "")
                
                if artifact_type == "text/plain":
                    result_parts.append(f"- {content}")
                elif artifact_type == "application/json":
                    try:
                        parsed_content = json.loads(content) if isinstance(content, str) else content
                        result_parts.append(f"- {json.dumps(parsed_content, indent=2)}")
                    except json.JSONDecodeError:
                        result_parts.append(f"- {content}")
                else:
                    result_parts.append(f"- [{artifact_type}] {content}")
        
        # Add metadata if available
        metadata = task_status.get("metadata", {})
        if metadata:
            completion_time = metadata.get("completedAt")
            if completion_time:
                result_parts.append(f"Completed at: {completion_time}")
        
        return "\n".join(result_parts)

    async def before_execution(self, **kwargs: Any):
        """Called before tool execution for logging and setup."""
        PrintStyle(
            font_color="#1B4F72", padding=True, background_color="white", bold=True
        ).print(f"{self.agent.agent_name}: Using A2A Communication tool")
        
        self.log = self.get_log_object()

        # Display tool arguments
        for key, value in self.args.items():
            PrintStyle(font_color="#85C1E9", bold=True).stream(
                self.nice_key(key) + ": "
            )
            PrintStyle(
                font_color="#85C1E9", padding=isinstance(value, str) and "\n" in value
            ).stream(str(value))
            PrintStyle().print()

    async def after_execution(self, response: Response, **kwargs: Any):
        """Called after tool execution for logging and cleanup."""
        raw_tool_response = response.message.strip() if response.message else ""
        if not raw_tool_response:
            PrintStyle(font_color="red").print(
                "Warning: A2A Communication tool returned an empty message."
            )
            raw_tool_response = "[A2A Communication returned no content]"

        # Log the result
        self.agent.hist_add_tool_result(self.name, raw_tool_response)
        
        PrintStyle(
            font_color="#1B4F72", background_color="white", padding=True, bold=True
        ).print(f"{self.agent.agent_name}: Response from A2A Communication")
        
        PrintStyle(font_color="#85C1E9").print(raw_tool_response)
        
        if self.log:
            self.log.update(content=raw_tool_response)

    def get_log_object(self):
        """Create a log object for this tool execution."""
        return self.agent.context.log.log(
            type="tool",
            heading=f"icon://communication {self.agent.agent_name}: A2A Communication",
            content="",
            kvps=self.args,
        )