from python.helpers.api import ApiHandler, Request, Response

from python.helpers import settings

from typing import Any


class SetSettings(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[Any, Any] | Response:
        set = settings.convert_in(input)
        set = settings.set_settings(set)
        return {"settings": set}
