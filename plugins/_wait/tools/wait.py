import asyncio
from datetime import timedelta
from helpers.tool import Tool, Response
from helpers.print_style import PrintStyle
from plugins._wait.helpers.wait import managed_wait
from helpers.localization import Localization

class WaitTool(Tool):

    async def execute(self, **kwargs) -> Response:
        await self.agent.handle_intervention()

        until_timestamp_str = self.args.get("until")

        is_duration_wait = not bool(until_timestamp_str)

        now = Localization.get().now()
        target_time = None

        try:
            if until_timestamp_str:
                target_time = Localization.get().localtime_str_to_utc_dt(until_timestamp_str)
                if not target_time:
                    raise ValueError(f"Invalid timestamp format: {until_timestamp_str}")
            else:
                seconds = int(self.args.get("seconds", 0) or 0)
                minutes = int(self.args.get("minutes", 0) or 0)
                hours = int(self.args.get("hours", 0) or 0)
                days = int(self.args.get("days", 0) or 0)
                wait_duration = timedelta(
                    days=days,
                    hours=hours,
                    minutes=minutes,
                    seconds=seconds,
                )
                if wait_duration.total_seconds() <= 0:
                    return Response(
                        message="Wait duration must be positive.",
                        break_loop=False,
                    )
                target_time = now + wait_duration
        except (TypeError, ValueError) as e:
            return Response(
                message=f"Invalid wait arguments: {e}",
                break_loop=False,
            )

        if target_time <= now:
            return Response(
                message=f"Target time {Localization.get().serialize_datetime(target_time)} is in the past.",
                break_loop=False,
            )

        PrintStyle.info(f"Waiting until {Localization.get().serialize_datetime(target_time)}...")

        target_time = await managed_wait(
            agent=self.agent,
            target_time=target_time,
            is_duration_wait=is_duration_wait,
            log=self.log,
            get_heading_callback=self.get_heading
        )

        if self.log:
            self.log.update(heading=self.get_heading("Done", done=True))

        message = self.agent.read_prompt(
            "fw.wait_complete.md",
            target_time=Localization.get().serialize_datetime(target_time)
        )

        return Response(
            message=message,
            break_loop=False,
        )

    def get_log_object(self):
        return self.agent.context.log.log(
            type="wait",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
        )

    def get_heading(self, text: str = "", done: bool = False):
        done_icon = " icon://done_all" if done else ""
        if not text:
            text = "Waiting..."
        return f"icon://timer Wait: {text}{done_icon}"
