from python.helpers.task_scheduler import ScheduledTask, TaskSchedule, SchedulerTaskList, TaskState
import asyncio

slist = SchedulerTaskList.get()

print(slist.model_dump_json(indent=4))

for task in slist.tasks:
    t = slist.get_task_by_uuid(task.uuid)
    t.update(state=TaskState.DISABLED)
    print("-" * 100)
    print(t.model_dump_json(indent=4))

print("-" * 100)

print(slist.model_dump_json(indent=4))
