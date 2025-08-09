import time
from python.helpers.api import ApiHandler, Request, Response

from typing import Any

from python.helpers.mcp_handler import MCPConfig
from python.helpers.settings import set_settings_delta
from python.helpers import files


class McpServersApply(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[Any, Any] | Response:
        mcp_servers = input["mcp_servers"]
        profile = (input.get("profile") or "default").strip()
        try:
            if profile == "default":
                # Global config via settings flow
                set_settings_delta({"mcp_servers": "[]"})  # to force reinitialization
                set_settings_delta({"mcp_servers": mcp_servers})

                time.sleep(1)  # wait at least a second
                status = MCPConfig.get_instance("default").get_servers_status()
                return {"success": True, "status": status}
            else:
                # Per-agent profile: persist to agents/<profile>/mcp.json
                rel_path = files.deabsolute_path(files.get_abs_path("agents", profile, "mcp.json"))
                files.write_file(rel_path, mcp_servers)

                # Update MCP multiton for this profile
                MCPConfig.update(mcp_servers, profile=profile)
                time.sleep(0.2)
                status = MCPConfig.get_instance(profile).get_servers_status()
                return {"success": True, "status": status}

        except Exception as e:
            return {"success": False, "error": str(e)}
