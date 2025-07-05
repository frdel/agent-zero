"""
AG-UI Middleware System
Translates between different protocols and Agent Zero's native system
"""

import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

from python.helpers.ag_ui_parser import AGUIParser, AGUIEventType
from python.helpers.ag_ui_validator import AGUIValidator
from python.helpers.ag_ui_state import AGUIStateManager, get_global_state_manager


class ProtocolType(Enum):
    """Supported protocol types for middleware translation"""
    AGENT_ZERO_NATIVE = "agent_zero_native"
    OPENAI_FUNCTIONS = "openai_functions"
    ANTHROPIC_TOOLS = "anthropic_tools"
    GENERIC_REST = "generic_rest"
    WEBSOCKET = "websocket"


@dataclass
class MiddlewareEvent:
    """Represents an event passing through middleware"""
    source_protocol: ProtocolType
    target_protocol: ProtocolType
    event_type: str
    data: Dict[str, Any]
    timestamp: int
    metadata: Dict[str, Any]


class AbstractMiddleware(ABC):
    """Abstract base class for AG-UI middleware components"""
    
    def __init__(self, source_protocol: ProtocolType, target_protocol: ProtocolType):
        self.source_protocol = source_protocol
        self.target_protocol = target_protocol
        self.parser = AGUIParser()
        self.validator = AGUIValidator()
        self.state_manager = get_global_state_manager()
        
    @abstractmethod
    async def translate_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate incoming request to AG-UI format"""
        pass
    
    @abstractmethod
    async def translate_response(self, ag_ui_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate AG-UI response to target protocol format"""
        pass
    
    @abstractmethod
    async def handle_event(self, event: MiddlewareEvent) -> Optional[MiddlewareEvent]:
        """Handle and potentially transform middleware events"""
        pass


class AgentZeroMiddleware(AbstractMiddleware):
    """Middleware for Agent Zero native protocol integration"""
    
    def __init__(self):
        super().__init__(ProtocolType.AGENT_ZERO_NATIVE, ProtocolType.AGENT_ZERO_NATIVE)
        
    async def translate_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate Agent Zero request to AG-UI format"""
        # Agent Zero requests are already in a compatible format
        ag_ui_request = {
            "type": "TOOL_CALL_START",
            "tool_name": "ag_ui_tool",
            "args": request_data.get("args", {}),
            "metadata": {
                "agent_id": request_data.get("agent_id", "agent_zero"),
                "timestamp": self._get_timestamp(),
                "protocol": "agent_zero_native"
            }
        }
        
        return ag_ui_request
    
    async def translate_response(self, ag_ui_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate AG-UI response to Agent Zero format"""
        return {
            "status": "success" if ag_ui_data.get("type") != "RUN_ERROR" else "error",
            "content": ag_ui_data.get("ui_components", ""),
            "message_type": "ag_ui",
            "metadata": ag_ui_data.get("agent_metadata", {}),
            "timestamp": ag_ui_data.get("timestamp", self._get_timestamp())
        }
    
    async def handle_event(self, event: MiddlewareEvent) -> Optional[MiddlewareEvent]:
        """Handle Agent Zero specific events"""
        # Pass through events with minimal processing
        return event


class OpenAIMiddleware(AbstractMiddleware):
    """Middleware for OpenAI Functions integration"""
    
    def __init__(self):
        super().__init__(ProtocolType.OPENAI_FUNCTIONS, ProtocolType.AGENT_ZERO_NATIVE)
        
    async def translate_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate OpenAI function call to AG-UI format"""
        function_call = request_data.get("function_call", {})
        function_name = function_call.get("name", "")
        
        if function_name == "create_ui_component":
            arguments = json.loads(function_call.get("arguments", "{}"))
            
            ag_ui_request = {
                "type": "UI_CONTROL",
                "component_spec": arguments.get("component_spec", {}),
                "metadata": {
                    "source": "openai_functions",
                    "function_name": function_name,
                    "timestamp": self._get_timestamp()
                }
            }
            
            return ag_ui_request
        
        # Default handling for other function calls
        return {
            "type": "TOOL_CALL_START",
            "tool_name": function_name,
            "args": json.loads(function_call.get("arguments", "{}")),
            "metadata": {"source": "openai_functions"}
        }
    
    async def translate_response(self, ag_ui_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate AG-UI response to OpenAI function response format"""
        return {
            "role": "function",
            "name": "create_ui_component",
            "content": json.dumps({
                "status": "success",
                "ui_components": ag_ui_data.get("ui_components", ""),
                "component_id": ag_ui_data.get("component_id"),
                "timestamp": ag_ui_data.get("timestamp")
            })
        }
    
    async def handle_event(self, event: MiddlewareEvent) -> Optional[MiddlewareEvent]:
        """Handle OpenAI specific events"""
        # Transform OpenAI events to AG-UI events
        if event.event_type == "function_call":
            return MiddlewareEvent(
                source_protocol=ProtocolType.OPENAI_FUNCTIONS,
                target_protocol=ProtocolType.AGENT_ZERO_NATIVE,
                event_type="TOOL_CALL_START",
                data=await self.translate_request(event.data),
                timestamp=self._get_timestamp(),
                metadata=event.metadata
            )
        
        return event


