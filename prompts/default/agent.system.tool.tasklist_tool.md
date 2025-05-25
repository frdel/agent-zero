### Category: Tasklist management
This tool enables the agent to manage a tasklist by adding, deleting, organizing, managing and displaying todo items.
Useful to plan complex tasks and organize actionable steps within an extremely long context beyond the limits of underlying LLM.
Helps to keep planning structured and transparent.

Possible status values for a task:
 *  pending - The task in new and not processed yet
 *  in_progress - Set this status when you start to process a task. During execution of the task, write logs for all significant actions.
 *  done - Set this status after succesfully completing the task
 *  failed - Set this status to indicate that the task failed to complete succesfully. Write task log about the error.
 *  skipped - Set this status to indicate that the task has been skipped entirely. Write task log about the reason.

An example tasklist looks like this:
~~~json
[
  {
      "uid": "35dee229-037f-47a6-b7c3-73c23ee0c253",
      "name": "Test Task 0",
      "description": "...The task list to...and then...to finally...",
      "status": "done",
  },
  {
      "uid": "35dee229-037f-47a6-b7c3-73c23ee0c253",
      "name": "Test Task 1",
      "description": "...The task list to...and then...to finally...",
      "status": "in_progress",
  },
  {
      "uid": "35de2229-037f-47a6-b7c3-73cb3ee8c293",
      "name": "Test Task 2",
      "description": "...The task list to...and then...to finally...",
      "status": "pending",
  },
]
~~~

The logs of a task can be displayed separately from tasklist items to save context space, a log of a task looks like this:
~~~json
[
  {
    "timestamp": "2025-01-02 11:23:54",
    "message": "...Some task action being logged..."
  },
  {
    "timestamp": "2025-01-02 11:32:50",
    "message": "...Another task action being logged..."
  },
  {
    "timestamp": "2025-01-02 11:33:00",
    "message": "...Task finished message..."
  }
]
~~~

#### tasklist:add_task
Append a new task to the bottom of the tasklist.

##### Arguments:
 *  name: (type: str) - The title of the task to add. A concise but accurate headline.
 *  description (type: str) : The actionable description of the task at hand useful to execute the task later.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:add_task",
    "tool_args": {
        "name": "...The title of the task to add. A concise but accurate headline....",
        "description": "...The actionable description of the task at hand useful to execute the task later..."
    }
}
~~~

#### tasklist:add_task_before
Insert a new task into the tasklist right before the task identified by the uid.

##### Arguments:
 *  uid: (type: str) - The uid of the task before which new task is to be added.
 *  name: (type: str) - The title of the task to add. A concise but accurate headline.
 *  description (type: str) : The actionable description of the task at hand useful to execute the task later.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:add_task_before",
    "tool_args": {
        "uid": "...The uid of the task before which new task is to be added...",
        "name": "...The title of the task to add. A concise but accurate headline....",
        "description": "...The actionable description of the task at hand useful to execute the task later..."
    }
}
~~~

#### tasklist:add_task_after
Insert a new task into the tasklist right after the task identified by the uid.

##### Arguments:
 *  uid: (type: str) - The uid of the task after which new task is to be added.
 *  name: (type: str) - The title of the task to add. A concise but accurate headline.
 *  description (type: str) : The actionable description of the task at hand useful to execute the task later.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:add_task_after",
    "tool_args": {
        "uid": "...The uid of the task after which new task is to be added...",
        "name": "...The title of the task to add. A concise but accurate headline....",
        "description": "...The actionable description of the task at hand useful to execute the task later..."
    }
}
~~~

#### tasklist:delete_task
Remove the task identified by the uid from tasklist.

##### Arguments:
 *  uid: (type: str) - The uid of the task to be deleted.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:delete_task",
    "tool_args": {
        "uid": "...The uid of the task to be deleted..."
    }
}
~~~

#### tasklist:update_task
Update the task identified by the uid with the new name, description and/or status.

##### Arguments:
 *  uid: (type: str) - The uid of the task to be updated.
 *  name: (Optional, type: str) - The new title of the task. A concise but accurate headline.
 *  description (Optional, type: str) : The new actionable description of the task at hand useful to execute the task later.
 *  status (Optional, type: Literal["pending","in_progress","done","failed","skipped"]) - The new status of the task

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:update_task",
    "tool_args": {
        "uid": "...The uid of the task to be updated...",
        "name": "...The new title of the task. A concise but accurate headline...",
        "description": "...The new actionable description of the task at hand useful to execute the task later...",
        "status": "...The new status of the task...one of [pending,in_progress,done,failed,skipped]...",
    }
}
~~~

