from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers import files
from werkzeug.utils import secure_filename


class UploadFile(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if "file" not in request.files:
            raise Exception("No file part")

        file_list = request.files.getlist("file")  # Handle multiple files
        saved_filenames = []

        for file in file_list:
            if file and self.allowed_file(file.filename):  # Check file type
                filename = secure_filename(file.filename) # type: ignore
                file.save(files.get_abs_path("tmp/upload", filename))
                saved_filenames.append(filename)

        return {"filenames": saved_filenames}  # Return saved filenames


    def allowed_file(self,filename):
        return True
        # ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "txt", "pdf", "csv", "html", "json", "md"}
        # return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS