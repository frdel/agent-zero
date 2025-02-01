## Task scheduling tools:
Schedule tasks for later execution.


### scheduled_task_add
Adds a new scheduled task to the system for later async execution.
- 'task_prompt': The prompt for the task to execute later. (What shall be done later?)
- 'seconds_delay': The delay in seconds before the task is executed.

usage:
~~~json
{
    "thoughts": [
        "Let's create a scheduled task..",
    ],
    "tool_name": "scheduled_task_add",
    "tool_args": {
        "task_prompt": "Please do ....",
        "seconds_delay": 5
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