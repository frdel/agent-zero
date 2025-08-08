from python.helpers.api import ApiHandler, Request, Response
import json
from python.helpers.user_management import get_user_manager
from flask import session


# Prefer thread-local current user (temporary elevation) if available
def _is_threadlocal_admin() -> bool:
    try:
        from python.helpers.user_management import get_current_user
        user = get_current_user()
        return bool(user and user.is_admin)
    except Exception:
        return False


def _is_session_temp_admin() -> bool:
    try:
        import time
        temp_admin = session.get('temp_admin')
        temp_admin_username = session.get('temp_admin_username')
        temp_admin_expires = session.get('temp_admin_expires')
        if temp_admin and temp_admin_username and temp_admin_expires:
            return int(time.time()) < int(temp_admin_expires)
        return False
    except Exception:
        return False


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
            # Get user manager instance for authentication checks
            user_manager = get_user_manager()

            # Check if current user is admin - prefer thread-local (temporary elevation)
            is_admin = False

            # Method 0: Thread-local temporary elevation (set by user_authenticate temporary flow)
            if _is_threadlocal_admin() or _is_session_temp_admin():
                is_admin = True

            # Method 1: Flask session
            if session.get('is_admin', False):
                is_admin = True

            # Method 2: Check username directly if session is unreliable
            username = session.get('username')
            if username == 'admin':
                is_admin = True

            # Method 3: Check Authorization header as fallback
            auth = request.authorization
            if auth and auth.username == 'admin' and auth.password:
                if user_manager.authenticate(auth.username, auth.password):
                    is_admin = True

            if not is_admin:
                return Response(
                    json.dumps({"error": "Admin privileges required"}),
                    status=403,
                    mimetype="application/json",
                )

            # Get all users (user_manager already initialized above)
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