class WebSocketMiddleware(AbstractMiddleware):
    """Middleware for WebSocket real-time communication"""
    
    def __init__(self):
        super().__init__(ProtocolType.WEBSOCKET, ProtocolType.AGENT_ZERO_NATIVE)
        self.connections: List[Any] = []
        
    async def translate_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate WebSocket message to AG-UI format"""
        ws_message = request_data.get("message", {})
        
        return {
            "type": ws_message.get("type", "UI_CONTROL"),
            "data": ws_message.get("data", {}),
            "metadata": {
                "source": "websocket",
                "connection_id": request_data.get("connection_id"),
                "timestamp": self._get_timestamp()
            }
        }
    
    async def translate_response(self, ag_ui_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate AG-UI response to WebSocket message format"""
        return {
            "type": "ag_ui_response",
            "data": {
                "ui_components": ag_ui_data.get("ui_components", ""),
                "event_type": ag_ui_data.get("type", "UI_UPDATE"),
                "timestamp": ag_ui_data.get("timestamp")
            },
            "metadata": ag_ui_data.get("metadata", {})
        }
    
    async def handle_event(self, event: MiddlewareEvent) -> Optional[MiddlewareEvent]:
        """Handle WebSocket specific events"""
        # Broadcast to all connected WebSocket clients
        if event.event_type in ["STATE_DELTA", "UI_UPDATE"]:
            await self._broadcast_to_websockets(event.data)
        
        return event
    
    async def _broadcast_to_websockets(self, data: Dict[str, Any]):
        """Broadcast data to all connected WebSocket clients"""
        if not self.connections:
            return

        # Create broadcast event
        broadcast_event = MiddlewareEvent(
            source_protocol=ProtocolType.AGENT_ZERO_NATIVE,
            target_protocol=ProtocolType.WEBSOCKET,
            event_type="BROADCAST",
            data=data,
            timestamp=self._get_timestamp(),
            metadata={"connection_count": len(self.connections)}
        )

        # Emit to event streams (this will reach the frontend via Server-Sent Events)
        if hasattr(self, '_event_streams'):
            for event_queue in self._event_streams[:]:
                try:
                    event_queue.put_nowait(broadcast_event)
                except asyncio.QueueFull:
                    print(f"Warning: WebSocket event queue full, skipping broadcast")
                except Exception as e:
                    print(f"Error broadcasting to WebSocket stream: {e}")

        print(f"[AG-UI] Broadcasted to {len(self.connections)} WebSocket clients and {len(getattr(self, '_event_streams', []))} event streams")

    def add_connection(self, connection):
        """Add a WebSocket connection"""
        self.connections.append(connection)
        print(f"[AG-UI] WebSocket connection added. Total: {len(self.connections)}")

    def remove_connection(self, connection):
        """Remove a WebSocket connection"""
        if connection in self.connections:
            self.connections.remove(connection)
            print(f"[AG-UI] WebSocket connection removed. Total: {len(self.connections)}")

    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        import time
        return int(time.time() * 1000)


