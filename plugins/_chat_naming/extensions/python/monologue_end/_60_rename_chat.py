import asyncio

from agent import AgentContext, AgentContextType, LoopData
from helpers.extension import Extension
from helpers.notification import NotificationManager, NotificationPriority, NotificationType
from plugins._chat_naming.helpers import naming

_UNSET_SCHEDULED_NAME = object()


class RenameChat(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent or self.agent is not self.agent.context.agent0:
            return
        if self.agent.context.type != AgentContextType.USER:
            return
        if self.agent.context.get_output_data("parent_context_id"):
            return

        config = naming.get_config(self.agent)
        if not config["automatic_naming"]:
            return
        if self.agent.context.get_data(naming.MANUAL_NAME_KEY):
            return

        mode = config["automatic_naming_mode"]
        if mode == naming.MODE_ONCE and str(self.agent.context.name or "").strip():
            return

        messages = naming.get_user_messages(
            self.agent,
            limit=None if mode == naming.MODE_ONCE else naming.RECENT_USER_MESSAGES,
        )
        if not messages:
            return
        if mode == naming.MODE_ONCE:
            messages = messages[:1]

        asyncio.create_task(
            self.change_name(
                messages=messages,
                request_sequence=naming.latest_user_sequence(self.agent),
                only_if_unnamed=(mode == naming.MODE_ONCE),
                scheduled_name=self.agent.context.name,
            )
        )

    async def change_name(
        self,
        *,
        messages: list[str],
        request_sequence: int,
        only_if_unnamed: bool,
        scheduled_name: object = _UNSET_SCHEDULED_NAME,
    ) -> None:
        if not self.agent:
            return

        try:
            new_name = await naming.generate_name(
                self.agent,
                user_messages=messages,
                current_name=self.agent.context.name,
            )
            if only_if_unnamed and str(self.agent.context.name or "").strip():
                return
            if naming.latest_user_sequence(self.agent) != request_sequence:
                return
            if (
                scheduled_name is not _UNSET_SCHEDULED_NAME
                and self.agent.context.name != scheduled_name
            ):
                return
            if self.agent.context.get_data(naming.MANUAL_NAME_KEY):
                return
            if AgentContext.get(self.agent.context.id) is not self.agent.context:
                return
            naming.save_context_name(self.agent, new_name)
        except Exception:
            NotificationManager.send_notification(
                type=NotificationType.ERROR,
                priority=NotificationPriority.NORMAL,
                title="Chat Naming Failed",
                message="Automatic chat naming failed because the Utility Model was not reachable.",
                detail=(
                    "Automatic chat naming uses the Utility Model. Check Settings > Models > "
                    "Utility Model, provider/API key, and network reachability."
                ),
                display_time=10,
                group="chat_naming",
                id=f"chat_naming_failed_{self.agent.context.id}",
            )
