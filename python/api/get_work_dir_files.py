from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers.file_browser import FileBrowser
from python.helpers import files


class GetWorkDirFiles(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        current_path = request.args.get("path", "")
        work_dir = files.get_abs_path("work_dir")
        browser = FileBrowser(work_dir)
        result = browser.get_files(current_path)

        return {"data": result}
