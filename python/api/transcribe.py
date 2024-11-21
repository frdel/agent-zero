from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers import runtime, whisper

class Transcribe(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        audio = input.get("audio")
        result = await whisper.transcribe(audio) # type: ignore
        return result
