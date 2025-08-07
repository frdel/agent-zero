from python.helpers.api import ApiHandler, Request, Response

from python.helpers import runtime

class RFC(ApiHandler):

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    @classmethod
    def requires_auth(cls) -> bool:
        return False

    async def process(self, input: dict, request: Request) -> dict | Response:
        result = await runtime.handle_rfc(input) # type: ignore
        return result
