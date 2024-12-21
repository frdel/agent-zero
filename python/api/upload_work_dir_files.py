from python.helpers.api import ApiHandler
from flask import Request, Response, send_file

from python.helpers.file_browser import FileBrowser
from python.helpers import files
import os




class UploadWorkDirFiles(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if "files[]" not in request.files:
            raise Exception("No files uploaded")

        current_path = request.form.get('path', '')
        uploaded_files = request.files.getlist("files[]") 
        
        browser = FileBrowser()
        
        successful, failed = browser.save_files(uploaded_files, current_path)
        
        if not successful and failed:
            raise Exception("All uploads failed")
            
        result = browser.get_files(current_path)
        
        return {
            "message": "Files uploaded successfully" if not failed else "Some files failed to upload",
            "data": result,
            "successful": successful,
            "failed": failed
        }