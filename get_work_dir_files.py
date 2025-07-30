#!/usr/bin/env python3
"""
Minimal get_work_dir_files module for container RFC calls
"""
import os

async def get_files(path):
    """Get files and directories without complex dependencies"""
    # Map path to actual filesystem path
    if path == "root" or path == "":
        base_path = "/a0/work_dir"
    elif path.startswith("root/"):
        base_path = f"/a0/work_dir/{path[5:]}"  # Remove 'root/' prefix
    elif path.startswith("/"):
        base_path = path
    else:
        base_path = f"/a0/work_dir/{path}"
    
    if not os.path.exists(base_path):
        return {
            "files": [],
            "directories": [],
            "path": path,
            "error": f"Path {path} not found"
        }
    
    files = []
    directories = []
    
    try:
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            
            if os.path.isdir(item_path):
                directories.append({
                    "name": item,
                    "path": f"{path}/{item}" if path != "root" else f"root/{item}",
                    "type": "directory",
                    "size": 0,
                    "modified": os.path.getmtime(item_path)
                })
            elif os.path.isfile(item_path):
                files.append({
                    "name": item,
                    "path": f"{path}/{item}" if path != "root" else f"root/{item}",
                    "type": "file",
                    "size": os.path.getsize(item_path),
                    "modified": os.path.getmtime(item_path),
                    "extension": os.path.splitext(item)[1]
                })
    except PermissionError:
        return {
            "files": [],
            "directories": [],
            "path": path,
            "error": f"Permission denied accessing {path}"
        }
    
    return {
        "files": sorted(files, key=lambda x: x["name"]),
        "directories": sorted(directories, key=lambda x: x["name"]),
        "path": path,
        "total_files": len(files),
        "total_directories": len(directories)
    }