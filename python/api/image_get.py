import os
from python.helpers.api import ApiHandler
from flask import Request, Response, send_file


class ImageGet(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
            # input data
            path = input.get("path", request.args.get("path", ""))
            if not path:
                raise ValueError("No path provided")

            # send file
            return send_file(path)

            