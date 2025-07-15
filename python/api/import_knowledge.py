from python.helpers.api import ApiHandler, Request, Response
from python.helpers import files, memory
import os
from werkzeug.utils import secure_filename


class ImportKnowledge(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if "files[]" not in request.files:
            raise Exception("No files part")

        ctxid = request.form.get("ctxid", "")
        if not ctxid:
            raise Exception("No context id provided")

        context = self.get_context(ctxid)

        file_list = request.files.getlist("files[]")
        KNOWLEDGE_FOLDER = files.get_abs_path(memory.get_custom_knowledge_subdir_abs(context.agent0),"main")

        saved_filenames = []

        for file in file_list:
            if file:
                filename = secure_filename(file.filename)  # type: ignore
                file.save(os.path.join(KNOWLEDGE_FOLDER, filename))
                saved_filenames.append(filename)

        #reload memory to re-import knowledge
        await memory.Memory.reload(context.agent0)
        context.log.set_initial_progress()

        return {
            "message": "Knowledge Imported",
            "filenames": saved_filenames[:5]
        }