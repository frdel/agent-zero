from python.helpers.api import ApiHandler
from flask import Request, Response

from typing import Any

# from python.helpers.mcp_handler import MCPConfig
from python.helpers.settings import set_settings_delta


class McpServersApply(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[Any, Any] | Response:
        mcp_servers = input["mcp_servers"]
        try:
            # MCPConfig.update(mcp_servers) # done in settings automatically
            set_settings_delta({"mcp_servers": mcp_servers})

        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": True}
