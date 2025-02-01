from python.helpers.tool import Tool, Response
from python.helpers.scheduler import scheduler, scheduled_task, SchedulingRequest
import uuid
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger


class ScheduledTaskAddTool(Tool):
    async def execute(self, task_prompt="", seconds_delay="", cron_expression="", **kwargs):
        if not task_prompt:
            msg = "No task prompt to schedule provided - please provide a task to schedule"
            return Response(message=msg, break_loop=True)

        # Determine which trigger type to use
        # Default to date if not specified
        trigger_type = kwargs.get('trigger_type', 'date')

        if trigger_type not in ['date', 'cron']:
            msg = "Invalid trigger_type. Must be either 'date' or 'cron'"
            return Response(message=msg, break_loop=True)

        json = {"text": task_prompt, "message_id": str(uuid.uuid4())}
        sr = SchedulingRequest(json)

        if trigger_type == 'date':
            # Handle one-time scheduling with delay
            seconds_delay = int(seconds_delay) if seconds_delay else 0
            run_date = datetime.now() + timedelta(seconds=seconds_delay)
            scheduler.add_job(scheduled_task, 'date',
                              run_date=run_date, args=[sr])
            msg = f"Task scheduled with delay of {seconds_delay} seconds"
        else:
            # Handle cron scheduling
            if not cron_expression:
                msg = "Cron expression is required when using 'cron' trigger type"
                return Response(message=msg, break_loop=True)

            try:
                # Validate cron expression
                trigger = CronTrigger.from_crontab(cron_expression)
                scheduler.add_job(scheduled_task, trigger, args=[sr])
                msg = f"Task scheduled with cron expression: {cron_expression}"
            except Exception as e:
                msg = f"Invalid cron expression: {str(e)}"
                return Response(message=msg, break_loop=True)

        return Response(message=msg, break_loop=False)
