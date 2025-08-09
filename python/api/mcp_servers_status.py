from python.helpers.api import ApiHandler, Request, Response

from typing import Any

from python.helpers.mcp_handler import MCPConfig


class McpServersStatus(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[Any, Any] | Response:
        # try:
        profile = (input.get("profile") or "default").strip()
        status = MCPConfig.get_instance(profile).get_servers_status()
        return {"success": True, "status": status}
        # except Exception as e:
        #     return {"success": False, "error": str(e)}
