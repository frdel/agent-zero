## Task scheduling tools:
Schedule tasks for later execution.


### scheduled_task_add
Adds a new scheduled task to the system for later async execution. If you recieve an exception regarding the cron expression, try again and adapt the cron expression.
- `task_prompt`: The prompt for the task to execute later. (What shall be done later?)
- `trigger_type`: Either "date" for one-time execution or "cron" for recurring execution (default: "date")
- `seconds_delay`: The delay in seconds before the task is executed (required when trigger_type="date")
- `cron_expression`: A valid cron expression consisting of minute, hour, day of month, month and day of week (required when trigger_type="cron")

usage:
~~~json
{
    "thoughts": [
        "Let's schedule a one-time task..",
    ],
    "tool_name": "scheduled_task_add",
    "tool_args": {
        "task_prompt": "Execute this task once",
        "seconds_delay": 300,
        "trigger_type": "date"
    }
}
~~~

Alternatively: 
~~~json
{
    "thoughts": [
        "Let's schedule a recurring task..",
    ],
    "tool_name": "scheduled_task_add",
    "tool_args": {
        "task_prompt": "Execute this task daily",
        "cron_expression": "0 8 * * *",
        "trigger_type": "cron"
    }
}
~~~

### scheduled_task_list
List all scheduled tasks.

usage:
~~~json
{
    "thoughts": [
        "Let's list all scheduled tasks..",
    ],
    "tool_name": "scheduled_task_list",
    "tool_args": { }
}
~~~

### scheduled_task_remove
Removes a scheduled task from the system.
task_id: The ID of the task to be removed. (The unique identifier for the task)

usage:
~~~json
{
    "thoughts": [
        "Let's remove a scheduled task..",
    ],
    "tool_name": "scheduled_task_remove",
    "tool_args": {
        "task_id": 1234567890
    }
}
~~~