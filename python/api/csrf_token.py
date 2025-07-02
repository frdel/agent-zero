import secrets
from python.helpers.api import (
    ApiHandler,
    Input,
    Output,
    Request,
    Response,
    session,
)
from python.helpers import runtime

class GetCsrfToken(ApiHandler):

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET"]

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    async def process(self, input: Input, request: Request) -> Output:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {"token": session["csrf_token"], "runtime_id": runtime.get_runtime_id()}
