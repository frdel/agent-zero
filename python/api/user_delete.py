from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_user_manager
from flask import session


class UserDelete(ApiHandler):

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
            # Check if current user is admin
            if not session.get('is_admin', False):
                return Response("Admin privileges required", status=403)

            # Validate input
            username = input.get('username')

            if not username:
                return {"error": "Username is required"}

            # Cannot delete yourself
            if username == session.get('username'):
                return {"error": "Cannot delete your own account"}

            # Delete user
            user_manager = get_user_manager()
            try:
                success = user_manager.delete_user(username)

                if success:
                    return {
                        'success': True,
                        'message': f'User "{username}" deleted successfully'
                    }
                else:
                    return {"error": f'User "{username}" not found'}

            except ValueError as e:
                return {"error": str(e)}

        except Exception as e:
            return {"error": f"Failed to delete user: {str(e)}"}