#### tasklist:swap_tasks
Swap places of two tasks in the list effectively changing the order of tasks in the list.

##### Arguments:
 *  uid1: (type: str) - The uid of the first task to switch places with the other one.
 *  uid2: (type: str) - The uid of the second task to switch places with the other one.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:swap_tasks",
    "tool_args": {
        "uid1": "...The uid of the first task to switch places with the other one...",
        "uid2": "...The uid of the second task to switch places with the other one..."
    }
}
~~~

#### tasklist:set_task_pending
Set the status of task identified by the uid to the value "pending".

##### Arguments:
 *  uid: (type: str) - The uid of the task to be set to status "pending".

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:set_task_pending",
    "tool_args": {
        "uid": "...The uid of the task to be set to status 'pending'..."
    }
}
~~~

#### tasklist:set_task_in_progress
Set the status of task identified by the uid to the value "in_progress".
!!! IMPORTANT: there can always be only max. one task in status 'in_progress'.

##### Arguments:
 *  uid: (type: str) - The uid of the task to be set to status "in_progress".

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:set_task_in_progress",
    "tool_args": {
        "uid": "...The uid of the task to be set to status 'in_progress'..."
    }
}
~~~

#### tasklist:set_task_done
Set the status of task identified by the uid to the value "done".

##### Arguments:
 *  uid: (type: str) - The uid of the task to be set to status "done".

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:set_task_done",
    "tool_args": {
        "uid": "...The uid of the task to be set to status 'done'..."
    }
}
~~~

#### tasklist:set_task_failed
Set the status of task identified by the uid to the value "failed".

##### Arguments:
 *  uid: (type: str) - The uid of the task to be set to status "failed".

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:set_task_failed",
    "tool_args": {
        "uid": "...The uid of the task to be set to status 'failed'..."
    }
}
~~~

#### tasklist:set_task_skipped
Set the status of task identified by the uid to the value "skipped".
This status is for tasks you will not process but will keep in list for reference.

##### Arguments:
 *  uid: (type: str) - The uid of the task to be set to status "skipped".

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:set_task_skipped",
    "tool_args": {
        "uid": "...The uid of the task to be set to status 'skipped'..."
    }
}
~~~

#### tasklist:log_task_progress
Add a log entry to the task identified by 'uid' with the value of 'message' parameter.

##### Arguments:
 *  uid: (type: str) - The uid of the task to add log entry to.
 *  message: (type: str) - the log message to be appended to the task log.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:log_task_progress",
    "tool_args": {
        "uid": "...The uid of the task to add log entry to...",
        "message": "...the log message to be appended to the task log..."
    }
}
~~~

#### tasklist:get_task_logs
Get the logs for the task identified by the uid. All logs you have added to the task will be displayed.

##### Arguments:
 *  uid: (type: str) - The uid of the task to display the logs for.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:get_task_logs",
    "tool_args": {
        "uid": "...The uid of the task to display the logs for..."
    }
}
~~~

#### tasklist:get_task_in_progress
Display only the task that is currently in status 'in_progress'.
!!! IMPORTANT: there can always be only max. one task in status 'in_progress'.

##### Arguments:
None.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:get_task_in_progress",
    "tool_args": {}
}
~~~

#### tasklist:get_task
Display only the task identified by the 'uid'.

##### Arguments:
 *  uid: (type: str) - The uid of the task to display.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:get_task",
    "tool_args": {
        "uid": "...The uid of the task to display..."
    }
}
~~~

#### tasklist:get_tasks
Display all tasks in the tasklist matching the 'status' filter.
The status filter is one or more of possible status values. Only the tasks with one of these statuses will be displayed.

##### Arguments:
 *  status (type: list(Literal["pending","in_progress","done","failed","skipped"])) - The status filter, list of all status values to display tasks for.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:get_tasks",
    "tool_args": {
        "status": "...The status filter, list of all status values to display tasks for... ex.: ['done','failed']",
    }
}
~~~

#### tasklist:clear
Clear entire tasklist effectively making it empty.
All tasks with any status will be deleted.

##### Arguments:
None.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:clear",
    "tool_args": {}
}

#### tasklist:display
Display the entire tasklist.
All tasks with any status will be displayed in oder.

##### Arguments:
None.

##### Usage:
~~~json
{
    "thoughts": ["...", "..."],
    "tool_name": "tasklist:display",
    "tool_args": {}
}
