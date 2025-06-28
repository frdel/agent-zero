import base64
from io import BytesIO

from python.helpers.api import ApiHandler, Input, Output, Request, Response
from flask import send_file

from python.helpers import files, runtime
from python.api import file_info
import os


class DownloadFile(ApiHandler):

    @classmethod
    def get_methods(cls):
        return ["GET"]

    async def process(self, input: Input, request: Request) -> Output:
        file_path = request.args.get("path", input.get("path", ""))
        if not file_path:
            raise ValueError("No file path provided")
        if not file_path.startswith("/"):
            file_path = f"/{file_path}"

        file = await runtime.call_development_function(
            file_info.get_file_info, file_path
        )

        if not file["exists"]:
            raise Exception(f"File {file_path} not found")

        if file["is_dir"]:
            zip_file = await runtime.call_development_function(files.zip_dir, file["abs_path"])
            if runtime.is_development():
                b64 = await runtime.call_development_function(fetch_file, zip_file)
                file_data = BytesIO(base64.b64decode(b64))
                return send_file(
                    file_data,
                    as_attachment=True,
                    download_name=os.path.basename(zip_file),
                )
            else:
                return send_file(
                    zip_file,
                    as_attachment=True,
                    download_name=f"{os.path.basename(file_path)}.zip",
                )
        elif file["is_file"]:
            if runtime.is_development():
                b64 = await runtime.call_development_function(fetch_file, file["abs_path"])
                file_data = BytesIO(base64.b64decode(b64))
                return send_file(
                    file_data,
                    as_attachment=True,
                    download_name=os.path.basename(file_path),
                )
            else:
                return send_file(
                    file["abs_path"],
                    as_attachment=True,
                    download_name=os.path.basename(file["file_name"]),
                )
        raise Exception(f"File {file_path} not found")


async def fetch_file(path):
    with open(path, "rb") as file:
        file_content = file.read()
        return base64.b64encode(file_content).decode("utf-8")
