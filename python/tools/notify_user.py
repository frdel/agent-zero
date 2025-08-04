from python.helpers.tool import Tool, Response
from agent import AgentContext
from python.helpers.notification import NotificationPriority, NotificationType

class NotifyUserTool(Tool):

    async def execute(self, **kwargs):

        message = self.args.get("message", "")
        title = self.args.get("title", "")
        detail = self.args.get("detail", "")
        notification_type = self.args.get("type", NotificationType.INFO)
        priority = self.args.get("priority", NotificationPriority.HIGH) # by default, agents should notify with high priority
        timeout = int(self.args.get("timeout", 30)) # agent's notifications should have longer timeouts

        try:
            notification_type = NotificationType(notification_type)
        except ValueError:
            return Response(message=f"Invalid notification type: {notification_type}", break_loop=False)

        try:
            priority = NotificationPriority(priority)
        except ValueError:
            return Response(message=f"Invalid notification priority: {priority}", break_loop=False)

        if not message:
            return Response(message="Message is required", break_loop=False)

        AgentContext.get_notification_manager().add_notification(
            message=message,
            title=title,
            detail=detail,
            type=notification_type,
            priority=priority,
            display_time=timeout,
        )
        return Response(message=self.agent.read_prompt("fw.notify_user.notification_sent.md"), break_loop=False)
