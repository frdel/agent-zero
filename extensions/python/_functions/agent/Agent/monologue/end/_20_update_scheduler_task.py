from helpers.extension import Extension


class UpdateSchedulerTask(Extension):
    async def execute(self, data: dict, **kwargs):
        if not self.agent or self.agent is not self.agent.context.agent0:
            return
        result = data.get("result")
        if data.get("exception") is not None or not isinstance(result, str):
            return

        from helpers.task_scheduler import TaskScheduler, TaskState, _now

        context = self.agent.context
        task_uuid = context.get_data("scheduler_task_uuid") or context.id
        await TaskScheduler.get().update_task_checked(
            task_uuid,
            lambda task: task.context_id == context.id and task.state == TaskState.ERROR,
            state=TaskState.IDLE,
            last_run=_now(),
            last_result=result,
        )
