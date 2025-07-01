from python.helpers.api import ApiHandler
from flask import Request, Response
from python.helpers.notification import AgentNotification, NotificationType


class NotificationCreate(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True

    async def process(self, input: dict, request: Request) -> dict | Response:
        # Extract notification data
        notification_type = input.get("type", "info")
        message = input.get("message", "")
        title = input.get("title", "")
        detail = input.get("detail", "")
        display_time = input.get("display_time", 3)  # Default to 3 seconds

        # Validate required fields
        if not message:
            return {"success": False, "error": "Message is required"}

        # Validate display_time
        try:
            display_time = int(display_time)
            if display_time <= 0:
                display_time = 3  # Reset to default if invalid
        except (ValueError, TypeError):
            display_time = 3  # Reset to default if not convertible to int

        # Validate notification type
        try:
            if isinstance(notification_type, str):
                notification_type = NotificationType(notification_type.lower())
        except ValueError:
            return {"success": False, "error": f"Invalid notification type: {notification_type}"}

        # Create notification using the appropriate helper method
        try:
            if notification_type == NotificationType.INFO:
                notification = AgentNotification.info(message, title, detail, display_time)
            elif notification_type == NotificationType.SUCCESS:
                notification = AgentNotification.success(message, title, detail, display_time)
            elif notification_type == NotificationType.WARNING:
                notification = AgentNotification.warning(message, title, detail, display_time)
            elif notification_type == NotificationType.ERROR:
                notification = AgentNotification.error(message, title, detail, display_time)
            elif notification_type == NotificationType.PROGRESS:
                notification = AgentNotification.progress(message, title, detail, display_time)
            else:
                notification = AgentNotification.info(message, title, detail, display_time)

            return {
                "success": True,
                "notification_id": notification.id,
                "message": "Notification created successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create notification: {str(e)}"
            }
