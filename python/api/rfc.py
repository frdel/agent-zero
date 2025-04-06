from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers import runtime

class RFC(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        result = await runtime.handle_rfc(input) # type: ignore
        return result
