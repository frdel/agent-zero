from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_user_manager
from python.helpers.authz import is_request_admin
import json


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
            if not is_request_admin():
                return Response(json.dumps({"error": "Admin privileges required"}), status=403, mimetype="application/json")

            username = input.get('username')
            if not username:
                return {"error": "Username is required"}

            user_manager = get_user_manager()
            if user_manager.delete_user(username):
                return {"success": True, "message": f"User '{username}' deleted successfully"}
            return {"error": f"Failed to delete user '{username}'"}
        except Exception as e:
            return {"error": f"Failed to delete user: {str(e)}"}
