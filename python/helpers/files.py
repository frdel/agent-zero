import os, re

import re

def read_file(relative_path, **kwargs):
    absolute_path = get_abs_path(relative_path)  # Construct the absolute path to the target file

    with open(absolute_path) as f:
        content = remove_code_fences(f.read())

    # Replace placeholders with values from kwargs
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        strval = str(value)
        content = content.replace(placeholder, strval)

    # Process include statements
    content = process_includes(content, os.path.dirname(absolute_path), **kwargs)

    return content

def remove_code_fences(text):
    return re.sub(r'~~~\w*\n|~~~', '', text)

def process_includes(content, base_path, **kwargs):
    # Regex to find {{ include 'path' }} or {{include'path'}}
    include_pattern = re.compile(r"{{\s*include\s*['\"](.*?)['\"]\s*}}")

    def replace_include(match):
        include_path = match.group(1)
        # Resolve the full path relative to base_path
        full_include_path = get_abs_path(base_path, include_path)
        
        # Recursively read the included file content
        included_content = read_file(full_include_path, **kwargs)
        return included_content

    # Replace all includes with the file content
    return re.sub(include_pattern, replace_include, content)


def get_abs_path(*relative_paths):
    return os.path.join(get_base_dir(), *relative_paths)

def exists(*relative_paths):
    path = get_abs_path(*relative_paths)
    return os.path.exists(path)


def get_base_dir():
    # Get the base directory from the current file path
    base_dir = os.path.dirname(os.path.abspath(os.path.join(__file__,"../../")))
    return base_dir

