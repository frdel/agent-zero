
import json
import re
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

class AGUIEventType(Enum):
    """AG-UI Protocol Event Types"""
    # Lifecycle Events
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    STEP_STARTED = "STEP_STARTED"
    STEP_FINISHED = "STEP_FINISHED"
    
    # Message Events
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"
    
    # Tool Call Events
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"
    
    # State Management Events
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"
    MESSAGES_SNAPSHOT = "MESSAGES_SNAPSHOT"
    
    # UI Events
    STRUCTURED_MESSAGE = "STRUCTURED_MESSAGE"
    DELTA_STREAMING = "DELTA_STREAMING"
    UI_CONTROL = "UI_CONTROL"
    UI_FORM_REQUEST = "UI_FORM_REQUEST"
    UI_VIEWPORT = "UI_VIEWPORT"
    
    # Component Interaction Events
    BUTTON_CLICK = "BUTTON_CLICK"
    FORM_SUBMIT = "FORM_SUBMIT"
    INPUT_CHANGE = "INPUT_CHANGE"
    INPUT_FOCUS = "INPUT_FOCUS"
    INPUT_BLUR = "INPUT_BLUR"
    
    # Modal Events
    MODAL_OPEN = "MODAL_OPEN"
    MODAL_CLOSE = "MODAL_CLOSE"
    MODAL_CONFIRM = "MODAL_CONFIRM"
    MODAL_CANCEL = "MODAL_CANCEL"
    
    # Tab Events
    TAB_CHANGE = "TAB_CHANGE"
    TAB_CLICK = "TAB_CLICK"
    
    # Table Events
    TABLE_SORT = "TABLE_SORT"
    TABLE_SEARCH = "TABLE_SEARCH"
    TABLE_ROW_CLICK = "TABLE_ROW_CLICK"
    TABLE_ROW_SELECT = "TABLE_ROW_SELECT"
    
    # List Events
    LIST_ITEM_CLICK = "LIST_ITEM_CLICK"
    LIST_ITEM_SELECT = "LIST_ITEM_SELECT"
    
    # Alert Events
    ALERT_DISMISS = "ALERT_DISMISS"
    ALERT_ACTION = "ALERT_ACTION"
    
    # Dropdown Events
    DROPDOWN_CHANGE = "DROPDOWN_CHANGE"
    DROPDOWN_OPEN = "DROPDOWN_OPEN"
    DROPDOWN_CLOSE = "DROPDOWN_CLOSE"
    
    # Checkbox/Radio Events
    CHECKBOX_CHANGE = "CHECKBOX_CHANGE"
    RADIO_CHANGE = "RADIO_CHANGE"
    
    # Slider Events
    SLIDER_CHANGE = "SLIDER_CHANGE"
    SLIDER_START = "SLIDER_START"
    SLIDER_END = "SLIDER_END"
    
    # Canvas Events
    CANVAS_NODE_CLICK = "CANVAS_NODE_CLICK"
    CANVAS_NODE_DRAG = "CANVAS_NODE_DRAG"
    CANVAS_EDGE_CLICK = "CANVAS_EDGE_CLICK"
    CANVAS_ZOOM = "CANVAS_ZOOM"
    CANVAS_PAN = "CANVAS_PAN"
    
    # Progress Events
    PROGRESS_COMPLETE = "PROGRESS_COMPLETE"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    
    # Generic Events
    COMPONENT_MOUNT = "COMPONENT_MOUNT"
    COMPONENT_UNMOUNT = "COMPONENT_UNMOUNT"
    COMPONENT_UPDATE = "COMPONENT_UPDATE"
    
    # Validation Events
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_SUCCESS = "VALIDATION_SUCCESS"

