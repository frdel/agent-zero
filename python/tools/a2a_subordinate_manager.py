#!/usr/bin/env python3
"""
A2A Subordinate Management Tool

Provides management capabilities for A2A subordinates including:
- List active subordinates
- Monitor subordinate health  
- Shutdown subordinates
- View subordinate hierarchy
"""

from typing import Any

from agent import Agent
from python.helpers.tool import Tool, Response


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
    
    def get_log_object(self):
        """Get log object for tool execution"""
        action = self.args.get("action", "list")
        role = self.args.get("role", "")
        
        heading = f"A2A Subordinate Manager: {action}"
        if role:
            heading += f" ({role})"
        
        return self.agent.context.log.log(
            type="tool",
            heading=heading,
            content="",
            kvps=self.args,
        )