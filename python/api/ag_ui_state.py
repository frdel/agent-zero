"""
AG-UI State API Handler
Handles AG-UI component state management
"""

import json
import threading
from typing import Dict, Any, Optional
from flask import Flask, Request, Response

from python.helpers.api import ApiHandler
from python.helpers.ag_ui_state import get_global_state_manager
from python.helpers.print_style import PrintStyle


class AGUIState(ApiHandler):
    """
    API handler for AG-UI state management
    """

    def __init__(self, app, thread_lock):
        super().__init__(app, thread_lock)
        self.state_manager = get_global_state_manager()
    
    @classmethod
    def requires_csrf(cls) -> bool:
        return False  # State operations should flow freely
    
    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST", "GET"]
    
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Process AG-UI state requests"""
        
        action = input.get("action", "get")
        
        if action == "get":
            return await self._handle_get_state(input, request)
        
        elif action == "set":
            return await self._handle_set_state(input, request)
        
        elif action == "update":
            return await self._handle_update_state(input, request)
        
        elif action == "delete":
            return await self._handle_delete_state(input, request)
        
        elif action == "list":
            return await self._handle_list_states(input, request)
        
        elif action == "clear":
            return await self._handle_clear_states(input, request)
        
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "available_actions": ["get", "set", "update", "delete", "list", "clear"]
            }
    
    async def _handle_get_state(self, input: dict, request: Request) -> dict:
        """Get component state"""
        try:
            component_id = input.get("component_id")
            
            if not component_id:
                return {
                    "success": False,
                    "error": "component_id is required"
                }
            
            state = self.state_manager.get_component_state(component_id)
            
            PrintStyle(font_color="cyan").print(f"[AG-UI State] Retrieved state for {component_id}")
            
            return {
                "success": True,
                "component_id": component_id,
                "state": state,
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"[AG-UI State] Error getting state: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_set_state(self, input: dict, request: Request) -> dict:
        """Set component state (replaces existing state)"""
        try:
            component_id = input.get("component_id")
            state = input.get("state", {})
            
            if not component_id:
                return {
                    "success": False,
                    "error": "component_id is required"
                }
            
            self.state_manager.set_component_state(component_id, state)
            
            PrintStyle(font_color="green").print(f"[AG-UI State] Set state for {component_id}")
            
            return {
                "success": True,
                "component_id": component_id,
                "message": "State set successfully",
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"[AG-UI State] Error setting state: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_update_state(self, input: dict, request: Request) -> dict:
        """Update component state (merges with existing state)"""
        try:
            component_id = input.get("component_id")
            state_updates = input.get("state", {})
            
            if not component_id:
                return {
                    "success": False,
                    "error": "component_id is required"
                }
            
            self.state_manager.update_component_state(component_id, state_updates)
            
            PrintStyle(font_color="blue").print(f"[AG-UI State] Updated state for {component_id}")
            
            return {
                "success": True,
                "component_id": component_id,
                "message": "State updated successfully",
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"[AG-UI State] Error updating state: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_delete_state(self, input: dict, request: Request) -> dict:
        """Delete component state"""
        try:
            component_id = input.get("component_id")
            
            if not component_id:
                return {
                    "success": False,
                    "error": "component_id is required"
                }
            
            deleted = self.state_manager.delete_component_state(component_id)
            
            if deleted:
                PrintStyle(font_color="yellow").print(f"[AG-UI State] Deleted state for {component_id}")
                return {
                    "success": True,
                    "component_id": component_id,
                    "message": "State deleted successfully",
                    "timestamp": self._get_timestamp()
                }
            else:
                return {
                    "success": False,
                    "component_id": component_id,
                    "message": "Component state not found"
                }
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"[AG-UI State] Error deleting state: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_list_states(self, input: dict, request: Request) -> dict:
        """List all component states"""
        try:
            # Get optional filters
            component_prefix = input.get("component_prefix")
            include_empty = input.get("include_empty", False)
            
            all_states = self.state_manager.get_all_component_states()
            
            # Apply filters
            filtered_states = {}
            for component_id, state in all_states.items():
                # Filter by prefix if specified
                if component_prefix and not component_id.startswith(component_prefix):
                    continue
                
                # Filter empty states if requested
                if not include_empty and not state:
                    continue
                
                filtered_states[component_id] = state
            
            PrintStyle(font_color="magenta").print(f"[AG-UI State] Listed {len(filtered_states)} component states")
            
            return {
                "success": True,
                "states": filtered_states,
                "count": len(filtered_states),
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"[AG-UI State] Error listing states: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_clear_states(self, input: dict, request: Request) -> dict:
        """Clear component states"""
        try:
            component_prefix = input.get("component_prefix")
            confirm = input.get("confirm", False)
            
            if not confirm:
                return {
                    "success": False,
                    "error": "This operation requires confirmation. Set 'confirm': true",
                    "warning": "This will permanently delete component states"
                }
            
            if component_prefix:
                # Clear states with specific prefix
                cleared_count = self.state_manager.clear_component_states_by_prefix(component_prefix)
                message = f"Cleared {cleared_count} component states with prefix '{component_prefix}'"
            else:
                # Clear all states
                cleared_count = self.state_manager.clear_all_component_states()
                message = f"Cleared all {cleared_count} component states"
            
            PrintStyle(font_color="red").print(f"[AG-UI State] {message}")
            
            return {
                "success": True,
                "message": message,
                "cleared_count": cleared_count,
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"[AG-UI State] Error clearing states: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        import time
        return int(time.time() * 1000)
