from fnmatch import fnmatch
import os, re

import re

def read_file(relative_path, backup_dirs=None, encoding="utf-8", **kwargs):
    if backup_dirs is None:
        backup_dirs = []

    # Try to get the absolute path for the file from the original directory or backup directories
    absolute_path = find_file_in_dirs(relative_path, backup_dirs)

    # Read the file content
    with open(absolute_path, 'r', encoding=encoding) as f:
        content = remove_code_fences(f.read())

    # Replace placeholders with values from kwargs
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        strval = str(value)
        content = content.replace(placeholder, strval)

    # Process include statements
    content = process_includes(content, os.path.dirname(relative_path), backup_dirs, **kwargs)

    return content

def process_includes(content, base_path, backup_dirs, **kwargs):
    # Regex to find {{ include 'path' }} or {{include'path'}}
    include_pattern = re.compile(r"{{\s*include\s*['\"](.*?)['\"]\s*}}")

    def replace_include(match):
        include_path = match.group(1)
        # First attempt to resolve the include relative to the base path
        full_include_path = find_file_in_dirs(os.path.join(base_path, include_path), backup_dirs)
        
        # Recursively read the included file content, keeping the original base path
        included_content = read_file(full_include_path, backup_dirs, **kwargs)
        return included_content

    # Replace all includes with the file content
    return re.sub(include_pattern, replace_include, content)

def find_file_in_dirs(file_path, backup_dirs):
    """
    This function tries to find the file first in the given file_path,
    and then in the backup_dirs if not found in the original location.
    Returns the absolute path of the found file.
    """
    # Try the original path first
    if os.path.isfile(get_abs_path(file_path)):
        return get_abs_path(file_path)

    # Loop through the backup directories
    for backup_dir in backup_dirs:
        backup_path = os.path.join(backup_dir, os.path.basename(file_path))
        if os.path.isfile(get_abs_path(backup_path)):
            return get_abs_path(backup_path)

    # If the file is not found, let it raise the FileNotFoundError
    raise FileNotFoundError(f"File '{file_path}' not found in the original path or backup directories.")

def remove_code_fences(text):
    return re.sub(r'~~~\w*\n|~~~', '', text)

def write_file(relative_path:str, content:str, encoding:str="utf-8"):
    abs_path = get_abs_path(relative_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, 'w', encoding=encoding) as f:
        f.write(content)

def delete_file(relative_path:str):
    abs_path = get_abs_path(relative_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)

def list_files(relative_path:str, filter:str="*"):
    abs_path = get_abs_path(relative_path)
    if not os.path.exists(abs_path):
        return []
    return [file for file in os.listdir(abs_path) if fnmatch(file, filter)]

def get_abs_path(*relative_paths):
    return os.path.join(get_base_dir(), *relative_paths)

def exists(*relative_paths):
    path = get_abs_path(*relative_paths)
    return os.path.exists(path)

def get_base_dir():
    # Get the base directory from the current file path
    base_dir = os.path.dirname(os.path.abspath(os.path.join(__file__,"../../")))
    return base_dir

