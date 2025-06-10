from python.helpers.api import ApiHandler
from flask import Request, Response

from typing import Any

from python.helpers.mcp_handler import MCPConfig


class McpServerGetLog(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[Any, Any] | Response:
        
        # try:
            server_name = input.get("server_name")
            if not server_name:
                return {"success": False, "error": "Missing server_name"}
            log = MCPConfig.get_instance().get_server_log(server_name)
            return {"success": True, "log": log}
        # except Exception as e:
        #     return {"success": False, "error": str(e)}
