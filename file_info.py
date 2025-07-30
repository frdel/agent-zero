#!/usr/bin/env python3
"""
Minimal file_info module for container RFC calls
"""
import os

async def get_file_info(path: str):
    """Get file information without complex dependencies"""
    # Determine the absolute path
    if path.startswith('/'):
        abs_path = path
    else:
        # For development, files are typically in work_dir or root
        if path.startswith('root/'):
            abs_path = f"/a0/work_dir/{path[5:]}"  # Remove 'root/' prefix
        elif path.startswith('work_dir/'):
            abs_path = f"/a0/{path}"
        else:
            abs_path = f"/a0/work_dir/{path}"
    
    exists = os.path.exists(abs_path)
    message = ""
    
    if not exists:
        message = f"File {path} not found."
    
    return {
        "input_path": path,
        "abs_path": abs_path,
        "exists": exists,
        "is_dir": os.path.isdir(abs_path) if exists else False,
        "is_file": os.path.isfile(abs_path) if exists else False,
        "is_link": os.path.islink(abs_path) if exists else False,
        "size": os.path.getsize(abs_path) if exists and os.path.isfile(abs_path) else 0,
        "modified": os.path.getmtime(abs_path) if exists else 0,
        "created": os.path.getctime(abs_path) if exists else 0,
        "permissions": os.stat(abs_path).st_mode if exists else 0,
        "dir_path": os.path.dirname(abs_path),
        "file_name": os.path.basename(abs_path),
        "file_ext": os.path.splitext(abs_path)[1],
        "message": message
    }