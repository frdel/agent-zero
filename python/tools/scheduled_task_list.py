# scheduled_task_list.py
from python.helpers.tool import Tool, Response
from python.helpers.scheduler import SchedulingRequest, scheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger


class ScheduledTaskListTool(Tool):

    async def execute(self, **kwargs):
        jobs = scheduler.get_jobs()
        tasks_info = []

        for job in jobs:
            job_id = job.id
            next_run = job.next_run_time
            trigger = job.trigger

            # Extract SchedulingRequest arguments
            args = job.args
            if args and isinstance(args[0], SchedulingRequest):
                scheduling_request = args[0]
                json_data = scheduling_request.get_json()
            else:
                json_data = {}

            if isinstance(trigger, CronTrigger):
                trigger_info = f"Cron: {trigger}"
            elif isinstance(trigger, DateTrigger):
                trigger_info = f"Date: {next_run}"
            else:
                trigger_info = str(trigger)

            tasks_info.append({
                'id': job_id,
                'trigger_info': trigger_info,
                'prompt': json_data['text']
            })

        msg = self.agent.read_prompt(
            "tool.scheduled_task.list_tool_response.md",
            scheduled_tasks=tasks_info
        )
        return Response(message=msg, break_loop=True)
