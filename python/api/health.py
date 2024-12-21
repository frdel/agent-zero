from python.helpers.api import ApiHandler
from flask import Request, Response

from python.helpers import git

class HealthCheck(ApiHandler):

    async def process(self, input: dict, request: Request) -> dict | Response:
        gitinfo = git.get_git_info()
        return {"gitinfo": gitinfo}
