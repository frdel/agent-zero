import uuid
from helpers.tool import Tool, Response
from agent import AgentContext
from helpers.notification import NotificationPriority, NotificationType
from helpers.strings import truncate_text

PRIORITY_ALIASES = {"normal": NotificationPriority.NORMAL, "high": NotificationPriority.HIGH}

class NotifyUserTool(Tool):

    async def execute(self, **kwargs):

        message = self.args.get("message", "")
        title = self.args.get("title", "")
        detail = self.args.get("detail", "")
        notification_type = self.args.get("type", NotificationType.INFO)
        priority = self.args.get("priority", "high") # by default, agents should notify with high priority

        try:
            notification_type = NotificationType(notification_type)
        except ValueError:
            return Response(message=f"Invalid notification type: {notification_type}", break_loop=False)

        try:
            priority = PRIORITY_ALIASES[priority]
        except (KeyError, TypeError):
            return Response(message=f"Invalid notification priority: {priority}", break_loop=False)

        if not message:
            return Response(message="Message is required", break_loop=False)

        AgentContext.get_notification_manager().add_notification(
            message=message,
            title=title,
            detail=detail,
            type=notification_type,
            priority=priority,
            display_time=30, # agent notifications get the longer default toast time
        )
        return Response(message=self.agent.read_prompt("fw.notify_user.notification_sent.md"), break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="notify_user",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self):
        title = str(self.args.get("title") or "").strip()
        text = f"Notifying user: {truncate_text(title, 60)}" if title else "Notifying user"
        return f"icon://notifications {text}"
