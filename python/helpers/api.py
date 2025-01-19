from abc import abstractmethod
import json
import threading
from typing import Union, TypedDict, Dict, Any
from attr import dataclass
from flask import Request, Response, jsonify, Flask
from agent import AgentContext
from initialize import initialize
from python.helpers.print_style import PrintStyle
from python.helpers.errors import format_error
from werkzeug.serving import make_server


Input = dict
Output = Union[Dict[str, Any], Response, TypedDict]


class ApiHandler:
    def __init__(self, app: Flask, thread_lock: threading.Lock):
        self.app = app
        self.thread_lock = thread_lock

    @abstractmethod
    async def process(self, input: Input, request: Request) -> Output:
        pass

    async def handle_request(self, request: Request) -> Response:
        try:
            # input data from request based on type
            if request.is_json:
                input = request.get_json()
            else:
                input = {"data": request.get_data(as_text=True)}

            # process via handler
            output = await self.process(input, request)

            # return output based on type
            if isinstance(output, Response):
                return output
            else:
                response_json = json.dumps(output)
                return Response(
                    response=response_json, status=200, mimetype="application/json"
                )

            # return exceptions with 500
        except Exception as e:
            error = format_error(e)
            PrintStyle.error(error)
            return Response(response=error, status=500, mimetype="text/plain")

    # get context to run agent zero in
    def get_context(self, ctxid: str):
        with self.thread_lock:
            if not ctxid:
                first = AgentContext.first()
                if first:
                    return first
                return AgentContext(config=initialize())
            got = AgentContext.get(ctxid)
            if got:
                return got
            return AgentContext(config=initialize(), id=ctxid)
