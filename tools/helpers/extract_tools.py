import re

def extract_tool_requests(response):
    # Regex to match the tool blocks
    pattern = r'<tool\$(.*?)>(.*?)</tool\$>'
    matches = re.findall(pattern, response, re.DOTALL)
    
    tool_usages = []
    
    for match in matches:
        attributes, body = match
        tool_dict = {}
        # Parse attributes
        for attr in re.findall(r'(\w+)="([^"]+)"', attributes):
            tool_dict[attr[0]] = attr[1]
        # Add body content
        tool_dict["body"] = body.strip()
        tool_usages.append(tool_dict)
    
    return tool_usages

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