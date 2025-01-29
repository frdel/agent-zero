from python.helpers.tool import Tool, Response
from python.helpers.scheduler import scheduler, scheduled_task, SchedulingRequest
import uuid
from datetime import datetime, timedelta
import time

# TODO: add a way to view this scheduled task on the UI, either in the current or in another chat
# -> maybe use the corresponding chat_id for this


class ScheduledTaskAddTool(Tool):

    async def execute(self, task_prompt="", seconds_delay="", **kwargs):
        # trigger_name: either "cron", "interval", or "date"
        seconds_delay = int(seconds_delay) if seconds_delay else 0

        if not task_prompt:
            msg = "No task prompt to schedule provided - please provide a task to schedule"
            return Response(message=msg, break_loop=True)
        json = {"text": task_prompt, "message_id": uuid.uuid4()}
        sr = SchedulingRequest(json)
        run_time = datetime.now() + timedelta(seconds=15)
        scheduler.add_job(scheduled_task, 'date', run_date=run_time, args=[sr])

        msg = f"Task scheduled with delay of {seconds_delay} seconds"

        return Response(message=msg, break_loop=True)
