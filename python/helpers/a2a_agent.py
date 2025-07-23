import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from python.helpers.print_style import PrintStyle
from python.helpers.a2a_handler import A2AHandler, PeerInfo, AgentCard
from python.helpers.a2a_client import A2AClient


class A2AAgent:
    """
    A2A Peer-to-Peer Communication Layer
    
    Extends Agent Zero's hierarchical communication system with mesh-style
    peer-to-peer capabilities while maintaining backward compatibility.
    
    Features:
    - Direct peer-to-peer messaging between agents
    - Automatic discovery and registration of A2A peers
    - Message format conversion for backward compatibility
    - Integration with existing superior-subordinate relationships
    """
    
    def __init__(self, agent: Any, context: Any):
        self.agent = agent
        self.context = context
        self.handler = A2AHandler.get_instance()
        self.discovered_peers: Dict[str, AgentCard] = {}
        
    async def send_peer_message(
        self, 
        peer_url: str, 
        message: str,
        context_data: Optional[Dict[str, Any]] = None,
        timeout: int = 60,
        interaction_type: str = "polling"
    ) -> str:
        """
        Send a direct message to a peer agent.
        
        This method provides peer-to-peer communication capability while
        maintaining compatibility with Agent Zero's existing message format.
        
        Args:
            peer_url: URL of the target A2A-compliant agent
            message: Message content to send
            context_data: Additional context to include
            timeout: Timeout for the operation
            interaction_type: "polling", "sse", or "webhook"
            
        Returns:
            Response message from the peer agent
        """
        try:
            # Discover peer capabilities if not already known
            peer_id = self._get_peer_id_from_url(peer_url)
            if peer_id not in self.discovered_peers:
                await self._discover_and_register_peer(peer_url)
            
            # Prepare message in A2A format
            task_data = {
                "taskId": str(uuid.uuid4()),
                "description": f"Peer message from {self.agent.agent_name}",
                "inputData": {
                    "message": message,
                    "context": context_data or {},
                    "source_agent": {
                        "name": self.agent.agent_name,
                        "number": self.agent.number,
                        "context_id": self.context.context_id,
                        "superior_present": self.agent.get_data("superior") is not None
                    },
                    "interaction_metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message_type": "peer_communication",
                        "requires_response": True
                    }
                },
                "inputTypes": ["text/plain", "application/json"],
                "outputTypes": ["text/plain", "application/json"],
                "metadata": {
                    "peer_to_peer": True,
                    "agent_zero_message": True,
                    "interaction_type": interaction_type,
                    "timeout": timeout
                }
            }
            
            # Get authentication token for peer
            auth_token = self._get_auth_token_for_peer(peer_id)
            
            # Create client and send message
            async with A2AClient(auth_token=auth_token, timeout=timeout) as client:
                if interaction_type.lower() == "polling":
                    response = await self._send_with_polling(client, peer_url, task_data, timeout)
                elif interaction_type.lower() == "sse":
                    response = await self._send_with_sse(client, peer_url, task_data, timeout)
                elif interaction_type.lower() == "webhook":
                    response = await self._send_with_webhook(client, peer_url, task_data, timeout)
                else:
                    raise ValueError(f"Unsupported interaction type: {interaction_type}")
            
            # Update peer last contact time
            self._update_peer_contact_time(peer_id)
            
            # Log the successful communication
            PrintStyle(font_color="green").print(
                f"A2A peer message sent successfully to {peer_url}"
            )
            
            return self._format_peer_response(response)
            
        except Exception as e:
            error_msg = f"Failed to send peer message to {peer_url}: {str(e)}"
            PrintStyle(background_color="red", font_color="white").print(error_msg)
            
            # Log error to context
            self.context.log.log(
                type="error",
                content=f"A2A peer communication failed: {error_msg}"
            )
            
            return f"Peer communication error: {str(e)}"
    
    async def broadcast_to_peers(
        self, 
        message: str,
        peer_urls: Optional[List[str]] = None,
        context_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Dict[str, str]:
        """
        Broadcast a message to multiple peer agents.
        
        Args:
            message: Message to broadcast
            peer_urls: List of peer URLs (if None, broadcasts to all known peers)
            context_data: Additional context data
            timeout: Timeout for each peer communication
            
        Returns:
            Dictionary mapping peer URLs to their responses
        """
        if peer_urls is None:
            peer_urls = list(self.discovered_peers.keys())
        
        if not peer_urls:
            PrintStyle(font_color="yellow").print("No peers available for broadcast")
            return {}
        
        PrintStyle(font_color="cyan").print(
            f"Broadcasting message to {len(peer_urls)} peers"
        )
        
        # Send messages concurrently to all peers
        tasks = []
        for peer_url in peer_urls:
            task = asyncio.create_task(
                self.send_peer_message(peer_url, message, context_data, timeout, "polling")
            )
            tasks.append((peer_url, task))
        
        # Collect responses
        responses = {}
        for peer_url, task in tasks:
            try:
                response = await task
                responses[peer_url] = response
            except Exception as e:
                responses[peer_url] = f"Error: {str(e)}"
        
        PrintStyle(font_color="green").print(
            f"Broadcast completed. {len([r for r in responses.values() if not r.startswith('Error:')])} successful"
        )
        
        return responses
    
    async def discover_peers_from_registry(self, registry_urls: List[str]) -> List[str]:
        """
        Discover peers from a list of registry URLs.
        
        Args:
            registry_urls: List of potential peer URLs to check
            
        Returns:
            List of successfully discovered peer URLs
        """
        discovered = []
        
        PrintStyle(font_color="cyan").print(
            f"Discovering peers from {len(registry_urls)} registry entries"
        )
        
        for url in registry_urls:
            try:
                await self._discover_and_register_peer(url)
                discovered.append(url)
                PrintStyle(font_color="green").print(f"Discovered peer: {url}")
            except Exception as e:
                PrintStyle(font_color="yellow").print(
                    f"Failed to discover peer at {url}: {str(e)}"
                )
        
        PrintStyle(font_color="cyan").print(
            f"Peer discovery completed. {len(discovered)} peers discovered."
        )
        
        return discovered
    
    def get_peer_capabilities(self, peer_url: str) -> List[str]:
        """Get capabilities of a discovered peer"""
        peer_id = self._get_peer_id_from_url(peer_url)
        peer_card = self.discovered_peers.get(peer_id)
        return peer_card.capabilities if peer_card else []
    
    def list_discovered_peers(self) -> Dict[str, Dict[str, Any]]:
        """List all discovered peers with their information"""
        return {
            peer_id: {
                "name": card.name,
                "description": card.description,
                "version": card.version,
                "capabilities": card.capabilities,
                "input_types": card.input_types,
                "output_types": card.output_types,
                "auth_required": card.auth_required
            }
            for peer_id, card in self.discovered_peers.items()
        }
    
    def is_peer_compatible(self, peer_url: str, required_capabilities: List[str]) -> bool:
        """Check if a peer has required capabilities"""
        peer_capabilities = self.get_peer_capabilities(peer_url)
        return all(cap in peer_capabilities for cap in required_capabilities)
    
    # Message Format Conversion
    
    def convert_to_legacy_format(self, a2a_response: Dict[str, Any]) -> str:
        """
        Convert A2A response to Agent Zero's legacy JSON format.
        
        This ensures backward compatibility with existing hierarchical
        communication patterns.
        """
        try:
            # Extract main content from artifacts
            artifacts = a2a_response.get("artifacts", [])
            if artifacts:
                content_parts = []
                for artifact in artifacts:
                    if artifact.get("type") == "text/plain":
                        content_parts.append(artifact.get("content", ""))
                    elif artifact.get("type") == "application/json":
                        try:
                            json_content = json.loads(artifact.get("content", "{}"))
                            if isinstance(json_content, dict) and "message" in json_content:
                                content_parts.append(json_content["message"])
                            else:
                                content_parts.append(str(json_content))
                        except json.JSONDecodeError:
                            content_parts.append(artifact.get("content", ""))
                
                return "\n".join(content_parts) if content_parts else "No content received"
            
            # Fallback to status message
            state = a2a_response.get("state", "UNKNOWN")
            return f"Peer response (state: {state})"
            
        except Exception as e:
            return f"Error processing peer response: {str(e)}"
    
    def convert_from_legacy_format(self, legacy_message: str) -> Dict[str, Any]:
        """
        Convert Agent Zero's legacy message format to A2A format.
        
        This allows existing Agent Zero messages to be sent via A2A protocol.
        """
        return {
            "message": legacy_message,
            "format": "agent_zero_legacy",
            "converted_at": datetime.now(timezone.utc).isoformat(),
            "conversion_metadata": {
                "source": "agent_zero_hierarchical",
                "target": "a2a_protocol"
            }
        }
    
    # Private Helper Methods
    
    async def _discover_and_register_peer(self, peer_url: str):
        """Discover and register a peer agent"""
        peer_id = self._get_peer_id_from_url(peer_url)
        
        # Use handler's discovery method
        agent_card = await self.handler.discover_peer(peer_url)
        
        if agent_card:
            # Store discovered peer
            self.discovered_peers[peer_id] = agent_card
            
            # Register with handler
            self.handler.register_peer(
                peer_id=peer_id,
                agent_card=agent_card,
                base_url=peer_url,
                auth_token=self._get_auth_token_for_peer(peer_id)
            )
            
            # Add to context if context has A2A support
            if hasattr(self.context, 'add_a2a_peer'):
                self.context.add_a2a_peer(peer_id, {
                    "name": agent_card.name,
                    "description": agent_card.description,
                    "base_url": peer_url,
                    "capabilities": agent_card.capabilities
                })
        else:
            raise Exception(f"Failed to discover agent card at {peer_url}")
    
    def _get_peer_id_from_url(self, peer_url: str) -> str:
        """Generate a consistent peer ID from URL"""
        # Simple approach: use the hostname and port
        from urllib.parse import urlparse
        parsed = urlparse(peer_url)
        return f"{parsed.hostname}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}"
    
    def _get_auth_token_for_peer(self, peer_id: str) -> Optional[str]:
        """Get authentication token for a specific peer"""
        # In a real implementation, you'd look this up from secure storage
        # For now, check if it's configured in the agent config
        if hasattr(self.agent.config, 'a2a_api_keys'):
            return self.agent.config.a2a_api_keys.get(peer_id)
        return None
    
    def _update_peer_contact_time(self, peer_id: str):
        """Update the last contact time for a peer"""
        if hasattr(self.context, 'a2a_peers') and peer_id in self.context.a2a_peers:
            self.context.a2a_peers[peer_id]['last_contact'] = datetime.now(timezone.utc).isoformat()
    
    async def _send_with_polling(
        self, 
        client: A2AClient, 
        peer_url: str, 
        task_data: Dict[str, Any], 
        timeout: int
    ) -> Dict[str, Any]:
        """Send message using polling interaction pattern"""
        task_id = await client.submit_task(peer_url, task_data)
        
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout:
            status = await client.get_task_status(peer_url, task_id)
            
            if status["state"] == "COMPLETED":
                return status
            elif status["state"] == "FAILED":
                raise Exception(f"Peer task failed: {status.get('error', 'Unknown error')}")
            
            await asyncio.sleep(2)
        
        raise Exception(f"Peer communication timed out after {timeout} seconds")
    
    async def _send_with_sse(
        self, 
        client: A2AClient, 
        peer_url: str, 
        task_data: Dict[str, Any], 
        timeout: int
    ) -> Dict[str, Any]:
        """Send message using SSE interaction pattern"""
        result = await client.submit_task_with_sse(peer_url, task_data, timeout)
        return result["status"]
    
    async def _send_with_webhook(
        self, 
        client: A2AClient, 
        peer_url: str, 
        task_data: Dict[str, Any], 
        timeout: int
    ) -> Dict[str, Any]:
        """Send message using webhook interaction pattern"""
        webhook_url = self.handler.get_webhook_url()
        result = await client.submit_task_with_webhook(peer_url, task_data, webhook_url, timeout)
        return result["status"]
    
    def _format_peer_response(self, response: Dict[str, Any]) -> str:
        """Format peer response for Agent Zero consumption"""
        # Extract main content from artifacts
        artifacts = response.get("artifacts", [])
        if artifacts:
            content_parts = []
            for artifact in artifacts:
                content = artifact.get("content", "")
                if isinstance(content, dict):
                    content = json.dumps(content, indent=2)
                content_parts.append(str(content))
            
            result = "\n".join(content_parts)
        else:
            result = f"Peer task completed (state: {response.get('state', 'UNKNOWN')})"
        
        # Add metadata if available
        metadata = response.get("metadata", {})
        if metadata:
            result += f"\n\nMetadata: {json.dumps(metadata, indent=2)}"
        
        return result