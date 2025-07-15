from python.helpers.api import ApiHandler, Request, Response
from typing import Any

from python.helpers.mcp_handler import MCPConfig


class McpServerGetDetail(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[Any, Any] | Response:
        
        # try:
            server_name = input.get("server_name")
            if not server_name:
                return {"success": False, "error": "Missing server_name"}
            detail = MCPConfig.get_instance().get_server_detail(server_name)
            return {"success": True, "detail": detail}
        # except Exception as e:
        #     return {"success": False, "error": str(e)}
