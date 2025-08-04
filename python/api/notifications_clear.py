from python.helpers.api import ApiHandler
from flask import Request, Response
from agent import AgentContext


class NotificationsClear(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True

    async def process(self, input: dict, request: Request) -> dict | Response:
        # Get the global notification manager
        notification_manager = AgentContext.get_notification_manager()

        # Clear all notifications
        notification_manager.clear_all()

        return {"success": True, "message": "All notifications cleared"}
