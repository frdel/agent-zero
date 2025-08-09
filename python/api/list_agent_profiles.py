from python.helpers.api import ApiHandler, Request, Response
from typing import Any
from python.helpers import files


class ListAgentProfiles(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[str, Any] | Response:
        try:
            profiles = [p for p in files.get_subdirectories("agents") if p != "_example"]
            profiles.sort()
            return {"success": True, "profiles": profiles}
        except Exception as e:
            return {"success": False, "error": str(e)}
