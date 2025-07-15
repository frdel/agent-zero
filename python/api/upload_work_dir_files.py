import base64
from werkzeug.datastructures import FileStorage
from python.helpers.api import ApiHandler, Request, Response
from python.helpers.file_browser import FileBrowser
from python.helpers import files, runtime
from python.api import get_work_dir_files
import os


class UploadWorkDirFiles(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if "files[]" not in request.files:
            raise Exception("No files uploaded")

        current_path = request.form.get("path", "")
        uploaded_files = request.files.getlist("files[]")

        # browser = FileBrowser()
        # successful, failed = browser.save_files(uploaded_files, current_path)

        successful, failed = await upload_files(uploaded_files, current_path)

        if not successful and failed:
            raise Exception("All uploads failed")

        # result = browser.get_files(current_path)
        result = await runtime.call_development_function(get_work_dir_files.get_files, current_path)

        return {
            "message": (
                "Files uploaded successfully"
                if not failed
                else "Some files failed to upload"
            ),
            "data": result,
            "successful": successful,
            "failed": failed,
        }


async def upload_files(uploaded_files: list[FileStorage], current_path: str):
    if runtime.is_development():
        successful = []
        failed = []
        for file in uploaded_files:
            file_content = file.stream.read()
            base64_content = base64.b64encode(file_content).decode("utf-8")
            if await runtime.call_development_function(
                upload_file, current_path, file.filename, base64_content
            ):
                successful.append(file.filename)
            else:
                failed.append(file.filename)
    else:
        browser = FileBrowser()
        successful, failed = browser.save_files(uploaded_files, current_path)

    return successful, failed


async def upload_file(current_path: str, filename: str, base64_content: str):
    browser = FileBrowser()
    return browser.save_file_b64(current_path, filename, base64_content)

