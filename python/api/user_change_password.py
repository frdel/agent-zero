from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_user_manager
from flask import session


class UserChangePassword(ApiHandler):

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
        try:
            current_username = session.get('username')
            if not current_username:
                return {"error": "Not authenticated"}

            # Get input parameters
            target_username = input.get('username')
            new_password = input.get('new_password')
            current_password = input.get('current_password')  # For verification

            if not target_username or not new_password:
                return {"error": "Username and new password are required"}

            if len(new_password) < 6:
                return {"error": "Password must be at least 6 characters long"}

            user_manager = get_user_manager()
            current_user = user_manager.get_user(current_username)
            target_user = user_manager.get_user(target_username)

            if not current_user or not target_user:
                return {"error": "User not found"}

            # Check permissions:
            # 1. Admin can change any user's password
            # 2. User can change their own password (must provide current password)
            if current_user.is_admin:
                # Admin can change any password without current password verification
                pass
            elif current_username == target_username:
                # User changing their own password - verify current password
                if not current_password:
                    return {"error": "Current password is required to change your own password"}

                if not user_manager.authenticate(current_username, current_password):
                    return {"error": "Current password is incorrect"}
            else:
                # Regular user trying to change someone else's password
                return {"error": "Permission denied: You can only change your own password"}

            # Prevent changing admin username
            if target_username == "admin" and current_username != "admin":
                return {"error": "Only the admin user can change the admin password"}

            # Change the password
            success = user_manager.update_user(target_username, password=new_password)

            if success:
                # If the user changed their own password, invalidate their session
                # This forces them to log in again with the new password
                if current_username == target_username:
                    session.clear()

                return {
                    'success': True,
                    'message': f'Password for "{target_username}" changed successfully',
                    'logout': current_username == target_username
                }
            else:
                return {"error": f'Failed to change password for "{target_username}"'}

        except Exception as e:
            return {"error": f"Failed to change password: {str(e)}"}
