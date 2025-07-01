from python.helpers.tool import Tool, Response
from agent import AgentContext


class NotifyUserTool(Tool):

    async def execute(self, **kwargs):

        message = self.args.get("message", "")
        title = self.args.get("title", "")
        detail = self.args.get("detail", "")
        notification_type = self.args.get("type", "info")

        if notification_type not in ["info", "success", "warning", "error", "progress"]:
            return Response(message=f"Invalid notification type: {notification_type}", break_loop=False)

        if not message:
            return Response(message="Message is required", break_loop=False)

        AgentContext.get_notification_manager().add_notification(
            message=message,
            title=title,
            detail=detail,
            type=notification_type,
        )
        return Response(message=self.agent.read_prompt("fw.notify_user.notification_sent.md"), break_loop=False)
