from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers import settings


class SetSettings(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        set = settings.convert_in(input)
        set = settings.set_settings(set)
        return {"settings": set}
