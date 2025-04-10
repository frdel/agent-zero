from python.helpers.tool import Tool, Response
from python.helpers.scheduler import scheduler


class ScheduledTaskRemoveTool(Tool):

    async def execute(self, task_id="", **kwargs):
        if not task_id:
            msg = "No task ID provided. Please provide the ID of the task you want to remove."
            return Response(message=msg, break_loop=False)

        try:
            # Remove the job from the scheduler
            job = scheduler.get_job(task_id)
            if job:
                scheduler.remove_job(task_id)
                msg = f"Task with ID {task_id} has been successfully removed."
            else:
                msg = f"No task found with ID {task_id}"

            return Response(message=msg, break_loop=False)

        except Exception as e:
            msg = f"An error occurred while trying to remove the task: {
                str(e)}"
            return Response(message=msg, break_loop=False)
