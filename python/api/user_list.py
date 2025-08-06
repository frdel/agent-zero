from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_user_manager
from flask import session


class UserList(ApiHandler):

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

            # Get all users
            user_manager = get_user_manager()
            users = user_manager.list_users()

            return {
                'success': True,
                'users': [
                    {
                        'username': user.username,
                        'is_admin': user.is_admin,
                        'created_at': user.created_at.isoformat()
                    }
                    for user in users
                ]
            }

        except Exception as e:
            return {"error": f"Failed to list users: {str(e)}"}
