from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_user_manager
import json
from python.helpers.authz import is_request_admin


class UserCreate(ApiHandler):

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
            if not is_request_admin():
                return Response(json.dumps({"error": "Admin privileges required"}), status=403, mimetype="application/json")

            # Validate input
            username = input.get('username')
            password = input.get('password')
            is_admin = input.get('is_admin', False)

            if not username or not password:
                return {"error": "Username and password are required"}

            if len(username) < 3:
                return {"error": "Username must be at least 3 characters long"}

            if len(password) < 6:
                return {"error": "Password must be at least 6 characters long"}

            # Create user
            user_manager = get_user_manager()
            try:
                user = user_manager.create_user(username, password, is_admin)

                return {
                    'success': True,
                    'message': f'User "{username}" created successfully',
                    'user': {
                        'username': user.username,
                        'is_admin': user.is_admin,
                        'created_at': user.created_at.isoformat()
                    }
                }

            except ValueError as e:
                return {"error": str(e)}

        except Exception as e:
            return {"error": f"Failed to create user: {str(e)}"}
