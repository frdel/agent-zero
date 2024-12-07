from python.helpers.api import ApiHandler
from flask import Request, Response, send_file

from python.helpers.file_browser import FileBrowser
from python.helpers import files
import os


class DownloadWorkDirFile(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        file_path = request.args.get("path", "")
        if not file_path:
            raise ValueError("No file path provided")

        browser = FileBrowser()

        full_path = browser.get_full_path(file_path, True)
        if os.path.isdir(full_path):
            zip_file = browser.zip_dir(full_path)
            return send_file(
                zip_file,
                as_attachment=True,
                download_name=f"{os.path.basename(file_path)}.zip",
            )
        if full_path:
            return send_file(
                full_path, as_attachment=True, download_name=os.path.basename(file_path)
            )
        raise Exception("File not found")
