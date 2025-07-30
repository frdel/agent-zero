#!/usr/bin/env python3
"""
A2A Peer Communication Tool for Subordinate Agents

Enhanced A2A communication tool that enables subordinate agents to:
- Discover peer subordinate agents through parent registry
- Communicate directly with other subordinate agents  
- Communicate with the parent agent and user
- Maintain peer relationships for ongoing collaboration
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.a2a_client import A2AClient
from python.helpers.a2a_handler import A2AHandler, A2AError


class A2aPeerCommunication(Tool):
    """
    A2A Peer Communication Tool for Subordinate Agents
    
    Enables subordinate agents to discover and communicate with:
    - Other subordinate agents (peer-to-peer)
    - Parent agent 
    - User (through parent agent routing)
    """
    
    def __init__(self, agent, name: str, method, args: dict, message: str, loop_data: Any):
        super().__init__(agent, name, method, args, message, loop_data)
        self.peer_registry_cache = {}
        self.last_registry_fetch = None
        self.cache_ttl_seconds = 30  # Cache registry for 30 seconds
    
    async def execute(
        self,
        target: str = "",
        message: str = "",
        communication_type: str = "peer",  # "peer", "parent", "user"
        interaction_type: str = "sse",
        timeout: int = 120,
        discover_peers: str = "false",
        **kwargs
    ) -> Response:
        """
        Execute A2A peer communication
        
        Args:
            target: Target identifier (agent_id, role, or "parent"/"user")
            message: Message to send to target
            communication_type: "peer" (subordinate), "parent" (parent agent), "user" (via parent)
            interaction_type: "polling", "sse", or "webhook"
            timeout: Maximum time to wait for response
            discover_peers: "true" to refresh peer discovery, "false" to use cache
        """
        if not message.strip():
            return Response(
                message="Error: Message is required for A2A peer communication",
                break_loop=False
            )
        
        if not target.strip():
            return Response(
                message="Error: Target is required (agent_id, role, 'parent', or 'user')",
                break_loop=False
            )
        
        try:
            # Handle different communication types
            if communication_type.lower() == "user":
                return await self._communicate_with_user(target, message, timeout)
            elif communication_type.lower() == "parent":
                return await self._communicate_with_parent(message, timeout)
            elif communication_type.lower() == "peer":
                # Discover peers if requested or cache is stale
                if discover_peers.lower() == "true" or self._is_cache_stale():
                    await self._discover_peers()
                
                return await self._communicate_with_peer(target, message, interaction_type, timeout)
            else:
                return Response(
                    message=f"Error: Unsupported communication_type '{communication_type}'. Use 'peer', 'parent', or 'user'.",
                    break_loop=False
                )
                
        except Exception as e:
            error_msg = f"A2A Peer Communication Error: {str(e)}"
            PrintStyle(font_color="red").print(error_msg)
            return Response(message=error_msg, break_loop=False)
    
    async def _discover_peers(self) -> bool:
        """Discover peer subordinate agents from parent registry"""
        try:
            # Get parent agent info from config
            parent_url = self.agent.config.additional.get('parent_agent_url', '')
            parent_token = self.agent.config.additional.get('parent_agent_token', '')
            
            if not parent_url:
                PrintStyle(font_color="yellow").print("Warning: No parent agent URL configured for peer discovery")
                return False
            
            # Create A2A client with parent token
            async with A2AClient(url_token=parent_token) as client:
                # Fetch subordinate registry from parent
                registry_url = f"{parent_url}/subordinates/registry"
                
                try:
                    response = await client._make_request("GET", registry_url, retries=2)
                    
                    if response.get("success"):
                        subordinates = response.get("subordinates", {})
                        
                        # Filter out self and update cache
                        my_agent_id = self.agent.config.additional.get('agent_id', '')
                        self.peer_registry_cache = {
                            agent_id: info for agent_id, info in subordinates.items()
                            if agent_id != my_agent_id and info.get("status") in ["ready", "idle", "busy"]
                        }
                        
                        self.last_registry_fetch = datetime.now()
                        
                        PrintStyle(font_color="green").print(
                            f"Discovered {len(self.peer_registry_cache)} peer subordinate agents"
                        )
                        
                        # Log discovered peers
                        for peer_id, peer_info in self.peer_registry_cache.items():
                            PrintStyle(font_color="cyan").print(
                                f"  - {peer_info['role']} ({peer_id}) at {peer_info['url']}"
                            )
                        
                        return True
                        
                    else:
                        PrintStyle(font_color="yellow").print(
                            f"Failed to fetch subordinate registry: {response.get('error', 'Unknown error')}"
                        )
                        return False
                        
                except Exception as e:
                    PrintStyle(font_color="yellow").print(
                        f"Error fetching subordinate registry: {str(e)}"
                    )
                    return False
                    
        except Exception as e:
            PrintStyle(font_color="red").print(f"Peer discovery failed: {str(e)}")
            return False
    
    async def _communicate_with_peer(self, target: str, message: str, interaction_type: str, timeout: int) -> Response:
        """Communicate with a peer subordinate agent"""
        # Find target peer by agent_id or role
        target_peer = None
        target_url = None
        
        # First try exact agent_id match
        if target in self.peer_registry_cache:
            target_peer = self.peer_registry_cache[target]
            target_url = target_peer["url"]
        else:
            # Try role match
            for peer_id, peer_info in self.peer_registry_cache.items():
                if peer_info["role"].lower() == target.lower():
                    target_peer = peer_info
                    target_url = peer_info["url"]
                    break
        
        if not target_peer:
            # Try to discover peers if target not found
            await self._discover_peers()
            
            # Try again after discovery
            if target in self.peer_registry_cache:
                target_peer = self.peer_registry_cache[target]
                target_url = target_peer["url"]
            else:
                for peer_id, peer_info in self.peer_registry_cache.items():
                    if peer_info["role"].lower() == target.lower():
                        target_peer = peer_info
                        target_url = peer_info["url"]
                        break
            
            if not target_peer:
                available_peers = [f"{info['role']} ({peer_id})" for peer_id, info in self.peer_registry_cache.items()]
                return Response(
                    message=f"Error: Peer '{target}' not found. Available peers: {', '.join(available_peers) if available_peers else 'None'}",
                    break_loop=False
                )
        
        # Prepare task data for peer communication
        task_data = {
            "description": f"Peer message from {self.agent.config.additional.get('role', 'subordinate')}",
            "inputData": {
                "message": message,
                "sender_info": {
                    "agent_id": self.agent.config.additional.get('agent_id', ''),
                    "role": self.agent.config.additional.get('role', ''),
                    "type": "subordinate_peer"
                }
            },
            "metadata": {
                "peer_to_peer": True,
                "communication_type": "subordinate_to_subordinate"
            }
        }
        
        # Get parent token for auth
        parent_token = self.agent.config.additional.get('parent_agent_token', '')
        
        # Send message to peer
        try:
            async with A2AClient(url_token=parent_token) as client:
                if interaction_type.lower() == "sse":
                    response = await client.submit_task_with_sse(target_url, task_data, timeout)
                elif interaction_type.lower() == "polling":
                    task_id = await client.submit_task(target_url, task_data)
                    response = {"status": await client.get_task_status(target_url, task_id)}
                else:
                    return Response(
                        message=f"Error: Unsupported interaction_type '{interaction_type}' for peer communication",
                        break_loop=False
                    )
                
                # Extract response content
                response_content = self._extract_response_content(response)
                
                formatted_response = f"**Response from @{target_peer['role']} ({target_peer['agent_id']}):**\n\n{response_content}"
                
                return Response(message=formatted_response, break_loop=False)
                
        except Exception as e:
            return Response(
                message=f"Error communicating with peer {target}: {str(e)}",
                break_loop=False
            )
    
    async def _communicate_with_parent(self, message: str, timeout: int) -> Response:
        """Communicate with parent agent"""
        parent_url = self.agent.config.additional.get('parent_agent_url', '')
        parent_token = self.agent.config.additional.get('parent_agent_token', '')
        
        if not parent_url:
            return Response(
                message="Error: No parent agent URL configured",
                break_loop=False
            )
        
        task_data = {
            "description": f"Message from subordinate {self.agent.config.additional.get('role', '')}",
            "inputData": {
                "message": message,
                "sender_info": {
                    "agent_id": self.agent.config.additional.get('agent_id', ''),
                    "role": self.agent.config.additional.get('role', ''),
                    "type": "subordinate_to_parent"
                }
            }
        }
        
        try:
            async with A2AClient(url_token=parent_token) as client:
                response = await client.submit_task_with_sse(parent_url, task_data, timeout)
                response_content = self._extract_response_content(response)
                
                return Response(
                    message=f"**Response from Parent Agent:**\n\n{response_content}",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Error communicating with parent agent: {str(e)}",
                break_loop=False
            )
    
    async def _communicate_with_user(self, target: str, message: str, timeout: int) -> Response:
        """Communicate with user through parent agent routing"""
        # This would need to be routed through the parent agent to reach the user
        parent_message = f"[Message for User from {self.agent.config.additional.get('role', 'subordinate')}]: {message}"
        
        return await self._communicate_with_parent(parent_message, timeout)
    
    def _extract_response_content(self, response: Dict[str, Any]) -> str:
        """Extract readable content from A2A response"""
        # Try to get content from artifacts
        if response.get("artifacts"):
            for artifact in response["artifacts"]:
                if artifact.get("type") == "text/plain" and artifact.get("content"):
                    return artifact["content"]
        
        # Try response field
        if response.get("response"):
            return response["response"]
        
        # Try content field
        if response.get("content"):
            return response["content"]
        
        # Try status result
        if response.get("status", {}).get("result"):
            return response["status"]["result"]
        
        # Fallback
        return "Response received successfully (no detailed content available)"
    
    def _is_cache_stale(self) -> bool:
        """Check if peer registry cache is stale"""
        if not self.last_registry_fetch:
            return True
        
        cache_age = (datetime.now() - self.last_registry_fetch).total_seconds()
        return cache_age > self.cache_ttl_seconds
    
    async def before_execution(self, **kwargs: Any):
        """Called before tool execution"""
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(
            f"{self.agent.agent_name}: Using A2A Peer Communication"
        )
        
        # Show current peer count
        peer_count = len(self.peer_registry_cache)
        PrintStyle(font_color="#85C1E9").print(f"Known peers: {peer_count}")
        
        # Display tool arguments
        for key, value in self.args.items():
            if key not in ["discover_peers"]:  # Skip internal args
                PrintStyle(font_color="#85C1E9", bold=True).stream(f"{key}: ")
                PrintStyle(font_color="#85C1E9").stream(str(value))
                PrintStyle().print()
    
    async def after_execution(self, response: Response, **kwargs: Any):
        """Called after tool execution"""
        if response.message:
            PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: A2A Peer Communication Response"
            )
            PrintStyle(font_color="#85C1E9").print(response.message)