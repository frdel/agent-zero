import os
import json
from flask import request, Response, send_file
from python.helpers.api import ApiHandler
from python.helpers import files
from python.helpers.print_style import PrintStyle


class CanvasServe(ApiHandler):
    """
    API endpoint to serve canvas artifacts safely
    """
    
    def __init__(self, app, lock):
        super().__init__(app, lock)

    async def _serve_file(self, canvas_id, filename):
        """Internal method to serve canvas files"""
        try:
            # Validate canvas ID (should be alphanumeric with dashes)
            if not canvas_id.replace('-', '').isalnum():
                return Response("Invalid canvas ID", status=400)
            
            # Construct safe file path
            canvas_dir = files.get_abs_path("work_dir", "canvas", canvas_id)
            file_path = os.path.join(canvas_dir, filename)
            
            # Security check - ensure file is within canvas directory
            if not os.path.abspath(file_path).startswith(os.path.abspath(canvas_dir)):
                return Response("Access denied", status=403)
            
            # Check if file exists
            if not os.path.exists(file_path):
                PrintStyle(font_color="yellow", padding=True).print(f"Canvas file not found: {file_path}")
                return Response("Canvas file not found", status=404)
            
            # Determine MIME type based on file extension
            mime_type = self._get_mime_type(filename)
            
            PrintStyle(font_color="green", padding=True).print(f"Serving canvas file: {canvas_id}/{filename}")
            
            # Serve the file
            return send_file(
                file_path,
                mimetype=mime_type,
                as_attachment=False,
                download_name=filename
            )
            
        except Exception as e:
            PrintStyle(font_color="red", padding=True).print(f"Canvas serve error: {str(e)}")
            return Response(f"Server error: {str(e)}", status=500)

    async def process(self, input, request):
        """Handle API-style requests with canvas_id and filename in input data"""
        try:
            canvas_id = input.get('canvas_id')
            filename = input.get('filename', 'content.html')
            
            if not canvas_id:
                return {"error": "canvas_id is required"}
            
            return await self._serve_file(canvas_id, filename)
            
        except Exception as e:
            PrintStyle(font_color="red", padding=True).print(f"Canvas API error: {str(e)}")
            return {"error": f"Server error: {str(e)}"}

    async def handle_request(self, request):
        """Override handle_request to support both URL path and API-style requests"""
        
        # Check if this is a path-based request
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 3 and path_parts[0] == 'canvas_serve':
            canvas_id = path_parts[1]
            filename = path_parts[2]
            return await self._serve_file(canvas_id, filename)
        
        # Otherwise use the standard API handler
        return await super().handle_request(request)

    def _get_mime_type(self, filename):
        """Get MIME type based on file extension"""
        
        extension = filename.lower().split('.')[-1]
        
        mime_types = {
            'html': 'text/html',
            'css': 'text/css',
            'js': 'application/javascript',
            'json': 'application/json',
            'txt': 'text/plain',
            'md': 'text/markdown',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'svg': 'image/svg+xml',
            'pdf': 'application/pdf'
        }
        
        return mime_types.get(extension, 'text/plain')

    @classmethod
    def requires_auth(cls):
        """This endpoint requires authentication"""
        return True

    @classmethod
    def requires_loopback(cls):
        """This endpoint doesn't require loopback"""
        return False

    @classmethod
    def requires_api_key(cls):
        """This endpoint doesn't require API key"""
        return False