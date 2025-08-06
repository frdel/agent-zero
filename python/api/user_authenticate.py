from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_user_manager, set_current_user
from flask import session


class UserAuthenticate(ApiHandler):

    @classmethod
    def requires_auth(cls) -> bool:
        return False  # This endpoint doesn't require basic auth

    @classmethod
    def requires_csrf(cls) -> bool:
        return False  # Don't require CSRF for initial authentication

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            # Get credentials from input
            username = input.get('username')
            password = input.get('password')

            if not username or not password:
                return {"error": "Username and password are required"}

            # Authenticate user
            user_manager = get_user_manager()
            if user_manager.authenticate(username, password):
                user = user_manager.get_user(username)
                if user:
                    # Set up session
                    session.clear()  # Clear any existing session data
                    session['username'] = user.username
                    session['is_admin'] = user.is_admin
                    session.permanent = True

                    # Force session to be saved
                    session.modified = True

                    # Set current user context for this request
                    set_current_user(user)

                    return {
                        'success': True,
                        'message': 'Authentication successful',
                        'user': {
                            'username': user.username,
                            'is_admin': user.is_admin
                        }
                    }
                else:
                    return {"error": "User not found"}
            else:
                return {"error": "Invalid username or password"}

        except Exception as e:
            return {"error": f"Authentication failed: {str(e)}"}
