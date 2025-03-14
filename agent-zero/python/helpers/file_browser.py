import os
from pathlib import Path
import shutil
import tempfile
import base64
from typing import Dict, List, Tuple, Optional, Any
import zipfile
from werkzeug.utils import secure_filename
from datetime import datetime

from python.helpers import files, runtime
from python.helpers.print_style import PrintStyle

class FileBrowser:
    ALLOWED_EXTENSIONS = {
        'image': {'jpg', 'jpeg', 'png', 'bmp'},
        'code': {'py', 'js', 'sh', 'html', 'css'},
        'document': {'md', 'pdf', 'txt', 'csv', 'json'}
    }

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(self):
        # if runtime.is_development():
        #     base_dir = files.get_base_dir()
        # else:
        #     base_dir = "/"
        base_dir = "/"
        self.base_dir = Path(base_dir)
      
    def _check_file_size(self, file) -> bool:
        try:
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            return size <= self.MAX_FILE_SIZE
        except (AttributeError, IOError):
            return False

    def save_file_b64(self, current_path: str, filename:str, base64_content: str):
        try:
            # Resolve the target directory path
            target_file = (self.base_dir / current_path / filename).resolve()
            if not str(target_file).startswith(str(self.base_dir)):
                raise ValueError("Invalid target directory")

            os.makedirs(target_file.parent, exist_ok=True)
            # Save file
            with open(target_file, "wb") as file:
                file.write(base64.b64decode(base64_content))
            return True
        except Exception as e:
            PrintStyle.error(f"Error saving file {filename}: {e}")
            return False

    def save_files(self, files: List, current_path: str = "") -> Tuple[List[str], List[str]]:
        """Save uploaded files and return successful and failed filenames"""
        successful = []
        failed = []
        
        try:
            # Resolve the target directory path
            target_dir = (self.base_dir / current_path).resolve()
            if not str(target_dir).startswith(str(self.base_dir)):
                raise ValueError("Invalid target directory")
                
            os.makedirs(target_dir, exist_ok=True)
            
            for file in files:
                try:
                    if file and self._is_allowed_file(file.filename, file):
                        filename = secure_filename(file.filename)
                        file_path = target_dir / filename

                        file.save(str(file_path))
                        successful.append(filename)
                    else:
                        failed.append(file.filename)
                except Exception as e:
                    PrintStyle.error(f"Error saving file {file.filename}: {e}")
                    failed.append(file.filename)
                    
            return successful, failed
            
        except Exception as e:
            PrintStyle.error(f"Error in save_files: {e}")
            return successful, failed
        
    def delete_file(self, file_path: str) -> bool:
        """Delete a file or empty directory"""
        try:
            # Resolve the full path while preventing directory traversal
            full_path = (self.base_dir / file_path).resolve()
            if not str(full_path).startswith(str(self.base_dir)):
                raise ValueError("Invalid path")
                
            if os.path.exists(full_path):
                if os.path.isfile(full_path):
                    os.remove(full_path)
                elif os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                return True
                
            return False
            
        except Exception as e:
            PrintStyle.error(f"Error deleting {file_path}: {e}")
            return False

    def _is_allowed_file(self, filename: str, file) -> bool:
        # allow any file to be uploaded in file browser
        
        # if not filename:
        #     return False
        # ext = self._get_file_extension(filename)
        # all_allowed = set().union(*self.ALLOWED_EXTENSIONS.values())
        # if ext not in all_allowed:
        #     return False
        
        return True  # Allow the file if it passes the checks

    def _get_file_extension(self, filename: str) -> str:
        return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
    def get_files(self, current_path: str = "") -> Dict:
        try:
            # Resolve the full path while preventing directory traversal
            full_path = (self.base_dir / current_path).resolve()
            if not str(full_path).startswith(str(self.base_dir)):
                raise ValueError("Invalid path")

            files = []
            folders = []

            # List all entries in the current directory
            for entry in os.scandir(full_path):
                entry_data: Dict[str, Any] = {
                    "name": entry.name,
                    "path": str(Path(entry.path).relative_to(self.base_dir)),
                    "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat()
                }

                if entry.is_file():
                    entry_data.update({
                        "type": self._get_file_type(entry.name),
                        "size": entry.stat().st_size,
                        "is_dir": False
                    })
                    files.append(entry_data)
                else:
                    entry_data.update({
                        "type": "folder",
                        "size": 0,  # Directories show as 0 bytes
                        "is_dir": True
                    })
                    folders.append(entry_data)

            # Combine folders and files, folders first
            all_entries = folders + files

            # Get parent directory path if not at root
            parent_path = ""
            if current_path:
                try:
                    # Get the absolute path of current directory
                    current_abs = (self.base_dir / current_path).resolve()

                    # parent_path is empty only if we're already at root
                    if str(current_abs) != str(self.base_dir):
                        parent_path = str(Path(current_path).parent)
                    
                except Exception as e:
                    parent_path = ""

            return {
                "entries": all_entries,
                "current_path": current_path,
                "parent_path": parent_path
            }

        except Exception as e:
            PrintStyle.error(f"Error reading directory: {e}")
            return {"entries": [], "current_path": "", "parent_path": ""}
        
    def get_full_path(self, file_path: str, allow_dir: bool = False) -> str:
        """Get full file path if it exists and is within base_dir"""
        full_path = files.get_abs_path(self.base_dir,file_path)
        if not files.exists(full_path):
            raise ValueError(f"File {file_path} not found")        
        return full_path
        
    def _get_file_type(self, filename: str) -> str:
        ext = self._get_file_extension(filename)
        for file_type, extensions in self.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                return file_type
        return 'unknown'