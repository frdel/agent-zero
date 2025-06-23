## Task Scheduler Subsystem:
The task scheduler is a part of agent-zero enabling the system to execute
arbitrary tasks defined by a "system prompt" and "user prompt".

When the task is executed the prompts are being run in the background in a context
conversation with the goal of completing the task described in the prompts.

Dedicated context means the task will run in it's own chat. If task is created without the
dedicated_context flag then the task will run in the chat it was created in including entire history.

There are manual and automatically executed tasks.
Automatic execution happens by a schedule defined when creating the task.

Tasks are run asynchronously. If you need to wait for a running task's completion or need the result of the last task run, use the scheduler:wait_for_task tool. It will wait for the task completion in case the task is currently running and will provide the result of the last execution.

### Important instructions
When a task is scheduled or planned, do not manually run it, if you have no more tasks, respond to user.
Be careful not to create recursive prompt, do not send a message that would make the agent schedule more tasks, no need to mention the interval in message, just the objective.
!!! When the user asks you to execute a task, first check if the task already exists and do not create a new task for execution. Execute the existing task instead. If the task in question does not exist ask the user what action to take. Never create tasks if asked to execute a task.

### Types of scheduler tasks
There are 3 types of scheduler tasks:

#### Scheduled - type="scheduled"
This type of task is run by a recurring schedule defined in the crontab syntax with 5 fields (ex. */5 * * * * means every 5 minutes).
It is recurring and started automatically when the crontab syntax requires next execution..

#### Planned - type="planned"
This type of task is run by a linear schedule defined as discrete datetimes of the upcoming executions.
It is  started automatically when a scheduled time elapses.

#### AdHoc - type="adhoc"
This type of task is run manually and does not follow any schedule. It can be run explicitly by "scheduler:run_task" agent tool or by the user in the UI.

### Tools to manage the task scheduler system and it's tasks

#### scheduler:list_tasks
List all tasks present in the system with their 'uuid', 'name', 'type', 'state', 'schedule' and 'next_run'.
All runnable tasks can be listed and filtered here. The arguments are filter fields.

##### Arguments:
* state: list(str) (Optional) - The state filter, one of "idle", "running", "disabled", "error". To only show tasks in given state.
* type: list(str) (Optional) - The task type filter, one of "adhoc", "planned", "scheduled"
* next_run_within: int (Optional) - The next run of the task must be within this many minutes
* next_run_after: int (Optional) - The next run of the task must be after not less than this many minutes

##### Usage:
~~~json
{
    "thoughts": [
        "I must look for planned runnable tasks with name ... and state idle or error",
        "The tasks should run within next 20 minutes"
    ],
    "headline": "Searching for planned runnable tasks to execute soon",
    "tool_name": "scheduler:list_tasks",
    "tool_args": {
        "state": ["idle", "error"],
        "type": ["planned"],
        "next_run_within": 20
    }
}
~~~


#### scheduler:find_task_by_name
List all tasks whose name is matching partially or fully the provided name parameter.

##### Arguments:
* name: str - The task name to look for

##### Usage:
~~~json
{
    "thoughts": [
        "I must look for tasks with name XYZ"
    ],
    "headline": "Finding tasks by name XYZ",
    "tool_name": "scheduler:find_task_by_name",
    "tool_args": {
        "name": "XYZ"
    }
}
~~~


#### scheduler:show_task
Show task details for scheduler task with the given uuid.

##### Arguments:
* uuid: string - The uuid of the task to display

##### Usage (execute task with uuid "xyz-123"):
~~~json
{
    "thoughts": [
        "I need details of task xxx-yyy-zzz",
    ],
    "headline": "Retrieving task details and configuration",
    "tool_name": "scheduler:show_task",
    "tool_args": {
        "uuid": "xxx-yyy-zzz",
    }
}
~~~


#### scheduler:run_task
Execute a task manually which is not in "running" state
This can be used to trigger tasks manually.
Normally you should only "run" tasks manually if they are in the "idle" state.
It is also advised to only run "adhoc" tasks manually but every task type can be triggered by this tool.
You can pass input data in text form as the "context" argument. The context will then be prepended to the task prompt when executed. This way you can pass for example result of one task as the input of another task or provide additional information specific to this one task run.

##### Arguments:
* uuid: string - The uuid of the task to run. Can be retrieved for example from "scheduler:tasks_list"
* context: (Optional) string - The context that will be prepended to the actual task prompt as contextual information.

##### Usage (execute task with uuid "xyz-123"):
~~~json
{
    "thoughts": [
        "I must run task xyz-123",
    ],
    "headline": "Manually executing scheduled task",
    "tool_name": "scheduler:run_task",
    "tool_args": {
        "uuid": "xyz-123",
        "context": "This text is useful to execute the task more precisely"
    }
}
~~~


#### scheduler:delete_task
Delete the task defined by the given uuid from the system.

##### Arguments:
* uuid: string - The uuid of the task to run. Can be retrieved for example from "scheduler:tasks_list"

