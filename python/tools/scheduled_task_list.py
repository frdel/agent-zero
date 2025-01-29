from python.helpers.tool import Tool, Response
from python.helpers.scheduler import scheduler


class ScheduledTaskListTool(Tool):

    async def execute(self, **kwargs):
        jobs = scheduler.get_jobs()
        msg = self.agent.read_prompt(
            "tool.scheduled_task.list_tool_response.md",
            scheduled_tasks=jobs
        )
        return Response(message=msg, break_loop=True)
