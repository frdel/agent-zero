from python.helpers.api import ApiHandler, Request, Response

from python.helpers import settings

class GetSettings(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        set = settings.convert_out(settings.get_settings())
        return {"settings": set}
