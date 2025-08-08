import time
from python.helpers.api import ApiHandler, Request, Response

from typing import Any

from python.helpers.mcp_handler import MCPConfig
from python.helpers.settings import set_settings_delta


class McpServersApply(ApiHandler):
    async def process(self, input: dict[Any, Any], request: Request) -> dict[Any, Any] | Response:
        mcp_servers = input["mcp_servers"]
        try:
            # Ensure MCP config is updated in admin settings (global config)
            from python.helpers.user_management import get_user_manager, set_current_user, get_current_user

            user_manager = get_user_manager()
            admin_user = user_manager.get_user("admin")
            original_user = None

            try:
                # Try Flask session first (works across threads)
                try:
                    from flask import session
                    username = session.get('username')
                    if username:
                        original_user = user_manager.get_user(username)
                    else:
                        raise RuntimeError("No session username")
                except (RuntimeError, ImportError):
                    # Fallback to thread-local storage
                    original_user = get_current_user()
            except RuntimeError:
                pass

            try:
                if admin_user:
                    set_current_user(admin_user)

                # MCPConfig.update(mcp_servers)  # done in settings automatically
                set_settings_delta({"mcp_servers": "[]"})  # to force reinitialization
                set_settings_delta({"mcp_servers": mcp_servers})
            finally:
                # Restore original user context
                set_current_user(original_user)

            time.sleep(1) # wait at least a second
            # MCPConfig.wait_for_lock() # wait until config lock is released
            status = MCPConfig.get_instance().get_servers_status()
            return {"success": True, "status": status}

        except Exception as e:
            return {"success": False, "error": str(e)}
