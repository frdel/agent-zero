"""
Admin API endpoint for managing global default sudo commands.
Admin-only endpoint for managing the list of default sudo commands
that get assigned to new regular users.
"""

from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_admin_sudo_manager
from python.helpers.authz import is_request_admin
import json
from python.helpers.user_management import DefaultSudoCommands


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
            if not is_request_admin():
                return Response(json.dumps({"error": "Admin privileges required"}), status=403, mimetype="application/json")

            # Get action from input
            action = input.get("action")
            if not action:
                return {"success": False, "error": "Action not specified"}

            # Get admin sudo manager for sudo management
            admin_manager = get_admin_sudo_manager()

            if action == "get":
                # Get current global default commands
                try:
                    current_commands = admin_manager.get_global_default_commands()
                    factory_commands = admin_manager.get_factory_defaults()

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

                # Validate all commands
                for cmd in commands:
                    if not DefaultSudoCommands.validate_sudo_command(cmd):
                        return {"success": False, "error": f"Invalid command: {cmd}"}

                # Update global defaults
                success = admin_manager.update_global_default_commands(commands)
                if success:
                    updated_commands = admin_manager.get_global_default_commands()
                    return {
                        "success": True,
                        "message": f"Updated global default commands ({len(updated_commands)} commands)",
                        "commands": updated_commands
                    }
                else:
                    return {"success": False, "error": "Failed to update global defaults"}

            elif action == "reset":
                # Reset to factory defaults
                success = admin_manager.reset_to_factory_defaults()
                if success:
                    factory_commands = admin_manager.get_factory_defaults()
                    return {
                        "success": True,
                        "message": f"Reset to factory defaults ({len(factory_commands)} commands)",
                        "commands": factory_commands
                    }
                else:
                    return {"success": False, "error": "Failed to reset to factory defaults"}

            elif action == "apply_to_all":
                # Apply current defaults to all existing users
                merge = input.get("merge", True)  # Default to merge mode

                success = admin_manager.apply_defaults_to_all_users(merge=merge)
                action_type = "merged with" if merge else "replaced"

                if success:
                    return {
                        "success": True,
                        "message": f"Applied default commands to all users ({action_type} existing commands)"
                    }
                else:
                    return {"success": False, "error": "Failed to apply defaults to all users"}

            elif action == "apply_to_user":
                # Apply current defaults to specific user
                username = input.get("username")
                if not username:
                    return {"success": False, "error": "Username not specified"}

                merge = input.get("merge", True)  # Default to merge mode

                # Use admin manager method
                try:
                    success = admin_manager.apply_defaults_to_user(username, merge=merge)
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
