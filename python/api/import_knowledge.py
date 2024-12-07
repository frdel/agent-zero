from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers.file_browser import FileBrowser
from python.helpers import files
import os
from werkzeug.utils import secure_filename


class ImportKnowledge(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if "files[]" not in request.files:
            raise Exception("No files part")

        file_list = request.files.getlist("files[]")
        KNOWLEDGE_FOLDER = files.get_abs_path("knowledge/custom/main")

        saved_filenames = []

        for file in file_list:
            if file:
                filename = secure_filename(file.filename)  # type: ignore
                file.save(os.path.join(KNOWLEDGE_FOLDER, filename))
                saved_filenames.append(filename)

        return {"message": "Knowledge Imported", "filenames": saved_filenames}
