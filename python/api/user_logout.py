from python.helpers.api import ApiHandler, Request, Response
from flask import session


class UserLogout(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True  # Must be authenticated to logout

    @classmethod
    def requires_csrf(cls) -> bool:
        return True  # Require CSRF protection

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        """Logout user by clearing session"""
        try:
            # Clear thread-local user context
            from python.helpers.user_management import set_current_user
            try:
                set_current_user(None)
            except Exception:
                pass  # Thread-local clearing failed, that's fine

            # Clear the entire session
            session.clear()

            # Clear central username storage
            try:
                from python.helpers.user_management import get_user_manager
                get_user_manager().set_central_current_username(None)
            except Exception:
                pass

            # Force session to be saved
            session.modified = True

            return {
                'success': True,
                'message': 'Logged out successfully'
            }

        except Exception as e:
            return {"error": f"Logout failed: {str(e)}"}
