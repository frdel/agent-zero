from python.helpers.api import ApiHandler, Request, Response
from typing import Any
from python.helpers import files

DEFAULT_CONFIG = '{\n    "mcpServers": {}\n}'


class McpProfileGetConfig(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[str, Any] | Response:
        try:
            profile = (input.get("profile") or "default").strip()
            if profile == "default":
                # Read from settings hidden field is handled client-side; provide it for symmetry if needed later
                return {"success": True, "mcp_servers": DEFAULT_CONFIG}
            rel_path = f"agents/{profile}/mcp.json"
            if files.exists(rel_path):
                content = files.read_file(rel_path)
            else:
                content = DEFAULT_CONFIG
            return {"success": True, "mcp_servers": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
