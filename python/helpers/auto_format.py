import re
import json
from typing import Optional, Dict, Any
from python.helpers import dirty_json


def detect_misformat(response: str) -> bool:
    """
    Detect if a response needs auto-formatting.
    Returns True if the response appears to be malformed JSON or plain text.
    """
    if not response or not isinstance(response, str):
        return False
    
    # Try to parse as JSON first
    try:
        parsed = dirty_json.try_parse(response.strip())
        if parsed is None:
            return True
        
        # Check if it has the required structure
        if isinstance(parsed, dict):
            has_tool_name = "tool_name" in parsed
            has_tool_args = "tool_args" in parsed
            has_thoughts = "thoughts" in parsed
            
            # If it has some of the required fields, it's probably not misformatted
            if has_tool_name or (has_tool_args and has_thoughts):
                return False
        
        # If we get here, it's probably misformatted
        return True
        
    except Exception:
        # Failed to parse, definitely misformatted
        return True


def extract_components(response: str) -> Dict[str, Any]:
    """
    Extract potential tool usage components from text response.
    Returns a dict with extracted thoughts, tool_name, and tool_args.
    """
    components = {
        "thoughts": [],
        "tool_name": "response",
        "tool_args": {"text": response.strip()}
    }
    
    # Try to extract tool usage patterns
    tool_patterns = [
        r'tool[_\s]*name[:\s]*["\']?(\w+)["\']?',
        r'using[_\s]*tool[:\s]*["\']?(\w+)["\']?',
        r'call[_\s]*tool[:\s]*["\']?(\w+)["\']?',
        r'execute[_\s]*tool[:\s]*["\']?(\w+)["\']?',
    ]
    
    response_lower = response.lower()
    for pattern in tool_patterns:
        match = re.search(pattern, response_lower)
        if match:
            components["tool_name"] = match.group(1)
            break
    
    # Try to extract thoughts or reasoning
    thought_patterns = [
        r'(?:i\s+(?:think|believe|need|will|should|want)|let\s+me|first|next|now)\s+(.+?)(?:\.|$)',
        r'(?:thoughts?|reasoning|analysis)[:\s]+(.+?)(?:\n|$)',
        r'^(.+?)(?:using|calling|executing|with)\s+(?:tool|function)',
    ]
    
    for pattern in thought_patterns:
        matches = re.findall(pattern, response, re.IGNORECASE | re.MULTILINE)
        if matches:
            components["thoughts"].extend([match.strip() for match in matches[:3]])
            break
    
    # If no specific thoughts found, use first sentence as thought
    if not components["thoughts"]:
        sentences = re.split(r'[.!?]+', response.strip())
        if sentences and sentences[0].strip():
            components["thoughts"] = [sentences[0].strip()]
        else:
            components["thoughts"] = ["Converting unformatted response to proper JSON structure"]
    
    return components


def auto_format_response(response: str) -> Optional[str]:
    """
    Attempt to auto-format a malformed response into proper JSON.
    Returns the formatted JSON string or None if formatting fails.
    """
    if not response or not isinstance(response, str):
        return None
    
    try:
        # Extract components from the response
        components = extract_components(response)
        
        # Build the properly formatted JSON structure
        formatted_response = {
            "thoughts": components["thoughts"],
            "tool_name": components["tool_name"],
            "tool_args": components["tool_args"]
        }
        
        # Convert to JSON string
        return json.dumps(formatted_response, ensure_ascii=False, indent=None)
        
    except Exception as e:
        # If auto-formatting fails, return None
        return None


def is_valid_agent_response(response: str) -> bool:
    """
    Check if a response is a valid agent response with proper JSON structure.
    Returns True if the response has the required fields: thoughts, tool_name, tool_args.
    """
    try:
        parsed = dirty_json.try_parse(response.strip())
        if parsed is None or not isinstance(parsed, dict):
            return False
        
        required_fields = ["thoughts", "tool_name", "tool_args"]
        return all(field in parsed for field in required_fields)
        
    except Exception:
        return False