class AGUIMessageType(Enum):
    """AG-UI Message Types"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    DEVELOPER = "developer"

@dataclass
class AGUIBaseEvent:
    """Base AG-UI Event Structure"""
    type: AGUIEventType
    timestamp: Optional[int] = None
    raw_event: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = int(datetime.now().timestamp() * 1000)

@dataclass
class AGUIMessage:
    """AG-UI Message Structure"""
    id: str
    type: AGUIMessageType
    content: str
    timestamp: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = int(datetime.now().timestamp() * 1000)

@dataclass
class AGUIToolDefinition:
    """AG-UI Tool Definition"""
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str] = field(default_factory=list)

@dataclass
class AGUIComponent:
    """AG-UI Component Structure"""
    type: str
    properties: Dict[str, Any]
    id: Optional[str] = None
    children: List['AGUIComponent'] = field(default_factory=list)
    events: Dict[str, str] = field(default_factory=dict)
    
class AGUIParser:
    """AG-UI Protocol Parser"""
    
    def __init__(self):
        self.supported_events = set(event.value for event in AGUIEventType)
        self.supported_message_types = set(msg_type.value for msg_type in AGUIMessageType)
    
    def parse_event(self, event_data: Union[str, Dict[str, Any]]) -> AGUIBaseEvent:
        """Parse AG-UI event from JSON string or dictionary"""
        if isinstance(event_data, str):
            try:
                event_dict = json.loads(event_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in event data: {e}")
        else:
            event_dict = event_data
        
        event_type_str = event_dict.get('type')
        if not event_type_str:
            raise ValueError("Event type is required")
        
        if event_type_str not in self.supported_events:
            raise ValueError(f"Unsupported event type: {event_type_str}")
        
        event_type = AGUIEventType(event_type_str)
        
        return AGUIBaseEvent(
            type=event_type,
            timestamp=event_dict.get('timestamp'),
            raw_event=event_dict
        )
    
    def parse_message(self, message_data: Union[str, Dict[str, Any]]) -> AGUIMessage:
        """Parse AG-UI message from JSON string or dictionary"""
        if isinstance(message_data, str):
            try:
                message_dict = json.loads(message_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in message data: {e}")
        else:
            message_dict = message_data
        
        message_id = message_dict.get('id')
        if not message_id:
            raise ValueError("Message ID is required")
        
        message_type_str = message_dict.get('type')
        if not message_type_str:
            raise ValueError("Message type is required")
        
        if message_type_str not in self.supported_message_types:
            raise ValueError(f"Unsupported message type: {message_type_str}")
        
        message_type = AGUIMessageType(message_type_str)
        
        content = message_dict.get('content', '')
        
        return AGUIMessage(
            id=message_id,
            type=message_type,
            content=content,
            timestamp=message_dict.get('timestamp'),
            metadata=message_dict.get('metadata', {})
        )
    
    def parse_component(self, component_data: Union[str, Dict[str, Any]]) -> AGUIComponent:
        """Parse AG-UI component from JSON string or dictionary"""
        if isinstance(component_data, str):
            try:
                component_dict = json.loads(component_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in component data: {e}")
        else:
            component_dict = component_data

        component_type = component_dict.get('type')
        if not component_type:
            raise ValueError("Component type is required")

        properties = component_dict.get('properties', {})

        component = AGUIComponent(
            type=component_type,
            properties=properties,
            id=component_dict.get('id'),
            events=component_dict.get('events', {})
        )

        # Parse children recursively from the children array
        children_data = component_dict.get('children', [])
        for child_data in children_data:
            child_component = self.parse_component(child_data)
            component.children.append(child_component)

        # Also check for children in properties (for backward compatibility)
        # and move them to the children array
        children_in_props = properties.get('children', [])
        if children_in_props and isinstance(children_in_props, list):
            for child_data in children_in_props:
                if isinstance(child_data, dict):
                    try:
                        child_component = self.parse_component(child_data)
                        component.children.append(child_component)
                    except Exception as e:
                        # Create a warning but continue processing other children
                        import warnings
                        warnings.warn(f"Failed to parse child component in properties: {e}")

            # Remove children from properties to avoid double processing
            properties = dict(properties)  # Create a copy
            del properties['children']
            component.properties = properties

        return component
    
    def parse_tool_definition(self, tool_data: Union[str, Dict[str, Any]]) -> AGUIToolDefinition:
        """Parse AG-UI tool definition from JSON string or dictionary"""
        if isinstance(tool_data, str):
            try:
                tool_dict = json.loads(tool_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in tool data: {e}")
        else:
            tool_dict = tool_data
        
        name = tool_dict.get('name')
        if not name:
            raise ValueError("Tool name is required")
        
        description = tool_dict.get('description', '')
        parameters = tool_dict.get('parameters', {})
        required = tool_dict.get('required', [])
        
        return AGUIToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            required=required
        )
    
    def parse_spec(self, spec_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse full AG-UI specification"""
        if isinstance(spec_data, str):
            try:
                spec_dict = json.loads(spec_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in specification: {e}")
        else:
            spec_dict = spec_data
        
        parsed_spec = {
            'events': [],
            'messages': [],
            'components': [],
            'tools': [],
            'metadata': spec_dict.get('metadata', {})
        }
        
        # Parse events
        events_data = spec_dict.get('events', [])
        for event_data in events_data:
            parsed_event = self.parse_event(event_data)
            parsed_spec['events'].append(parsed_event)
        
        # Parse messages
        messages_data = spec_dict.get('messages', [])
        for message_data in messages_data:
            parsed_message = self.parse_message(message_data)
            parsed_spec['messages'].append(parsed_message)
        
        # Parse components
        components_data = spec_dict.get('components', [])
        for component_data in components_data:
            parsed_component = self.parse_component(component_data)
            parsed_spec['components'].append(parsed_component)
        
        # Parse tools
        tools_data = spec_dict.get('tools', [])
        for tool_data in tools_data:
            parsed_tool = self.parse_tool_definition(tool_data)
            parsed_spec['tools'].append(parsed_tool)
        
        return parsed_spec
    
    def serialize_event(self, event: AGUIBaseEvent) -> Dict[str, Any]:
        """Serialize AG-UI event to dictionary"""
        return {
            'type': event.type.value,
            'timestamp': event.timestamp,
            'raw_event': event.raw_event
        }
    
    def serialize_message(self, message: AGUIMessage) -> Dict[str, Any]:
        """Serialize AG-UI message to dictionary"""
        return {
            'id': message.id,
            'type': message.type.value,
            'content': message.content,
            'timestamp': message.timestamp,
            'metadata': message.metadata
        }
    
    def serialize_component(self, component: AGUIComponent) -> Dict[str, Any]:
        """Serialize AG-UI component to dictionary"""
        return {
            'type': component.type,
            'properties': component.properties,
            'id': component.id,
            'events': component.events,
            'children': [self.serialize_component(child) for child in component.children]
        }
