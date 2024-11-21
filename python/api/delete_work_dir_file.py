from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers.file_browser import FileBrowser
from python.helpers import files


class DeleteWorkDirFile(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        file_path = input.get('path', '')
        current_path = input.get('currentPath', '')
        
        work_dir = files.get_abs_path("work_dir")
        browser = FileBrowser(work_dir)
        
        if browser.delete_file(file_path):
            # Get updated file list
            result = browser.get_files(current_path)
            return {
                "data": result
            }
        else:
            raise Exception("File not found or could not be deleted")