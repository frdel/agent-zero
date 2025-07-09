import os
import re
from typing import override
from python.helpers.api import ApiHandler
from python.helpers import files
from flask import Request, Response, send_file


class ImageGet(ApiHandler):

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET"]

    async def process(self, input: dict, request: Request) -> dict | Response:
            # input data
            path = input.get("path", request.args.get("path", ""))
            metadata = input.get("metadata", request.args.get("metadata", "false")).lower() == "true"
            
            print(f"ImageGet: Processing path={path}, metadata={metadata}")  # Debug
            
            if not path:
                raise ValueError("No path provided")
            
            # check if path is within base directory
            if not files.is_in_base_dir(path):
                raise ValueError("Path is outside of allowed directory")
            
            # get file extension and info
            file_ext = os.path.splitext(path)[1].lower()
            filename = os.path.basename(path)
            
            print(f"ImageGet: file_ext={file_ext}, filename={filename}")  # Debug
            
            # list of allowed image extensions
            image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"]
            
            # If metadata is requested, return file information
            if metadata:
                return self._get_file_metadata(path, filename, file_ext, image_extensions)
            
            if file_ext in image_extensions:
                # Handle image files
                print(f"ImageGet: Handling as image file")  # Debug
                if not os.path.exists(path):
                    # If image doesn't exist, return default image icon
                    return self._get_fallback_icon("image")
                
                # send actual image file with proper headers for device sync
                response = send_file(path)
                # Add cache headers for better device sync performance
                response.headers['Cache-Control'] = 'public, max-age=3600'
                response.headers['X-File-Type'] = 'image'
                response.headers['X-File-Name'] = filename
                return response
            else:
                # Handle non-image files with fallback icons
                print(f"ImageGet: Handling as non-image file, getting icon")  # Debug
                return self._get_file_type_icon(file_ext, filename)
    
    def _get_file_type_icon(self, file_ext, filename=None):
        """Return appropriate icon for file type"""
        print(f"_get_file_type_icon: file_ext={file_ext}, filename={filename}")  # Debug
        
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
        print(f"_get_file_type_icon: icon_name={icon_name}")  # Debug
        
        response = self._get_fallback_icon(icon_name)
        
        # Add headers for device sync
        if hasattr(response, 'headers'):
            response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache icons for 24 hours
            response.headers['X-File-Type'] = 'icon'
            response.headers['X-Icon-Type'] = icon_name
            if filename:
                response.headers['X-File-Name'] = filename
        
        return response
    
    def _get_file_metadata(self, path, filename, file_ext, image_extensions):
        """Return file metadata for device sync and UI enhancement"""
        metadata = {
            'filename': filename,
            'extension': file_ext,
            'exists': os.path.exists(path),
            'is_image': file_ext in image_extensions,
            'file_type': 'image' if file_ext in image_extensions else self._get_file_category(file_ext),
            'api_url': f'/image_get?path={path}',
            'icon_type': self._get_icon_type(file_ext) if file_ext not in image_extensions else 'image'
        }
        
        # Add file size if file exists
        if metadata['exists']:
            try:
                metadata['size'] = os.path.getsize(path)
                metadata['size_human'] = self._format_file_size(metadata['size'])
            except OSError:
                metadata['size'] = 0
                metadata['size_human'] = 'Unknown'
        
        return metadata
    
    def _get_file_category(self, file_ext):
        """Get file category for metadata"""
        categories = {
            '.zip': 'archive', '.rar': 'archive', '.7z': 'archive', '.tar': 'archive', '.gz': 'archive',
            '.pdf': 'document', '.doc': 'document', '.docx': 'document', '.txt': 'document',
            '.py': 'code', '.js': 'code', '.html': 'code', '.css': 'code', '.json': 'code',
            '.xls': 'spreadsheet', '.xlsx': 'spreadsheet', '.csv': 'spreadsheet',
            '.ppt': 'presentation', '.pptx': 'presentation'
        }
        return categories.get(file_ext, 'file')
    
    def _get_icon_type(self, file_ext):
        """Get icon type for metadata (matches the icon mapping)"""
        icon_mapping = {
            '.zip': 'archive', '.rar': 'archive', '.7z': 'archive', '.tar': 'archive', '.gz': 'archive',
            '.pdf': 'document', '.doc': 'document', '.docx': 'document', '.txt': 'document', '.rtf': 'document', '.odt': 'document',
            '.py': 'code', '.js': 'code', '.html': 'code', '.css': 'code', '.json': 'code', '.xml': 'code', '.md': 'code',
            '.yml': 'code', '.yaml': 'code', '.sql': 'code', '.sh': 'code', '.bat': 'code',
            '.xls': 'document', '.xlsx': 'document', '.csv': 'document',
            '.ppt': 'document', '.pptx': 'document', '.odp': 'document'
        }
        return icon_mapping.get(file_ext, 'file')
    
    def _format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def _get_fallback_icon(self, icon_name):
        """Return fallback icon from public directory"""
        print(f"_get_fallback_icon: icon_name={icon_name}")  # Debug
        
        # Path to public icons
        icon_path = files.get_abs_path(f"webui/public/{icon_name}.svg")
        print(f"_get_fallback_icon: icon_path={icon_path}")  # Debug
        
        # Check if specific icon exists, fallback to generic file icon
        if not os.path.exists(icon_path):
            print(f"_get_fallback_icon: Icon not found, falling back to file.svg")  # Debug
            icon_path = files.get_abs_path("webui/public/file.svg")
        
        # Final fallback if file.svg doesn't exist
        if not os.path.exists(icon_path):
            print(f"_get_fallback_icon: ERROR - file.svg not found at {icon_path}")  # Debug
            raise ValueError(f"Fallback icon not found: {icon_path}")
        
        print(f"_get_fallback_icon: Sending file {icon_path}")  # Debug
        return send_file(icon_path, mimetype='image/svg+xml')

            