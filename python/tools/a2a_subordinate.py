#!/usr/bin/env python3
"""
A2A Subordinate Tool

Enhanced subordinate agent tool that uses A2A protocol for communication.
This replaces the traditional call_subordinate with true peer-to-peer
communication between subordinate agents.
"""

import asyncio
from typing import Any, Dict, List, Optional

from agent import Agent, UserMessage
from python.helpers.tool import Tool, Response
from python.helpers.a2a_subordinate_manager import A2ASubordinateManager, SubordinateInfo
from python.helpers.print_style import PrintStyle
from python.helpers.a2a_handler import A2AError


class A2ASubordinate(Tool):
    """
    A2A-based subordinate agent tool for enhanced multi-agent collaboration.
    
    This tool spawns subordinate agents as independent A2A processes, enabling:
    - True parallel processing between agents
    - Direct user communication with subordinates
    - Peer-to-peer agent collaboration
    - Scalable multi-agent workflows
    """
    
    def __init__(self, agent: Agent, name: str, method, args: dict, message: str, loop_data: Any):
        super().__init__(agent, name, method, args, message, loop_data)
        
        # Initialize subordinate manager
        if not hasattr(self.agent.context, 'subordinate_manager'):
            self.agent.context.subordinate_manager = A2ASubordinateManager(
                agent_context=self.agent.context,
                base_port=getattr(self.agent.config, 'a2a_subordinate_base_port', 8100)
            )
        
        self.subordinate_manager = self.agent.context.subordinate_manager
    
    async def execute(
        self,
        message: str = "",
        role: str = "specialist",
        prompt_profile: str = "default",
        reset: str = "false",
        capabilities: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        timeout: int = 60,
        **kwargs
    ) -> Response:
        """
        Execute A2A subordinate communication
        
        Args:
            message: Message/task to send to subordinate
            role: Role/specialty of subordinate (e.g., 'coder', 'analyst', 'researcher')
            prompt_profile: Prompt profile to use for subordinate behavior
            reset: "true" to spawn new subordinate, "false" to use existing
            capabilities: List of capabilities the subordinate should have
            context: Additional context data to share with subordinate
            timeout: Maximum time to wait for response
        
        Returns:
            Response object with subordinate's reply
        """
        if not message.strip():
            return Response(
                message="Error: Message is required for subordinate communication",
                break_loop=False
            )
        
        try:
            # Validate A2A is enabled
            if not getattr(self.agent.config, 'a2a_enabled', False):
                return Response(
                    message="Error: A2A protocol must be enabled to use A2A subordinates. Enable a2a_enabled in agent config.",
                    break_loop=False
                )
            
            # Default capabilities based on role
            if capabilities is None:
                capabilities = self._get_default_capabilities(role)
            
            # Prepare shared context
            shared_context = {
                "parent_agent": self.agent.agent_name,
                "parent_context_id": self.agent.context.context_id,
                "conversation_history": self._get_relevant_history(),
                **(context or {})
            }
            
            # Check if we need to spawn a new subordinate
            force_new = str(reset).lower().strip() == "true"
            
            # Spawn or get existing subordinate
            subordinate = await self.subordinate_manager.spawn_subordinate(
                role=role,
                prompt_profile=prompt_profile,
                capabilities=capabilities,
                shared_context=shared_context,
                force_new=force_new
            )
            
            # Send message to subordinate
            PrintStyle(font_color="cyan").print(f"Communicating with A2A subordinate: {role}")
            
            response = await self.subordinate_manager.send_message_to_subordinate(
                role=role,
                message=message,
                context_data=shared_context,
                timeout=timeout
            )
            
            # Log the interaction
            self._log_subordinate_interaction(subordinate, message, response)
            
            return Response(
                message=response,
                break_loop=False
            )
            
        except A2AError as e:
            error_msg = f"A2A Subordinate Error: {str(e)}"
            PrintStyle(font_color="red").print(error_msg)
            return Response(message=error_msg, break_loop=False)
            
        except Exception as e:
            error_msg = f"Subordinate communication failed: {str(e)}"
            PrintStyle(font_color="red").print(error_msg)
            return Response(message=error_msg, break_loop=False)
    
    def _get_default_capabilities(self, role: str) -> List[str]:
        """Get default capabilities based on subordinate role"""
        role_capabilities = {
            "coder": ["code_execution", "file_management", "debugging", "testing"],
            "analyst": ["data_analysis", "visualization", "reporting", "statistics"],
            "researcher": ["web_search", "information_gathering", "summarization"],
            "tester": ["testing", "validation", "quality_assurance", "debugging"],
            "writer": ["content_creation", "editing", "documentation"],
            "specialist": ["task_execution", "problem_solving", "analysis"],
            "assistant": ["general_assistance", "task_execution", "communication"]
        }
        
        base_capabilities = ["task_execution", "text_processing"]
        role_specific = role_capabilities.get(role.lower(), ["specialized_task_execution"])
        
        return base_capabilities + role_specific
    
    def _get_relevant_history(self, max_messages: int = 5) -> List[Dict[str, Any]]:
        """Get relevant conversation history to share with subordinate"""
        history = []
        
        try:
            # Get recent messages from agent history
            if hasattr(self.agent, 'history') and self.agent.history:
                recent_messages = self.agent.history.get_messages()[-max_messages:]
                
                for msg in recent_messages:
                    if hasattr(msg, 'message') and msg.message:
                        history.append({
                            "role": getattr(msg, 'role', 'user'),
                            "content": msg.message[:500],  # Truncate long messages
                            "timestamp": getattr(msg, 'timestamp', None)
                        })
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Warning: Could not extract history: {str(e)}")
        
        return history
    
    def _log_subordinate_interaction(self, subordinate: SubordinateInfo, message: str, response: str):
        """Log subordinate interaction for tracking"""
        try:
            log_entry = {
                "type": "a2a_subordinate_interaction",
                "subordinate_id": subordinate.agent_id,
                "subordinate_role": subordinate.role,
                "subordinate_url": subordinate.url,
                "message_sent": message[:200] + "..." if len(message) > 200 else message,
                "response_received": response[:200] + "..." if len(response) > 200 else response,
                "timestamp": subordinate.last_contact.isoformat()
            }
            
            # Add to agent context log if available
            if hasattr(self.agent.context, 'log'):
                self.agent.context.log.log(
                    type="tool",
                    heading=f"A2A Subordinate Communication: {subordinate.role}",
                    content=f"Message: {message}\n\nResponse: {response}",
                    kvps=log_entry
                )
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Warning: Could not log interaction: {str(e)}")
    
    def get_log_object(self):
        """Get log object for tool execution"""
        subordinate_info = ""
        
        # Get subordinate information if available
        role = self.args.get("role", "specialist")
        if hasattr(self, 'subordinate_manager'):
            subordinate = self.subordinate_manager.get_subordinate_by_role(role)
            if subordinate:
                subordinate_info = f" ({subordinate.url})"
        
        return self.agent.context.log.log(
            type="tool",
            heading=f"A2A Subordinate: {role}{subordinate_info}",
            content="",
            kvps=self.args,
        )


