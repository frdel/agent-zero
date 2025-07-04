import re
import json
from typing import Optional, Dict, Any
from python.helpers import dirty_json


def detect_misformat(response: str) -> bool:
    """
    Detect if a response needs auto-formatting.
    Returns True if the response appears to be malformed JSON that was intended to be a tool call.
    Returns False for normal conversational text.
    """
    if not response or not isinstance(response, str):
        return False
    
    response = response.strip()
    
    # First check: Does this look like it was intended to be JSON?
    # Look for JSON-like patterns that suggest tool usage intent
    json_indicators = [
        response.startswith('{') and response.endswith('}'),
        'tool_name' in response,
        'tool_args' in response, 
        '"thoughts"' in response or "'thoughts'" in response,
        response.count('{') > 0 and response.count(':') > 0
    ]
    
    # If it doesn't look like intended JSON, it's probably normal text
    if not any(json_indicators):
        return False
    
    # Try to parse as JSON
    try:
        parsed = dirty_json.try_parse(response)
        if parsed is None:
            # Looks like JSON but failed to parse - probably malformed
            return True
        
        # Check if it has the required structure
        if isinstance(parsed, dict):
            has_tool_name = "tool_name" in parsed
            has_tool_args = "tool_args" in parsed
            has_thoughts = "thoughts" in parsed
            
            # If it has the required fields, it's properly formatted
            if has_tool_name and has_tool_args and has_thoughts:
                return False
            # If it has some tool-related fields, might need formatting
            elif has_tool_name or has_tool_args:
                return True
        
        # Parsed but doesn't look like a tool call
        return False
        
    except Exception:
        # Failed to parse but looked like JSON - probably malformed
        return True


def extract_components(response: str) -> Dict[str, Any]:
    """
    Extract potential tool usage components from text response.
    Returns a dict with extracted thoughts, tool_name, and tool_args.
    """
    # Default to response tool only if we can't find anything else
    components = {
        "thoughts": [],
        "tool_name": None,  # Don't default to response yet
        "tool_args": {}
    }
    
    # Try to extract tool usage patterns more aggressively
    tool_patterns = [
        r'["\']?tool_name["\']?\s*:\s*["\']?(\w+)["\']?',  # tool_name: value
        r'tool[_\s]*name[:\s]*["\']?(\w+)["\']?',
        r'using[_\s]*tool[:\s]*["\']?(\w+)["\']?',
        r'call[_\s]*tool[:\s]*["\']?(\w+)["\']?',
        r'execute[_\s]*tool[:\s]*["\']?(\w+)["\']?',
        # Look for common tool names directly
        r'\b(search|code_execution|response|memory_save|memory_load|browser|webpage_content)\b',
    ]
    
    response_lower = response.lower()
    for pattern in tool_patterns:
        match = re.search(pattern, response_lower, re.IGNORECASE)
        if match:
            components["tool_name"] = match.group(1)
            break
    
    # Try to extract tool arguments if we found a tool name
    if components["tool_name"] and components["tool_name"] != "response":
        # Try to extract tool arguments
        arg_patterns = [
            r'["\']?tool_args["\']?\s*:\s*(\{[^}]*\})',  # tool_args: {...}
            r'["\']?args["\']?\s*:\s*(\{[^}]*\})',       # args: {...}
        ]
        
        for pattern in arg_patterns:
            match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    # Try to parse the arguments
                    args_text = match.group(1)
                    args_fixed = fix_json_syntax(args_text)
                    if args_fixed:
                        components["tool_args"] = json.loads(args_fixed)
                    else:
                        # Try dirty JSON parser
                        components["tool_args"] = dirty_json.try_parse(args_text) or {}
                except Exception:
                    components["tool_args"] = {}
                break
        
        # If no args found, try to extract basic arguments for common tools
        if not components["tool_args"]:
            if components["tool_name"] in ["search", "search_engine"]:
                # Look for query
                query_match = re.search(r'(?:query|search)[:\s]*["\']?([^"\'}\n]+)["\']?', response, re.IGNORECASE)
                if query_match:
                    components["tool_args"] = {"query": query_match.group(1).strip()}
            elif components["tool_name"] == "code_execution":
                # Look for code
                code_match = re.search(r'(?:code|script)[:\s]*["\']?([^"\'}\n]+)["\']?', response, re.IGNORECASE)
                if code_match:
                    components["tool_args"] = {"code": code_match.group(1).strip()}
    
    # If no tool found, default to response
    if not components["tool_name"]:
        components["tool_name"] = "response"
        components["tool_args"] = {"text": response.strip()}
    
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
        # First, try to fix common JSON syntax errors
        fixed_json = fix_json_syntax(response.strip())
        if fixed_json:
            try:
                # Try to parse the fixed JSON
                parsed = json.loads(fixed_json)
                if isinstance(parsed, dict) and ("tool_name" in parsed or "thoughts" in parsed):
                    return fixed_json
            except json.JSONDecodeError:
                pass
        
        # If JSON fix didn't work, try dirty JSON parser
        try:
            parsed = dirty_json.try_parse(response.strip())
            if parsed and isinstance(parsed, dict):
                # Check if it looks like a tool call
                if "tool_name" in parsed:
                    # Clean up the parsed data
                    cleaned = {
                        "thoughts": parsed.get("thoughts", ["Auto-formatted malformed response"]),
                        "tool_name": parsed.get("tool_name", "response"),
                        "tool_args": parsed.get("tool_args", {})
                    }
                    return json.dumps(cleaned, ensure_ascii=False)
        except Exception:
            pass
        
        # Last resort: extract components using pattern matching
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


def fix_json_syntax(text: str) -> Optional[str]:
    """
    Fix common JSON syntax errors like missing quotes around keys.
    """
    try:
        # Strip any leading/trailing text that's not part of JSON
        text = text.strip()
        
        # Find JSON-like content between braces
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        # Common fixes for malformed JSON
        fixes = [
            # Fix unquoted keys (but be careful not to break quoted strings)
            (r'(?<=[{\s,])(\w+)(?=\s*:)', r'"\1"'),
            # Fix single quotes to double quotes  
            (r"'([^']*)'", r'"\1"'),
            # Fix trailing commas
            (r',(\s*[}\]])', r'\1'),
            # Fix missing quotes around string values (simple heuristic)
            (r':\s*([^"\{\[\s][^,\}\]]*?)(?=\s*[,\}\]])', r': "\1"'),
            # Fix missing commas between key-value pairs
            (r'"\s*(?=["\w])', r'", '),
        ]
        
        fixed = text
        for pattern, replacement in fixes:
            fixed = re.sub(pattern, replacement, fixed)
        
        # Try to parse the fixed version
        json.loads(fixed)
        return fixed
        
    except Exception:
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