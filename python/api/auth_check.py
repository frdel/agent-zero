from python.helpers.api import ApiHandler
from flask import Request, Response


class AuthCheck(ApiHandler):

    @classmethod
    def requires_auth(cls) -> bool:
        return True  # Requires session-based auth

    @classmethod
    def requires_csrf(cls) -> bool:
        return False  # No CSRF required for simple auth check

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST", "GET"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        """Simple endpoint to check if user is authenticated"""
        try:
            # If we get here, the user is authenticated (requires_auth passed)
            from flask import session
            from python.helpers.user_management import get_user_manager

            username = session.get('username')
            # Removed debug output and unused is_admin

            if username:
                user_manager = get_user_manager()
                user = user_manager.users.get(username)
                if user:
                    return {
                        "authenticated": True,
                        "user": {
                            "username": user.username,
                            "is_admin": user.is_admin
                        }
                    }

            return {"authenticated": False, "error": "No valid session"}
        except Exception as e:
            return {"authenticated": False, "error": str(e)}
