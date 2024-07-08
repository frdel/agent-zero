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

# def extract_tool_requests2(response):
#     # Regex to match the tags ending with $, allowing for varying whitespace
#     pattern = r'<(\w+)\$[\s]*(.*?)>([\s\S]*?)(?=<\w+\$|<\/\1\$|$)'
#     matches = re.findall(pattern, response, re.DOTALL)
    
#     tool_usages = []
#     allowed_tags = list_python_files("tools")
    
#     for match in matches:
#         tag_name, attributes, content = match

#         if tag_name not in allowed_tags: continue
        
#         tool_dict = {}
#         tool_dict['name'] = tag_name
#         tool_dict['args'] = {}
        
#         # Parse attributes
#         for attr in re.findall(r'(\w+)\s*=\s*"([^"]+)"', attributes):
#             tool_dict['args'][attr[0]] = attr[1]
        
#         # Add body content
#         tool_dict["content"] = content.strip()
#         tool_dict["index"] = len(tool_usages)
#         tool_usages.append(tool_dict)
    
#     return tool_usages

# def extract_tool_requests(response):
#     # Regex to match the tool blocks, allowing for varying whitespace
#     pattern = r'<tool\$[\s]*(.*?)>(.*?)<\/tool\$\s*>'
#     matches = re.findall(pattern, response, re.DOTALL)
    
#     tool_usages = []
    
#     for match in matches:
#         attributes, body = match
#         tool_dict = {}
#         # Parse attributes
#         for attr in re.findall(r'(\w+)\s*=\s*"([^"]+)"', attributes):
#             tool_dict[attr[0]] = attr[1]
#         # Add body content
#         tool_dict["body"] = body.strip()
#         tool_usages.append(tool_dict)
    
#     return tool_usages

# def extract_specified_tags(response):

#     allowed_tags = list_python_files("tools")
    
#     # Create a regex pattern to match specified tags and their attributes
#     pattern = r'<({})([\s\S]*?)>'.format('|'.join(allowed_tags))
#     matches = re.findall(pattern, response, re.DOTALL)
    
#     extracted_tags = []
    
#     for match in matches:
#         tag_name, attributes = match
#         tag_dict = {}
#         tag_dict['name'] = tag_name
        
#         # Parse attributes
#         for attr in re.findall(r'(\w+)\s*=\s*"([^"]+)"', attributes):
#             tag_dict[attr[0]] = attr[1]
        
#         # Extract the body text (everything after the tag until the next tag or end of string)
#         body_pattern = r'<{0}[\s\S]*?>([\s\S]*?)(?=<|$)'.format(tag_name)
#         body_match = re.search(body_pattern, response, re.DOTALL)
#         tag_dict['body'] = body_match.group(1).strip() if body_match else ''
        
#         extracted_tags.append(tag_dict)
    
#     return extracted_tags

# def list_python_files(directory):
#     # List all files in the given directory
#     list = os.listdir(files.get_abs_path(directory))
#     # Filter for Python files and remove the extension
#     python_files = { os.path.splitext(file)[0] for file in list if file.endswith('.py') }
#     return python_files

# import re
# from xml.etree import ElementTree as ET

# def extract_tool_usages_advanced(response):
#     tool_usages = []
#     pattern = re.compile(r'<tool.*?>', re.DOTALL)
    
#     start_pos = 0
#     while start_pos < len(response):
#         match = pattern.search(response, start_pos)
#         if not match:
#             break
        
#         tag_start = match.start()
#         tag_end = match.end()
#         end_tag = '</tool>'
        
#         # To find the corresponding end tag correctly handling nested tags
#         depth = 1
#         search_pos = tag_end
        
#         while depth > 0:
#             next_open = response.find('<tool', search_pos)
#             next_close = response.find(end_tag, search_pos)
            
#             if next_close == -1:
#                 break
            
#             if next_open != -1 and next_open < next_close:
#                 depth += 1
#                 search_pos = next_open + len('<tool')
#             else:
#                 depth -= 1
#                 search_pos = next_close + len(end_tag)
        
#         end_tag_end = search_pos
        
#         # Extract the whole tool block
#         tool_block = response[tag_start:end_tag_end]
        
#         try:
#             element = ET.fromstring(tool_block)
#             tool_dict = element.attrib
#             tool_dict["body"] = ET.tostring(element, encoding='unicode', method='xml').split('>', 1)[1].rsplit('<', 1)[0].strip()
#             tool_usages.append(tool_dict)
#         except ET.ParseError:
#             # In case of parsing error, fall back to including entire content between the tags
#             body_content = response[tag_end:end_tag_end - len(end_tag)].strip()
#             tool_dict = {"name": re.search(r'name="(.*?)"', match.group(0)).group(1), "body": body_content}
#             tool_usages.append(tool_dict)
        
#         start_pos = end_tag_end

#     return tool_usages

# # Example usage with the given input
# response = """
# <tool name="code_execution_tool">
#     #comment <tool<tool name="abc><tool><loot><tool>"
# print(text)
# </tool>
# """

# tool_usages = extract_tool_usages(response)
# print(tool_usages)