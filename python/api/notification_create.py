from python.helpers.api import ApiHandler
from flask import Request, Response
from python.helpers.notification import NotificationManager, NotificationPriority, NotificationType


class NotificationCreate(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True

    async def process(self, input: dict, request: Request) -> dict | Response:
        # Extract notification data
        notification_type = input.get("type", NotificationType.INFO.value)
        priority = input.get("priority", NotificationPriority.NORMAL.value)
        message = input.get("message", "")
        title = input.get("title", "")
        detail = input.get("detail", "")
        display_time = input.get("display_time", 3)  # Default to 3 seconds
        group = input.get("group", "")  # Group parameter for notification grouping

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
            return {
                "success": False,
                "error": f"Invalid notification type: {notification_type}",
            }

        # Create notification using the appropriate helper method
        try:
            notification = NotificationManager.send_notification(
                notification_type,
                priority,
                message,
                title,
                detail,
                display_time,
                group,
            )

            return {
                "success": True,
                "notification_id": notification.id,
                "message": "Notification created successfully",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create notification: {str(e)}",
            }
