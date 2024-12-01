from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers.file_browser import FileBrowser
from python.helpers import files, runtime


class GetWorkDirFiles(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        current_path = request.args.get("path", "")
        if current_path == "$WORK_DIR":
            if runtime.is_development():
                current_path = "work_dir"
            else:
                current_path = "root"
        browser = FileBrowser()
        result = browser.get_files(current_path)

        return {"data": result}