class A2ASubordinateManager(Tool):
    """
    A2A Subordinate Management Tool
    
    Provides management capabilities for A2A subordinates including:
    - List active subordinates
    - Monitor subordinate health
    - Shutdown subordinates
    - View subordinate hierarchy
    """
    
    async def execute(
        self,
        action: str = "list",
        role: str = "",
        **kwargs
    ) -> Response:
        """
        Execute subordinate management action
        
        Args:
            action: Management action ('list', 'status', 'shutdown', 'hierarchy')
            role: Subordinate role (for role-specific actions)
        
        Returns:
            Response with management action results
        """
        if not hasattr(self.agent.context, 'subordinate_manager'):
            return Response(
                message="No subordinate manager available. Use a2a_subordinate tool first.",
                break_loop=False
            )
        
        manager = self.agent.context.subordinate_manager
        
        try:
            if action == "list":
                return await self._list_subordinates(manager)
            elif action == "status":
                return await self._subordinate_status(manager, role)
            elif action == "shutdown":
                return await self._shutdown_subordinate(manager, role)
            elif action == "hierarchy":
                return await self._show_hierarchy(manager)
            else:
                return Response(
                    message=f"Unknown action: {action}. Available: list, status, shutdown, hierarchy",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Management action failed: {str(e)}",
                break_loop=False
            )
    
    async def _list_subordinates(self, manager) -> Response:
        """List all active subordinates"""
        subordinates = manager.get_all_subordinates()
        
        if not subordinates:
            return Response(
                message="No active subordinates found.",
                break_loop=False
            )
        
        result = "Active A2A Subordinates:\n\n"
        for sub in subordinates:
            result += f"• {sub.role} ({sub.agent_id})\n"
            result += f"  URL: {sub.url}\n"
            result += f"  Status: {sub.status}\n"
            result += f"  Capabilities: {', '.join(sub.capabilities)}\n"
            result += f"  Last Contact: {sub.last_contact.strftime('%H:%M:%S')}\n\n"
        
        return Response(message=result, break_loop=False)
    
    async def _subordinate_status(self, manager, role: str) -> Response:
        """Get detailed status of a specific subordinate"""
        if not role:
            return Response(
                message="Role parameter required for status check",
                break_loop=False
            )
        
        subordinate = manager.get_subordinate_by_role(role)
        if not subordinate:
            return Response(
                message=f"No subordinate found with role: {role}",
                break_loop=False
            )
        
        result = f"Subordinate Status: {role}\n\n"
        result += f"Agent ID: {subordinate.agent_id}\n"
        result += f"URL: {subordinate.url}\n"
        result += f"Port: {subordinate.port}\n"
        result += f"Status: {subordinate.status}\n"
        result += f"Process ID: {subordinate.process_id}\n"
        result += f"Spawned: {subordinate.spawned_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"Last Contact: {subordinate.last_contact.strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"Capabilities: {', '.join(subordinate.capabilities)}\n"
        
        return Response(message=result, break_loop=False)
    
    async def _shutdown_subordinate(self, manager, role: str) -> Response:
        """Shutdown a specific subordinate"""
        if not role:
            return Response(
                message="Role parameter required for shutdown",
                break_loop=False
            )
        
        success = await manager.shutdown_subordinate(role)
        
        if success:
            return Response(
                message=f"Successfully shutdown subordinate: {role}",
                break_loop=False
            )
        else:
            return Response(
                message=f"Failed to shutdown subordinate: {role} (not found or already stopped)",
                break_loop=False
            )
    
    async def _show_hierarchy(self, manager) -> Response:
        """Show agent hierarchy"""
        hierarchy = manager.get_subordinate_hierarchy()
        
        if not hierarchy:
            return Response(
                message="No agent hierarchy found.",
                break_loop=False
            )
        
        result = "Agent Hierarchy:\n\n"
        for parent, children in hierarchy.items():
            result += f"📍 {parent}\n"
            for child in children:
                subordinate = manager.subordinates.get(child)
                if subordinate:
                    result += f"  └── {subordinate.role} ({subordinate.status})\n"
            result += "\n"
        
        return Response(message=result, break_loop=False)