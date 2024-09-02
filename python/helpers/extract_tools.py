import re, os
from typing import Any
from .  import files
# import dirtyjson
from .dirty_json import DirtyJson
import regex


def json_parse_dirty(json:str) -> dict[str,Any] | None:
    ext_json = extract_json_object_string(json)
    if ext_json:
        # ext_json = fix_json_string(ext_json)
        data = DirtyJson.parse_string(ext_json)
        if isinstance(data,dict): return data
    return None

def extract_json_object_string(content):
    start = content.find('{')
    if start == -1:
        return ""

    # Find the first '{'
    end = content.rfind('}')
    if end == -1:
        # If there's no closing '}', return from start to the end
        return content[start:]
    else:
        # If there's a closing '}', return the substring from start to end
        return content[start:end+1]

def extract_json_string(content):
    # Regular expression pattern to match a JSON object
    pattern = r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]|"(?:\\.|[^"\\])*"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'
    
    # Search for the pattern in the content
    match = regex.search(pattern, content)
    
    if match:
        # Return the matched JSON string
        return match.group(0)
    else:
        print("No JSON content found.")
        return ""

def fix_json_string(json_string):
    # Function to replace unescaped line breaks within JSON string values
    def replace_unescaped_newlines(match):
        return match.group(0).replace('\n', '\\n')

    # Use regex to find string values and apply the replacement function
    fixed_string = re.sub(r'(?<=: ")(.*?)(?=")', replace_unescaped_newlines, json_string, flags=re.DOTALL)
    return fixed_string

