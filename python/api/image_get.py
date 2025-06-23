import os
import re
from python.helpers.api import ApiHandler
from python.helpers import files
from flask import Request, Response, send_file


class ImageGet(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
            # input data
            path = input.get("path", request.args.get("path", ""))
            if not path:
                raise ValueError("No path provided")
            
            # check if path is within base directory
            if not files.is_in_base_dir(path):
                raise ValueError("Path is outside of allowed directory")
            
            # get file extension
            file_ext = os.path.splitext(path)[1].lower()
            
            # list of allowed image extensions
            image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"]
            
            if file_ext in image_extensions:
                # Handle image files
                if not os.path.exists(path):
                    # If image doesn't exist, return default image icon
                    return self._get_fallback_icon("image")
                
                # send actual image file
                return send_file(path)
            else:
                # Handle non-image files with fallback icons
                return self._get_file_type_icon(file_ext)
    
    def _get_file_type_icon(self, file_ext):
        """Return appropriate icon for file type"""
        # Map file extensions to icon names
        icon_mapping = {
            # Archive files
            '.zip': 'archive',
            '.rar': 'archive', 
            '.7z': 'archive',
            '.tar': 'archive',
            '.gz': 'archive',
            
            # Document files  
            '.pdf': 'document',
            '.doc': 'document',
            '.docx': 'document',
            '.txt': 'document',
            '.rtf': 'document',
            '.odt': 'document',
            
            # Code files
            '.py': 'code',
            '.js': 'code',
            '.html': 'code',
            '.css': 'code',
            '.json': 'code',
            '.xml': 'code',
            '.md': 'code',
            '.yml': 'code',
            '.yaml': 'code',
            '.sql': 'code',
            '.sh': 'code',
            '.bat': 'code',
            
            # Spreadsheet files
            '.xls': 'document',
            '.xlsx': 'document',
            '.csv': 'document',
            
            # Presentation files
            '.ppt': 'document',
            '.pptx': 'document',
            '.odp': 'document',
        }
        
        # Get icon name, default to 'file' if not found
        icon_name = icon_mapping.get(file_ext, 'file')
        return self._get_fallback_icon(icon_name)
    
    def _get_fallback_icon(self, icon_name):
        """Return fallback icon from public directory"""
        # Path to public icons
        icon_path = files.get_abs_path(f"webui/public/{icon_name}.svg")
        
        # Check if specific icon exists, fallback to generic file icon
        if not os.path.exists(icon_path):
            icon_path = files.get_abs_path("webui/public/file.svg")
        
        # Final fallback if file.svg doesn't exist
        if not os.path.exists(icon_path):
            raise ValueError(f"Fallback icon not found: {icon_path}")
        
        return send_file(icon_path, mimetype='image/svg+xml')

            