##### Usage (execute task with uuid "xyz-123"):
~~~json
{
    "thoughts": [
        "I must delete task xyz-123",
    ],
    "headline": "Removing task from scheduler",
    "tool_name": "scheduler:delete_task",
    "tool_args": {
        "uuid": "xyz-123",
    }
}
~~~


#### scheduler:create_scheduled_task
Create a task within the scheduler system with the type "scheduled".
The scheduled type of tasks is being run by a cron schedule that you must provide.

##### Arguments:
* name: str - The name of the task, will also be displayed when listing tasks
* system_prompt: str - The system prompt to be used when executing the task
* prompt: str - The actual prompt with the task definition
* schedule: dict[str,str] - the dict of all cron schedule values. The keys are descriptive: minute, hour, day, month, weekday. The values are cron syntax fields named by the keys.
* attachments: list[str] - Here you can add message attachments, valid are filesystem paths and internet urls
* dedicated_context: bool - if false, then the task will run in the context it was created in. If true, the task will have it's own context. If unspecified then false is assumed. The tasks run in the context they were created in by default.

##### Usage:
~~~json
{
    "thoughts": [
        "I need to create a scheduled task that runs every 20 minutes in a separate chat"
    ],
    "headline": "Creating recurring cron-scheduled email task",
    "tool_name": "scheduler:create_scheduled_task",
    "tool_args": {
        "name": "XXX",
        "system_prompt": "You are a software developer",
        "prompt": "Send the user an email with a greeting using python and smtp. The user's address is: xxx@yyy.zzz",
        "attachments": [],
        "schedule": {
            "minute": "*/20",
            "hour": "*",
            "day": "*",
            "month": "*",
            "weekday": "*",
        },
        "dedicated_context": true
    }
}
~~~


#### scheduler:create_adhoc_task
Create a task within the scheduler system with the type "adhoc".
The adhoc type of tasks is being run manually by "scheduler:run_task" tool or by the user via ui.

##### Arguments:
* name: str - The name of the task, will also be displayed when listing tasks
* system_prompt: str - The system prompt to be used when executing the task
* prompt: str - The actual prompt with the task definition
* attachments: list[str] - Here you can add message attachments, valid are filesystem paths and internet urls
* dedicated_context: bool - if false, then the task will run in the context it was created in. If true, the task will have it's own context. If unspecified then false is assumed. The tasks run in the context they were created in by default.

##### Usage:
~~~json
{
    "thoughts": [
        "I need to create an adhoc task that can be run manually when needed"
    ],
    "headline": "Creating on-demand email task",
    "tool_name": "scheduler:create_adhoc_task",
    "tool_args": {
        "name": "XXX",
        "system_prompt": "You are a software developer",
        "prompt": "Send the user an email with a greeting using python and smtp. The user's address is: xxx@yyy.zzz",
        "attachments": [],
        "dedicated_context": false
    }
}
~~~


#### scheduler:create_planned_task
Create a task within the scheduler system with the type "planned".
The planned type of tasks is being run by a fixed plan, a list of datetimes that you must provide.

##### Arguments:
* name: str - The name of the task, will also be displayed when listing tasks
* system_prompt: str - The system prompt to be used when executing the task
* prompt: str - The actual prompt with the task definition
* plan: list(iso datetime string) - the list of all execution timestamps. The dates should be in the 24 hour (!) strftime iso format: "%Y-%m-%dT%H:%M:%S"
* attachments: list[str] - Here you can add message attachments, valid are filesystem paths and internet urls
* dedicated_context: bool - if false, then the task will run in the context it was created in. If true, the task will have it's own context. If unspecified then false is assumed. The tasks run in the context they were created in by default.

##### Usage:
~~~json
{
    "thoughts": [
        "I need to create a planned task to run tomorrow at 6:25 PM",
        "Today is 2025-04-29 according to system prompt"
    ],
    "headline": "Creating planned task for specific datetime",
    "tool_name": "scheduler:create_planned_task",
    "tool_args": {
        "name": "XXX",
        "system_prompt": "You are a software developer",
        "prompt": "Send the user an email with a greeting using python and smtp. The user's address is: xxx@yyy.zzz",
        "attachments": [],
        "plan": ["2025-04-29T18:25:00"],
        "dedicated_context": false
    }
}
~~~


#### scheduler:wait_for_task
Wait for the completion of a scheduler task identified by the uuid argument and return the result of last execution of the task.
Attention: You can only wait for tasks running in a different chat context (dedicated). Tasks with dedicated_context=False can not be waited for.

##### Arguments:
* uuid: string - The uuid of the task to wait for. Can be retrieved for example from "scheduler:tasks_list"

##### Usage (wait for task with uuid "xyz-123"):
~~~json
{
    "thoughts": [
        "I need the most current result of the task xyz-123",
    ],
    "headline": "Waiting for task completion and results",
    "tool_name": "scheduler:wait_for_task",
    "tool_args": {
        "uuid": "xyz-123",
    }
}
~~~
