"""
Admin API endpoint for managing global default sudo commands.
Admin-only endpoint for managing the list of default sudo commands
that get assigned to new regular users.
"""

from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_admin_sudo_manager
from flask import session


class AdminSudoDefaults(ApiHandler):
    """Admin-only endpoint for managing global default sudo commands"""

    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def requires_csrf(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        """Process admin sudo defaults management requests"""
        try:
            # Check if current user is admin
            if not session.get('is_admin', False):
                return Response("Admin privileges required", status=403)

            # Get action from input
            action = input.get("action")
            if not action:
                return {"success": False, "error": "Action not specified"}

            # Get admin sudo manager
            manager = get_admin_sudo_manager()

            if action == "get":
                # Get current global default commands
                try:
                    current_commands = manager.get_global_default_commands()
                    factory_commands = manager.get_factory_defaults()

                    return {
                        "success": True,
                        "current_commands": current_commands,
                        "factory_commands": factory_commands,
                        "total_current": len(current_commands),
                        "total_factory": len(factory_commands)
                    }
                except Exception as e:
                    return {"success": False, "error": f"Failed to get commands: {str(e)}"}

            elif action == "update":
                # Update global default commands
                commands = input.get("commands")
                if not isinstance(commands, list):
                    return {"success": False, "error": "Commands must be a list"}

                try:
                    success = manager.update_global_default_commands(commands)
                    if success:
                        updated_commands = manager.get_global_default_commands()
                        return {
                            "success": True,
                            "message": f"Updated global default commands ({len(updated_commands)} commands)",
                            "commands": updated_commands
                        }
                    else:
                        return {"success": False, "error": "Failed to update commands"}
                except Exception as e:
                    return {"success": False, "error": f"Failed to update commands: {str(e)}"}

            elif action == "reset":
                # Reset to factory defaults
                try:
                    success = manager.reset_to_factory_defaults()
                    if success:
                        factory_commands = manager.get_factory_defaults()
                        return {
                            "success": True,
                            "message": f"Reset to factory defaults ({len(factory_commands)} commands)",
                            "commands": factory_commands
                        }
                    else:
                        return {"success": False, "error": "Failed to reset to factory defaults"}
                except Exception as e:
                    return {"success": False, "error": f"Failed to reset: {str(e)}"}

            elif action == "apply_to_all":
                # Apply current defaults to all existing users
                merge = input.get("merge", True)  # Default to merge mode

                try:
                    success = manager.apply_defaults_to_all_users(merge=merge)
                    action_type = "merged with" if merge else "replaced"

                    if success:
                        return {
                            "success": True,
                            "message": f"Applied default commands to all users ({action_type} existing commands)"
                        }
                    else:
                        return {"success": False, "error": "Failed to apply defaults to all users"}
                except Exception as e:
                    return {"success": False, "error": f"Failed to apply defaults: {str(e)}"}

            elif action == "apply_to_user":
                # Apply current defaults to specific user
                username = input.get("username")
                if not username:
                    return {"success": False, "error": "Username not specified"}

                merge = input.get("merge", True)  # Default to merge mode

                try:
                    success = manager.apply_defaults_to_user(username, merge=merge)
                    action_type = "merged with" if merge else "replaced"

                    if success:
                        return {
                            "success": True,
                            "message": f"Applied default commands to user '{username}' ({action_type} existing commands)"
                        }
                    else:
                        return {"success": False, "error": f"Failed to apply defaults to user '{username}'"}
                except Exception as e:
                    return {"success": False, "error": f"Failed to apply defaults to user: {str(e)}"}

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except PermissionError:
            return {"success": False, "error": "Admin privileges required"}
        except Exception as e:
            return {"success": False, "error": f"Internal server error: {str(e)}"}