class MiddlewareRouter:
    """Routes requests through appropriate middleware based on protocol"""
    
    def __init__(self):
        self.middlewares: Dict[ProtocolType, AbstractMiddleware] = {}
        self.event_handlers: List[Callable] = []
        self.state_manager = get_global_state_manager()
        
        # Register default middlewares
        self.register_middleware(AgentZeroMiddleware())
        self.register_middleware(OpenAIMiddleware())
        self.register_middleware(WebSocketMiddleware())
    
    def register_middleware(self, middleware: AbstractMiddleware):
        """Register a middleware for a specific protocol"""
        self.middlewares[middleware.source_protocol] = middleware
    
    def register_event_handler(self, handler: Callable):
        """Register an event handler for middleware events"""
        self.event_handlers.append(handler)
    
    async def process_request(self, request_data: Dict[str, Any], source_protocol: ProtocolType) -> Dict[str, Any]:
        """Process request through appropriate middleware"""
        middleware = self.middlewares.get(source_protocol)
        if not middleware:
            raise ValueError(f"No middleware registered for protocol: {source_protocol}")
        
        # Translate request to AG-UI format
        ag_ui_request = await middleware.translate_request(request_data)
        
        # Emit middleware event
        event = MiddlewareEvent(
            source_protocol=source_protocol,
            target_protocol=ProtocolType.AGENT_ZERO_NATIVE,
            event_type="REQUEST_PROCESSED",
            data=ag_ui_request,
            timestamp=self._get_timestamp(),
            metadata={"middleware": middleware.__class__.__name__}
        )
        
        await self._emit_event(event)
        
        return ag_ui_request
    
    async def process_response(self, ag_ui_data: Dict[str, Any], target_protocol: ProtocolType) -> Dict[str, Any]:
        """Process response through appropriate middleware"""
        middleware = self.middlewares.get(target_protocol)
        if not middleware:
            raise ValueError(f"No middleware registered for protocol: {target_protocol}")
        
        # Translate AG-UI response to target format
        response = await middleware.translate_response(ag_ui_data)
        
        # Emit middleware event
        event = MiddlewareEvent(
            source_protocol=ProtocolType.AGENT_ZERO_NATIVE,
            target_protocol=target_protocol,
            event_type="RESPONSE_PROCESSED",
            data=response,
            timestamp=self._get_timestamp(),
            metadata={"middleware": middleware.__class__.__name__}
        )
        
        await self._emit_event(event)
        
        return response
    
    async def stream_events(self, source_protocol: ProtocolType) -> AsyncGenerator[MiddlewareEvent, None]:
        """Stream real events from a specific protocol middleware"""
        middleware = self.middlewares.get(source_protocol)
        if not middleware:
            return

        # Initialize real event streaming
        event_queue = asyncio.Queue()

        # Register this stream with the middleware
        if not hasattr(middleware, '_event_streams'):
            middleware._event_streams = []
        middleware._event_streams.append(event_queue)

        try:
            # Send initial connection event
            initial_event = MiddlewareEvent(
                source_protocol=source_protocol,
                target_protocol=ProtocolType.AGENT_ZERO_NATIVE,
                event_type="STREAM_START",
                data={"message": "Real event stream started", "protocol": source_protocol.value},
                timestamp=self._get_timestamp(),
                metadata={"stream_id": id(event_queue)}
            )
            yield initial_event

            # Stream real events from the queue
            while True:
                try:
                    # Wait for events with timeout to allow cleanup
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    heartbeat_event = MiddlewareEvent(
                        source_protocol=source_protocol,
                        target_protocol=ProtocolType.AGENT_ZERO_NATIVE,
                        event_type="HEARTBEAT",
                        data={"timestamp": self._get_timestamp()},
                        timestamp=self._get_timestamp(),
                        metadata={}
                    )
                    yield heartbeat_event

        except Exception as e:
            # Send error event and cleanup
            error_event = MiddlewareEvent(
                source_protocol=source_protocol,
                target_protocol=ProtocolType.AGENT_ZERO_NATIVE,
                event_type="STREAM_ERROR",
                data={"error": str(e)},
                timestamp=self._get_timestamp(),
                metadata={}
            )
            yield error_event
        finally:
            # Cleanup: remove this stream from middleware
            if hasattr(middleware, '_event_streams') and event_queue in middleware._event_streams:
                middleware._event_streams.remove(event_queue)
    
    async def _emit_event(self, event: MiddlewareEvent):
        """Emit event to all registered handlers and active streams"""
        # Emit to registered handlers
        for handler in self.event_handlers:
            try:
                await handler(event)
            except Exception as e:
                print(f"Error in middleware event handler: {e}")

        # Emit to active event streams
        await self._emit_to_streams(event)

    async def _emit_to_streams(self, event: MiddlewareEvent):
        """Emit event to all active event streams"""
        for middleware in self.middlewares.values():
            if hasattr(middleware, '_event_streams'):
                for event_queue in middleware._event_streams[:]:  # Copy list to avoid modification during iteration
                    try:
                        # Non-blocking put - if queue is full, skip this stream
                        event_queue.put_nowait(event)
                    except asyncio.QueueFull:
                        print(f"Warning: Event queue full for {middleware.__class__.__name__}, skipping event")
                    except Exception as e:
                        print(f"Error emitting to event stream: {e}")
                        # Remove broken stream
                        try:
                            middleware._event_streams.remove(event_queue)
                        except ValueError:
                            pass  # Already removed

    def emit_event_sync(self, event: MiddlewareEvent):
        """Synchronous wrapper for emitting events"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, schedule the coroutine
                asyncio.create_task(self._emit_event(event))
            else:
                # If no loop is running, run it
                loop.run_until_complete(self._emit_event(event))
        except Exception as e:
            print(f"Error in sync event emission: {e}")
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        import time
        return int(time.time() * 1000)


# Global middleware router instance
_global_middleware_router = None


def get_global_middleware_router() -> MiddlewareRouter:
    """Get or create global middleware router instance"""
    global _global_middleware_router
    if _global_middleware_router is None:
        _global_middleware_router = MiddlewareRouter()
    return _global_middleware_router


async def process_external_request(request_data: Dict[str, Any], protocol: str = "agent_zero_native") -> Dict[str, Any]:
    """Process external request through middleware system"""
    protocol_type = ProtocolType(protocol)
    router = get_global_middleware_router()
    return await router.process_request(request_data, protocol_type)


async def process_ag_ui_response(ag_ui_data: Dict[str, Any], target_protocol: str = "agent_zero_native") -> Dict[str, Any]:
    """Process AG-UI response through middleware system"""
    protocol_type = ProtocolType(target_protocol)
    router = get_global_middleware_router()
    return await router.process_response(ag_ui_data, protocol_type)