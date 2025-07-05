
import re
import html
from typing import Dict, List, Optional, Any, Union
from .ag_ui_parser import AGUIParser, AGUIBaseEvent, AGUIMessage, AGUIComponent, AGUIToolDefinition

class AGUIValidationError(Exception):
    """Custom exception for AG-UI validation errors"""
    pass

class AGUIValidator:
    """AG-UI Protocol Validator"""
    
    # Security patterns to block potentially malicious content
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript URLs
        r'on\w+\s*=',  # Event handlers
        r'<iframe[^>]*>',  # IFrames
        r'<object[^>]*>',  # Objects
        r'<embed[^>]*>',  # Embeds
        r'<link[^>]*>',  # Links that could load external resources
        r'<form[^>]*action\s*=\s*["\']?(?!#)[^"\'>]*',  # Forms with external actions
    ]
    
    # Allowed HTML tags for component content
    ALLOWED_HTML_TAGS = {
        'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'u',
        'br', 'hr', 'img', 'a', 'button', 'input', 'textarea',
        'select', 'option', 'label', 'table', 'tr', 'td', 'th',
        'thead', 'tbody', 'tfoot', 'pre', 'code', 'blockquote'
    }
    
    # Allowed attributes for HTML tags
    ALLOWED_ATTRIBUTES = {
        'class', 'id', 'style', 'title', 'alt', 'src', 'href',
        'type', 'name', 'value', 'placeholder', 'disabled',
        'readonly', 'required', 'checked', 'selected', 'multiple',
        'rows', 'cols', 'maxlength', 'min', 'max', 'step',
        'x-data', 'x-show', 'x-if', 'x-for', 'x-bind', 'x-on',
        '@click', '@change', '@input', '@submit', '@focus', '@blur'
    }
    
    # Maximum lengths for various fields
    MAX_LENGTHS = {
        'component_id': 100,
        'component_type': 50,
        'property_key': 50,
        'property_value': 10000,
        'message_id': 100,
        'message_content': 1000000,  # 1MB
        'tool_name': 100,
        'tool_description': 500
    }
    
    def __init__(self):
        self.parser = AGUIParser()
        self.dangerous_regex = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in self.DANGEROUS_PATTERNS]
    
    def validate_event(self, event: AGUIBaseEvent) -> bool:
        """Validate AG-UI event"""
        if not event.type:
            raise AGUIValidationError("Event type is required")
        
        if event.timestamp and not isinstance(event.timestamp, int):
            raise AGUIValidationError("Event timestamp must be an integer")
        
        if event.raw_event and not isinstance(event.raw_event, dict):
            raise AGUIValidationError("Event raw_event must be a dictionary")
        
        return True
    
    def validate_message(self, message: AGUIMessage) -> bool:
        """Validate AG-UI message"""
        if not message.id:
            raise AGUIValidationError("Message ID is required")
        
        if len(message.id) > self.MAX_LENGTHS['message_id']:
            raise AGUIValidationError(f"Message ID too long (max {self.MAX_LENGTHS['message_id']} characters)")
        
        if not message.type:
            raise AGUIValidationError("Message type is required")
        
        if len(message.content) > self.MAX_LENGTHS['message_content']:
            raise AGUIValidationError(f"Message content too long (max {self.MAX_LENGTHS['message_content']} characters)")
        
        # Validate content for dangerous patterns
        self._validate_content_security(message.content)
        
        if message.timestamp and not isinstance(message.timestamp, int):
            raise AGUIValidationError("Message timestamp must be an integer")
        
        if not isinstance(message.metadata, dict):
            raise AGUIValidationError("Message metadata must be a dictionary")
        
        return True
    
    def validate_component(self, component: AGUIComponent) -> bool:
        """Validate AG-UI component"""
        if not component.type:
            raise AGUIValidationError("Component type is required")
        
        if len(component.type) > self.MAX_LENGTHS['component_type']:
            raise AGUIValidationError(f"Component type too long (max {self.MAX_LENGTHS['component_type']} characters)")
        
        if component.id and len(component.id) > self.MAX_LENGTHS['component_id']:
            raise AGUIValidationError(f"Component ID too long (max {self.MAX_LENGTHS['component_id']} characters)")
        
        if not isinstance(component.properties, dict):
            raise AGUIValidationError("Component properties must be a dictionary")
        
        # Validate properties
        self._validate_properties(component.properties)
        
        if not isinstance(component.events, dict):
            raise AGUIValidationError("Component events must be a dictionary")
        
        # Validate children recursively
        if not isinstance(component.children, list):
            raise AGUIValidationError("Component children must be a list")
        
        for child in component.children:
            self.validate_component(child)
        
        return True
    
    def validate_tool_definition(self, tool: AGUIToolDefinition) -> bool:
        """Validate AG-UI tool definition"""
        if not tool.name:
            raise AGUIValidationError("Tool name is required")
        
        if len(tool.name) > self.MAX_LENGTHS['tool_name']:
            raise AGUIValidationError(f"Tool name too long (max {self.MAX_LENGTHS['tool_name']} characters)")
        
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', tool.name):
            raise AGUIValidationError("Tool name must be a valid identifier")
        
        if len(tool.description) > self.MAX_LENGTHS['tool_description']:
            raise AGUIValidationError(f"Tool description too long (max {self.MAX_LENGTHS['tool_description']} characters)")
        
        if not isinstance(tool.parameters, dict):
            raise AGUIValidationError("Tool parameters must be a dictionary")
        
        if not isinstance(tool.required, list):
            raise AGUIValidationError("Tool required fields must be a list")
        
        # Validate required fields exist in parameters
        for required_field in tool.required:
            if required_field not in tool.parameters:
                raise AGUIValidationError(f"Required field '{required_field}' not found in tool parameters")
        
        return True
    
    def _validate_properties(self, properties: Dict[str, Any]) -> None:
        """Validate component properties"""
        for key, value in properties.items():
            if len(key) > self.MAX_LENGTHS['property_key']:
                raise AGUIValidationError(f"Property key too long (max {self.MAX_LENGTHS['property_key']} characters)")
            
            if isinstance(value, str):
                if len(value) > self.MAX_LENGTHS['property_value']:
                    raise AGUIValidationError(f"Property value too long (max {self.MAX_LENGTHS['property_value']} characters)")
                
                # Validate string content for security
                self._validate_content_security(value)
            elif isinstance(value, dict):
                # Recursively validate nested properties
                self._validate_properties(value)
            elif isinstance(value, list):
                # Validate list items
                for item in value:
                    if isinstance(item, str):
                        self._validate_content_security(item)
                    elif isinstance(item, dict):
                        self._validate_properties(item)
    
    def _validate_content_security(self, content: str) -> None:
        """Validate content for security issues"""
        # Check for dangerous patterns
        for pattern in self.dangerous_regex:
            if pattern.search(content):
                raise AGUIValidationError(f"Potentially dangerous content detected: {pattern.pattern}")
        
        # Additional validation for HTML content
        if '<' in content and '>' in content:
            self._validate_html_content(content)
    
    def _validate_html_content(self, content: str) -> None:
        """Validate HTML content for allowed tags and attributes"""
        # Extract tags from content
        tag_pattern = r'<(/?)([a-zA-Z0-9]+)([^>]*)>'
        tags = re.findall(tag_pattern, content)
        
        for closing, tag_name, attributes in tags:
            if tag_name.lower() not in self.ALLOWED_HTML_TAGS:
                raise AGUIValidationError(f"HTML tag '{tag_name}' is not allowed")
            
            # Validate attributes
            if attributes:
                attr_pattern = r'(\w+)\s*=\s*["\']?([^"\'>]*)["\']?'
                attrs = re.findall(attr_pattern, attributes)
                
                for attr_name, attr_value in attrs:
                    if attr_name.lower() not in self.ALLOWED_ATTRIBUTES:
                        raise AGUIValidationError(f"HTML attribute '{attr_name}' is not allowed")
                    
                    # Validate attribute values
                    if attr_name.lower() in ['href', 'src'] and attr_value:
                        if not self._is_safe_url(attr_value):
                            raise AGUIValidationError(f"Unsafe URL in {attr_name}: {attr_value}")
    
    def _is_safe_url(self, url: str) -> bool:
        """Check if URL is safe (no javascript: or data: schemes)"""
        url_lower = url.lower().strip()
        
        # Block dangerous URL schemes
        dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:', 'ftp:']
        for scheme in dangerous_schemes:
            if url_lower.startswith(scheme):
                return False
        
        return True
    
    def sanitize_content(self, content: str) -> str:
        """Sanitize content by escaping HTML entities"""
        return html.escape(content, quote=True)
    
    def validate_spec(self, spec: Dict[str, Any]) -> bool:
        """Validate complete AG-UI specification"""
        if not isinstance(spec, dict):
            raise AGUIValidationError("Specification must be a dictionary")
        
        # Validate events
        if 'events' in spec:
            if not isinstance(spec['events'], list):
                raise AGUIValidationError("Specification events must be a list")
            
            for event in spec['events']:
                if isinstance(event, dict):
                    parsed_event = self.parser.parse_event(event)
                    self.validate_event(parsed_event)
                else:
                    self.validate_event(event)
        
        # Validate messages
        if 'messages' in spec:
            if not isinstance(spec['messages'], list):
                raise AGUIValidationError("Specification messages must be a list")
            
            for message in spec['messages']:
                if isinstance(message, dict):
                    parsed_message = self.parser.parse_message(message)
                    self.validate_message(parsed_message)
                else:
                    self.validate_message(message)
        
        # Validate components
        if 'components' in spec:
            if not isinstance(spec['components'], list):
                raise AGUIValidationError("Specification components must be a list")
            
            for component in spec['components']:
                if isinstance(component, dict):
                    parsed_component = self.parser.parse_component(component)
                    self.validate_component(parsed_component)
                else:
                    self.validate_component(component)
        
        # Validate tools
        if 'tools' in spec:
            if not isinstance(spec['tools'], list):
                raise AGUIValidationError("Specification tools must be a list")
            
            for tool in spec['tools']:
                if isinstance(tool, dict):
                    parsed_tool = self.parser.parse_tool_definition(tool)
                    self.validate_tool_definition(parsed_tool)
                else:
                    self.validate_tool_definition(tool)
        
        return True
    
    def validate_and_sanitize(self, content: str) -> str:
        """Validate content and return sanitized version"""
        try:
            self._validate_content_security(content)
            return content  # Content is safe, return as-is
        except AGUIValidationError:
            # Content has security issues, return sanitized version
            return self.sanitize_content(content)
