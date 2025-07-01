from python.helpers.api import ApiHandler
from flask import Request, Response
from agent import AgentContext


class NotificationsMarkRead(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True

    async def process(self, input: dict, request: Request) -> dict | Response:
        notification_ids = input.get("notification_ids", [])
        mark_all = input.get("mark_all", False)

        notification_manager = AgentContext.get_notification_manager()

        if mark_all:
            notification_manager.mark_all_read()
            return {"success": True, "message": "All notifications marked as read"}

        if not notification_ids:
            return {"success": False, "error": "No notification IDs provided"}

        # Mark specific notifications as read
        marked_count = 0
        for notification_id in notification_ids:
            # Find notification by ID and mark as read
            for notification in notification_manager.notifications:
                if notification.id == notification_id and not notification.read:
                    notification.mark_read()
                    marked_count += 1
                    break

        return {
            "success": True,
            "marked_count": marked_count,
            "message": f"Marked {marked_count} notifications as read"
        }
