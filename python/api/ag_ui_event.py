"""
AG-UI Event API Handler
Handles real-time AG-UI events from the frontend
"""

import json
import asyncio
import threading
from typing import Dict, Any, List
from flask import Flask, Request, Response

from python.helpers.api import ApiHandler
from python.helpers.ag_ui_middleware import get_global_middleware_router, ProtocolType, MiddlewareEvent
from python.helpers.ag_ui_state import get_global_state_manager
from python.helpers.ag_ui_parser import AGUIParser, AGUIEventType
from python.helpers.print_style import PrintStyle


class AGUIEvent(ApiHandler):
    """
    API handler for AG-UI events from the frontend
    """

    def __init__(self, app, thread_lock):
        super().__init__(app, thread_lock)
        self.middleware_router = get_global_middleware_router()
        self.state_manager = get_global_state_manager()
        self.parser = AGUIParser()
        self.event_queue: List[Dict[str, Any]] = []
        self.event_handlers: List[callable] = []

        # Register this handler with the middleware router
        self.middleware_router.register_event_handler(self._handle_middleware_event)
    
    @classmethod
    def requires_csrf(cls) -> bool:
        return False  # AG-UI events should flow freely
    
    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST", "GET"]  # POST for events, GET for event stream
    
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Process AG-UI event requests"""
        
        if request.method == "GET":
            # Return event stream for real-time updates
            return await self._handle_event_stream(request)
        
        elif request.method == "POST":
            # Handle incoming event from frontend
            return await self._handle_incoming_event(input, request)
    
    async def _handle_incoming_event(self, input: dict, request: Request) -> dict:
        """Handle incoming AG-UI event from frontend"""
        try:
            event_type = input.get("type", "UNKNOWN")
            component_id = input.get("componentId")
            event_data = input.get("data", {})
            timestamp = input.get("timestamp")
            
            # Log the incoming event
            PrintStyle(font_color="cyan").print(f"[AG-UI] Received event: {event_type} from {component_id}")
            
            # Validate event type
            if event_type not in [e.value for e in AGUIEventType]:
                PrintStyle(font_color="yellow").print(f"[AG-UI] Warning: Unknown event type: {event_type}")
            
            # Create middleware event
            middleware_event = MiddlewareEvent(
                source_protocol=ProtocolType.WEBSOCKET,  # Frontend events come via web
                target_protocol=ProtocolType.AGENT_ZERO_NATIVE,
                event_type=event_type,
                data={
                    "component_id": component_id,
                    "event_data": event_data,
                    "timestamp": timestamp
                },
                timestamp=self._get_timestamp(),
                metadata={
                    "source": "frontend",
                    "user_agent": request.headers.get("User-Agent", ""),
                    "ip_address": request.remote_addr
                }
            )
            
            # Process through middleware
            processed_event = await self.middleware_router.middlewares[ProtocolType.WEBSOCKET].handle_event(middleware_event)
            
            # Handle specific event types
            await self._process_event_by_type(event_type, component_id, event_data)
            
            # Add to event queue for streaming
            self.event_queue.append({
                "type": event_type,
                "component_id": component_id,
                "data": event_data,
                "timestamp": timestamp,
                "processed_at": self._get_timestamp()
            })
            
            # Limit queue size
            if len(self.event_queue) > 100:
                self.event_queue = self.event_queue[-50:]  # Keep last 50 events
            
            # Notify event handlers
            for handler in self.event_handlers:
                try:
                    await handler(middleware_event)
                except Exception as e:
                    PrintStyle(font_color="red").print(f"[AG-UI] Error in event handler: {e}")
            
            return {
                "success": True,
                "message": "Event processed successfully",
                "event_id": f"{component_id}_{timestamp}",
                "processed_at": self._get_timestamp()
            }
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"[AG-UI] Error processing event: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to process AG-UI event"
            }
    
    async def _process_event_by_type(self, event_type: str, component_id: str, event_data: dict):
        """Process events based on their type"""
        
        if event_type == "BUTTON_CLICK":
            await self._handle_button_click(component_id, event_data)
        
        elif event_type == "FORM_SUBMIT":
            await self._handle_form_submit(component_id, event_data)
        
        elif event_type == "INPUT_CHANGE":
            await self._handle_input_change(component_id, event_data)
        
        elif event_type == "MODAL_OPEN":
            await self._handle_modal_open(component_id, event_data)
        
        elif event_type == "MODAL_CLOSE":
            await self._handle_modal_close(component_id, event_data)
        
        elif event_type == "TAB_CHANGE":
            await self._handle_tab_change(component_id, event_data)
        
        elif event_type == "TABLE_ROW_SELECT":
            await self._handle_table_row_select(component_id, event_data)
        
        # Add more event type handlers as needed
    
    async def _handle_button_click(self, component_id: str, event_data: dict):
        """Handle button click events"""
        PrintStyle(font_color="green").print(f"[AG-UI] Button clicked: {component_id}")
        
        # Update component state if needed
        self.state_manager.update_component_state(component_id, {
            "last_clicked": self._get_timestamp(),
            "click_count": self.state_manager.get_component_state(component_id, {}).get("click_count", 0) + 1
        })
    
    async def _handle_form_submit(self, component_id: str, event_data: dict):
        """Handle form submission events"""
        PrintStyle(font_color="green").print(f"[AG-UI] Form submitted: {component_id}")
        
        # Store form data in state
        self.state_manager.update_component_state(component_id, {
            "last_submission": self._get_timestamp(),
            "form_data": event_data
        })
    
    async def _handle_input_change(self, component_id: str, event_data: dict):
        """Handle input change events"""
        # Update component state with new value
        self.state_manager.update_component_state(component_id, {
            "value": event_data.get("value", ""),
            "last_changed": self._get_timestamp()
        })
    
    async def _handle_modal_open(self, component_id: str, event_data: dict):
        """Handle modal open events"""
        PrintStyle(font_color="blue").print(f"[AG-UI] Modal opened: {component_id}")
        
        self.state_manager.update_component_state(component_id, {
            "is_open": True,
            "opened_at": self._get_timestamp()
        })
    
    async def _handle_modal_close(self, component_id: str, event_data: dict):
        """Handle modal close events"""
        PrintStyle(font_color="blue").print(f"[AG-UI] Modal closed: {component_id}")
        
        self.state_manager.update_component_state(component_id, {
            "is_open": False,
            "closed_at": self._get_timestamp()
        })
    
    async def _handle_tab_change(self, component_id: str, event_data: dict):
        """Handle tab change events"""
        active_tab = event_data.get("activeTab", 0)
        PrintStyle(font_color="magenta").print(f"[AG-UI] Tab changed: {component_id} -> {active_tab}")
        
        self.state_manager.update_component_state(component_id, {
            "active_tab": active_tab,
            "last_changed": self._get_timestamp()
        })
    
    async def _handle_table_row_select(self, component_id: str, event_data: dict):
        """Handle table row selection events"""
        selected_rows = event_data.get("selectedRows", [])
        PrintStyle(font_color="yellow").print(f"[AG-UI] Table rows selected: {component_id} -> {selected_rows}")
        
        self.state_manager.update_component_state(component_id, {
            "selected_rows": selected_rows,
            "last_selection": self._get_timestamp()
        })
    
    async def _handle_event_stream(self, request: Request) -> Response:
        """Handle Server-Sent Events stream for real-time updates"""
        
        def event_generator():
            """Generate Server-Sent Events"""
            yield "data: {\"type\": \"connection\", \"message\": \"AG-UI event stream connected\"}\n\n"
            
            # Send recent events
            for event in self.event_queue[-10:]:  # Last 10 events
                yield f"data: {json.dumps(event)}\n\n"
            
            # Keep connection alive and send new events
            # In a real implementation, this would use a proper event system
            # For now, we'll send a heartbeat every 30 seconds
            import time
            last_heartbeat = time.time()
            
            while True:
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    yield f"data: {{\"type\": \"heartbeat\", \"timestamp\": {int(current_time * 1000)}}}\n\n"
                    last_heartbeat = current_time
                
                time.sleep(1)  # Check every second
        
        return Response(
            event_generator(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )
    
    async def _handle_middleware_event(self, event: MiddlewareEvent):
        """Handle events from the middleware system"""
        PrintStyle(font_color="cyan").print(f"[AG-UI] Middleware event: {event.event_type}")
        
        # Add to event queue for streaming to frontend
        self.event_queue.append({
            "type": "middleware_event",
            "event_type": event.event_type,
            "source_protocol": event.source_protocol.value,
            "target_protocol": event.target_protocol.value,
            "data": event.data,
            "timestamp": event.timestamp
        })
    
    def register_event_handler(self, handler: callable):
        """Register an event handler for AG-UI events"""
        self.event_handlers.append(handler)
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        import time
        return int(time.time() * 1000)
