import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional, Type
from datetime import datetime, timezone

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.a2a_handler import A2AHandler, AgentCard, A2AError, A2AErrorType
from python.helpers.a2a_client import A2AClient
from python.helpers.extract_tools import load_classes_from_folder


class A2ATool(Tool):
    """
    A2A Tool Wrapper
    
    Wraps remote A2A agent capabilities as local Agent Zero tools.
    This allows Agent Zero to seamlessly use skills from other A2A-compliant
    agents as if they were local tools.
    """
    
    def __init__(
        self, 
        agent: Any, 
        name: str, 
        method: str | None, 
        args: dict[str, str], 
        message: str, 
        loop_data: Any | None,
        peer_url: str,
        capability_name: str,
        agent_card: AgentCard,
        auth_token: Optional[str] = None,
        **kwargs
    ):
        super().__init__(agent, name, method, args, message, loop_data, **kwargs)
        self.peer_url = peer_url
        self.capability_name = capability_name
        self.agent_card = agent_card
        self.auth_token = auth_token
    
    async def execute(self, **kwargs) -> Response:
        """Execute the remote A2A capability"""
        error = ""
        result_message = ""
        
        try:
            # Prepare task data for A2A protocol
            task_data = {
                "taskId": str(uuid.uuid4()),
                "description": f"Execute capability: {self.capability_name}",
                "inputData": {
                    "capability": self.capability_name,
                    "tool_name": self.name,
                    "method": self.method,
                    "arguments": self.args,
                    "message": self.message,
                    "agent_context": {
                        "agent_name": self.agent.agent_name,
                        "agent_number": self.agent.number,
                        "context_id": getattr(self.agent.context, 'context_id', 'unknown')
                    }
                },
                "inputTypes": self.agent_card.input_types,
                "outputTypes": self.agent_card.output_types,
                "metadata": {
                    "tool_execution": True,
                    "capability_name": self.capability_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_zero_tool": True
                }
            }
            
            # Execute via A2A client
            async with A2AClient(auth_token=self.auth_token) as client:
                # Submit task and poll for completion
                task_id = await client.submit_task(self.peer_url, task_data)
                
                # Poll for completion with timeout
                result = await self._poll_for_completion(client, task_id, timeout=60)
                
                # Format response
                result_message = self._format_tool_result(result)
                
        except A2AError as e:
            error = f"A2A Tool Error ({e.error_type.value}): {str(e)}"
            result_message = f"Failed to execute remote capability '{self.capability_name}': {error}"
            
        except Exception as e:
            error = f"A2A Tool Exception: {str(e)}"
            result_message = f"Error executing remote capability '{self.capability_name}': {error}"
        
        if error:
            PrintStyle(
                background_color="#CC34C3", font_color="white", bold=True, padding=True
            ).print(f"A2ATool::Failed to execute remote capability '{self.capability_name}':")
            PrintStyle(
                background_color="#AA4455", font_color="white", padding=False
            ).print(error)
            
            self.agent.context.log.log(
                type="error",
                content=f"A2A Tool '{self.name}' failed: {error}",
            )
        
        return Response(message=result_message, break_loop=False)
    
    async def _poll_for_completion(self, client: A2AClient, task_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Poll for task completion"""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            status = await client.get_task_status(self.peer_url, task_id)
            
            if status["state"] == "COMPLETED":
                return status
            elif status["state"] == "FAILED":
                error_msg = status.get("error", "Unknown error")
                raise A2AError(
                    A2AErrorType.INVALID_AGENT_RESPONSE,
                    f"Remote capability execution failed: {error_msg}",
                    task_id
                )
            
            await asyncio.sleep(2)
        
        raise A2AError(
            A2AErrorType.INVALID_AGENT_RESPONSE,
            f"Remote capability execution timed out after {timeout} seconds"
        )
    
    def _format_tool_result(self, result: Dict[str, Any]) -> str:
        """Format the A2A task result as a tool response"""
        artifacts = result.get("artifacts", [])
        
        if not artifacts:
            return f"Remote capability '{self.capability_name}' completed successfully (no artifacts)"
        
        # Process artifacts
        result_parts = [f"Results from remote capability '{self.capability_name}':"]
        
        for artifact in artifacts:
            artifact_type = artifact.get("type", "unknown")
            content = artifact.get("content", "")
            
            if artifact_type == "text/plain":
                result_parts.append(f"- {content}")
            elif artifact_type == "application/json":
                try:
                    if isinstance(content, str):
                        parsed_content = json.loads(content)
                    else:
                        parsed_content = content
                    result_parts.append(f"- {json.dumps(parsed_content, indent=2)}")
                except json.JSONDecodeError:
                    result_parts.append(f"- {content}")
            else:
                result_parts.append(f"- [{artifact_type}] {content}")
        
        return "\n".join(result_parts)
    
    async def before_execution(self, **kwargs: Any):
        """Called before tool execution"""
        PrintStyle(
            font_color="#1B4F72", padding=True, background_color="white", bold=True
        ).print(f"{self.agent.agent_name}: Using remote A2A capability '{self.capability_name}' from {self.peer_url}")
        
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
        """Called after tool execution"""
        raw_tool_response = response.message.strip() if response.message else ""
        if not raw_tool_response:
            PrintStyle(font_color="red").print(
                f"Warning: A2A Tool '{self.name}' returned an empty message."
            )
            raw_tool_response = f"[A2A Tool '{self.capability_name}' returned no content]"
        
        # Log the result
        self.agent.hist_add_tool_result(self.name, raw_tool_response)
        
        PrintStyle(
            font_color="#1B4F72", background_color="white", padding=True, bold=True
        ).print(f"{self.agent.agent_name}: Response from A2A capability '{self.capability_name}'")
        
        PrintStyle(font_color="#85C1E9").print(raw_tool_response)
        
        if self.log:
            self.log.update(content=raw_tool_response)
    
    def get_log_object(self):
        """Create a log object for this tool execution"""
        return self.agent.context.log.log(
            type="tool",
            heading=f"icon://cloud {self.agent.agent_name}: A2A Capability '{self.capability_name}'",
            content="",
            kvps=self.args,
        )


class A2AToolRegistry:
    """
    A2A Tool Registry
    
    Manages discovery, registration, and creation of A2A tools from remote agents.
    Integrates with Agent Zero's existing tool discovery system.
    """
    
    def __init__(self):
        self.discovered_tools: Dict[str, Dict[str, Any]] = {}
        self.peer_agents: Dict[str, AgentCard] = {}
        self.handler = A2AHandler.get_instance()
    
    async def discover_tools_from_peer(
        self, 
        peer_url: str, 
        auth_token: Optional[str] = None
    ) -> List[str]:
        """
        Discover available tools/capabilities from an A2A peer.
        
        Args:
            peer_url: URL of the peer agent
            auth_token: Authentication token for the peer
            
        Returns:
            List of discovered tool names
        """
        try:
            # Discover agent card
            agent_card = await self.handler.discover_peer(peer_url)
            
            if not agent_card:
                raise Exception("Failed to discover agent card")
            
            # Store peer agent info
            peer_id = self._get_peer_id_from_url(peer_url)
            self.peer_agents[peer_id] = agent_card
            
            # Create tool entries for each capability
            discovered_tool_names = []
            
            for capability in agent_card.capabilities:
                tool_name = f"a2a_{peer_id}_{capability}".replace(":", "_").replace(".", "_")
                
                self.discovered_tools[tool_name] = {
                    "peer_url": peer_url,
                    "peer_id": peer_id,
                    "capability_name": capability,
                    "agent_card": agent_card,
                    "auth_token": auth_token,
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "input_types": agent_card.input_types,
                    "output_types": agent_card.output_types
                }
                
                discovered_tool_names.append(tool_name)
            
            PrintStyle(font_color="green").print(
                f"Discovered {len(discovered_tool_names)} A2A tools from {peer_url}"
            )
            
            return discovered_tool_names
            
        except Exception as e:
            PrintStyle(background_color="red", font_color="white").print(
                f"Failed to discover A2A tools from {peer_url}: {str(e)}"
            )
            return []
    
    async def discover_tools_from_registry(
        self, 
        peer_urls: List[str],
        auth_tokens: Optional[Dict[str, str]] = None
    ) -> Dict[str, List[str]]:
        """
        Discover tools from multiple peers in the registry.
        
        Args:
            peer_urls: List of peer URLs to discover from
            auth_tokens: Dictionary mapping peer URLs to auth tokens
            
        Returns:
            Dictionary mapping peer URLs to lists of discovered tool names
        """
        discovery_results = {}
        auth_tokens = auth_tokens or {}
        
        # Discover from all peers concurrently
        discovery_tasks = []
        for peer_url in peer_urls:
            auth_token = auth_tokens.get(peer_url)
            task = asyncio.create_task(
                self.discover_tools_from_peer(peer_url, auth_token)
            )
            discovery_tasks.append((peer_url, task))
        
        # Collect results
        for peer_url, task in discovery_tasks:
            try:
                tool_names = await task
                discovery_results[peer_url] = tool_names
            except Exception as e:
                PrintStyle(font_color="yellow").print(
                    f"Discovery failed for {peer_url}: {str(e)}"
                )
                discovery_results[peer_url] = []
        
        total_tools = sum(len(tools) for tools in discovery_results.values())
        PrintStyle(font_color="cyan").print(
            f"A2A tool discovery completed. {total_tools} tools discovered from {len(peer_urls)} peers."
        )
        
        return discovery_results
    
    def create_tool(
        self, 
        agent: Any, 
        tool_name: str, 
        method: str | None = None,
        args: Dict[str, str] = None,
        message: str = "",
        loop_data: Any = None
    ) -> Optional[A2ATool]:
        """
        Create an A2A tool instance for the given tool name.
        
        This method is called by Agent Zero's tool discovery system when
        it encounters an A2A tool name.
        """
        tool_info = self.discovered_tools.get(tool_name)
        
        if not tool_info:
            return None
        
        return A2ATool(
            agent=agent,
            name=tool_name,
            method=method,
            args=args or {},
            message=message,
            loop_data=loop_data,
            peer_url=tool_info["peer_url"],
            capability_name=tool_info["capability_name"],
            agent_card=tool_info["agent_card"],
            auth_token=tool_info["auth_token"]
        )
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available in the A2A registry"""
        return tool_name in self.discovered_tools
    
    def list_available_tools(self) -> Dict[str, Dict[str, Any]]:
        """List all available A2A tools with their metadata"""
        return {
            tool_name: {
                "peer_url": info["peer_url"],
                "capability_name": info["capability_name"],
                "agent_name": info["agent_card"].name,
                "agent_description": info["agent_card"].description,
                "input_types": info["input_types"],
                "output_types": info["output_types"],
                "discovered_at": info["discovered_at"]
            }
            for tool_name, info in self.discovered_tools.items()
        }
    
    def get_tools_by_capability(self, capability: str) -> List[str]:
        """Get all tools that provide a specific capability"""
        return [
            tool_name for tool_name, info in self.discovered_tools.items()
            if info["capability_name"] == capability
        ]
    
    def get_tools_by_peer(self, peer_url: str) -> List[str]:
        """Get all tools from a specific peer"""
        return [
            tool_name for tool_name, info in self.discovered_tools.items()
            if info["peer_url"] == peer_url
        ]
    
    def remove_peer_tools(self, peer_url: str) -> int:
        """Remove all tools from a specific peer"""
        tools_to_remove = self.get_tools_by_peer(peer_url)
        
        for tool_name in tools_to_remove:
            del self.discovered_tools[tool_name]
        
        # Also remove from peer agents
        peer_id = self._get_peer_id_from_url(peer_url)
        self.peer_agents.pop(peer_id, None)
        
        if tools_to_remove:
            PrintStyle(font_color="yellow").print(
                f"Removed {len(tools_to_remove)} A2A tools from peer {peer_url}"
            )
        
        return len(tools_to_remove)
    
    def validate_tool_compatibility(self, tool_name: str, required_types: List[str]) -> bool:
        """Validate that a tool supports required input/output types"""
        tool_info = self.discovered_tools.get(tool_name)
        
        if not tool_info:
            return False
        
        # Check if tool supports all required types
        supported_types = set(tool_info["input_types"] + tool_info["output_types"])
        return all(req_type in supported_types for req_type in required_types)
    
    def _get_peer_id_from_url(self, peer_url: str) -> str:
        """Generate a consistent peer ID from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(peer_url)
        return f"{parsed.hostname}_{parsed.port or (443 if parsed.scheme == 'https' else 80)}"


# Global registry instance
_a2a_tool_registry = None

def get_a2a_tool_registry() -> A2AToolRegistry:
    """Get the global A2A tool registry instance"""
    global _a2a_tool_registry
    if _a2a_tool_registry is None:
        _a2a_tool_registry = A2AToolRegistry()
    return _a2a_tool_registry


# Integration with Agent Zero's tool discovery system

def register_a2a_tools_with_agent_zero():
    """
    Register A2A tools with Agent Zero's tool discovery system.
    
    This function should be called during Agent Zero initialization
    to make A2A tools available to the agent.
    """
    try:
        # This would integrate with Agent Zero's existing tool discovery
        # For now, we'll create a simple registration mechanism
        registry = get_a2a_tool_registry()
        
        PrintStyle(font_color="cyan").print(
            "A2A Tool Registry initialized and ready for tool discovery"
        )
        
        return registry
        
    except Exception as e:
        PrintStyle(background_color="red", font_color="white").print(
            f"Failed to register A2A tools: {str(e)}"
        )
        return None


def create_a2a_tool_if_available(
    agent: Any,
    tool_name: str,
    method: str | None = None,
    args: Dict[str, str] = None,
    message: str = "",
    loop_data: Any = None
) -> Optional[Tool]:
    """
    Create an A2A tool if the tool name corresponds to a discovered A2A capability.
    
    This function can be integrated into Agent Zero's existing tool creation flow
    to provide seamless A2A tool support.
    """
    registry = get_a2a_tool_registry()
    
    if registry.has_tool(tool_name):
        return registry.create_tool(agent, tool_name, method, args, message, loop_data)
    
    return None