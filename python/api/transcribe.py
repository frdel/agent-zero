from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers import runtime, settings, whisper

class Transcribe(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        audio = input.get("audio")
        ctxid = input.get("ctxid", "")

        context = self.get_context(ctxid)
        if await whisper.is_downloading():
            context.log.log(type="info", content="Whisper model is currently being downloaded, please wait...")

        set = settings.get_settings()
        result = await whisper.transcribe(set["stt_model_size"], audio) # type: ignore
        return result
