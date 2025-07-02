from python.helpers.api import ApiHandler
from flask import Request, Response  # type: ignore
from typing import Any
import json, time
from python.helpers.settings import get_settings, set_settings_delta
from python.helpers.mcp_handler import MCPConfig, normalize_name


class McpServerToggle(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[str, Any] | Response:  # type: ignore
        """Enable/disable a single MCP server in settings.

        Expected JSON input:
        {
            "server_name": "context7",
            "enabled": true
        }
        """
        try:
            server_name = input.get("server_name")
            if not server_name:
                return {"success": False, "error": "server_name is required"}

            enabled_flag = bool(input.get("enabled", True))

            # Load current config JSON from settings
            settings = get_settings()
            mcp_json_str: str = settings.get("mcp_servers", "{\n    \"mcpServers\": {}\n}")
            try:
                mcp_config = json.loads(mcp_json_str)
            except Exception as e:
                return {"success": False, "error": f"Invalid MCP servers JSON in settings: {e}"}

            # Normalize to dict[server_name] -> config
            servers_dict = {}
            if isinstance(mcp_config, dict) and "mcpServers" in mcp_config:
                servers_dict = mcp_config["mcpServers"] if isinstance(mcp_config["mcpServers"], dict) else {}
            elif isinstance(mcp_config, dict):
                # assume flat single server definition
                servers_dict = {mcp_config.get("name", server_name): mcp_config}
            elif isinstance(mcp_config, list):
                # list of servers
                for srv in mcp_config:
                    if isinstance(srv, dict):
                        nm = srv.get("name")
                        if nm:
                            servers_dict[nm] = srv
            else:
                return {"success": False, "error": "Unsupported MCP servers config structure"}

            if server_name not in servers_dict:
                # attempt to match using normalized names (handles hyphens, spaces, etc.)
                norm_target = normalize_name(server_name)
                matched_key = next(
                    (k for k in servers_dict.keys() if normalize_name(k) == norm_target),
                    None,
                )
                if matched_key:
                    server_name = matched_key  # use the original key for update
                else:
                    return {"success": False, "error": f"Server '{server_name}' not found in configuration"}

            # Update disabled flag (note: enabled=True -> disabled=False)
            servers_dict[server_name]["disabled"] = not enabled_flag

            # Re-assemble config to original structure (ensure dict for type checker)
            if isinstance(mcp_config, dict):
                mcp_config["mcpServers"] = servers_dict
            else:
                # produce standard object structure holding the dict
                mcp_config = {"mcpServers": servers_dict}

            new_json_str = json.dumps(mcp_config, indent=2)

            # Save back to settings (triggering reinitialization)
            set_settings_delta({"mcp_servers": "[]"})  # force reinit
            set_settings_delta({"mcp_servers": new_json_str})

            # Give backend a short moment to reload servers
            time.sleep(1)
            status = MCPConfig.get_instance().get_servers_status()
            return {"success": True, "status": status}
        except Exception as e:
            return {"success": False, "error": str(e)} 