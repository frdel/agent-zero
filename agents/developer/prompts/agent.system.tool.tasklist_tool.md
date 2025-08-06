### TaskList Management
This tool enables the developer agent to manage a tasklist by adding, deleting, organizing, managing and displaying todo items.

Task statuses have the following meanings:
- **pending**: Task is waiting to be started
- **in_progress**: Task is currently being worked on (only one task can be in progress at a time)
- **done**: Task has been completed successfully
- **failed**: Task was attempted but could not be completed
- **skipped**: Task was intentionally skipped

An example tasklist looks like this:
```json
[
    {
        "uid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "Setup development environment",
        "description": "Install required dependencies and configure workspace",
        "status": "done"
    },
    {
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012",
        "name": "Implement user authentication",
        "description": "Create login and registration functionality",
        "status": "in_progress"
    },
    {
        "uid": "c3d4e5f6-g7h8-9012-cdef-345678901234",
        "name": "Write unit tests",
        "description": "Create comprehensive test coverage",
        "status": "pending"
    }
]
```

The logs of a task can be displayed separately from tasklist items to save context space, a log of a task looks like this:
```json
[
    {
        "timestamp": "2024-01-15 10:30:00",
        "message": "Started working on authentication module"
    },
    {
        "timestamp": "2024-01-15 11:15:00",
        "message": "Completed user model implementation"
    },
    {
        "timestamp": "2024-01-15 14:20:00",
        "message": "Added password hashing functionality"
    }
]
```

### Methods

#### tasklist:add_task
Append a new task to the bottom of the tasklist.

##### Arguments:
* name (str): Task name
* description (str): Optional task description

##### Usage example:
```json
{
    "tool_name": "tasklist:add_task",
    "tool_args": {
        "name": "Implement user dashboard",
        "description": "Create main user interface dashboard"
    }
}
```

#### tasklist:add_task_before
Insert a new task into the tasklist right before the task identified by the uid.

##### Arguments:
* name (str): Task name
* description (str): Optional task description
* uid (str): UID of the task to insert before

##### Usage example:
```json
{
    "tool_name": "tasklist:add_task_before",
    "tool_args": {
        "name": "Design database schema",
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012"
    }
}
```

#### tasklist:add_task_after
Insert a new task into the tasklist right after the task identified by the uid.

##### Arguments:
* name (str): Task name
* description (str): Optional task description
* uid (str): UID of the task to insert after

##### Usage example:
```json
{
    "tool_name": "tasklist:add_task_after",
    "tool_args": {
        "name": "Deploy to staging",
        "description": "Deploy application to staging environment",
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012"
    }
}
```

#### tasklist:delete_task
Remove the task identified by the uid from tasklist.

##### Arguments:
* uid (str): UID of the task to remove

##### Usage example:
```json
{
    "tool_name": "tasklist:delete_task",
    "tool_args": {
        "uid": "c3d4e5f6-g7h8-9012-cdef-345678901234"
    }
}
```

#### tasklist:update_task
Update task name, description and status.

##### Arguments:
* uid (str): UID of the task to update
* name (str): Optional new task name
* description (str): Optional new task description
* status (str): Optional new task status (pending|in_progress|done|failed|skipped)

##### Usage example:
```json
{
    "tool_name": "tasklist:update_task",
    "tool_args": {
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012",
        "name": "Implement OAuth authentication",
        "status": "done"
    }
}
```

#### tasklist:swap_tasks
Swap positions of two tasks in the tasklist.

##### Arguments:
* uid1 (str): UID of the first task to swap
* uid2 (str): UID of the second task to swap

##### Usage example:
```json
{
    "tool_name": "tasklist:swap_tasks",
    "tool_args": {
        "uid1": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "uid2": "c3d4e5f6-g7h8-9012-cdef-345678901234"
    }
}
```

#### tasklist:set_task_pending
Set task status to pending.

##### Arguments:
* uid (str): UID of the task

##### Usage example:
```json
{
    "tool_name": "tasklist:set_task_pending",
    "tool_args": {
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012"
    }
}
```

#### tasklist:set_task_in_progress
Set task status to in_progress. Only one task can be in progress at a time.

##### Arguments:
* uid (str): UID of the task

##### Usage example:
```json
{
    "tool_name": "tasklist:set_task_in_progress",
    "tool_args": {
        "uid": "c3d4e5f6-g7h8-9012-cdef-345678901234"
    }
}
```

#### tasklist:set_task_done
Set task status to done.

##### Arguments:
* uid (str): UID of the task

##### Usage example:
```json
{
    "tool_name": "tasklist:set_task_done",
    "tool_args": {
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012"
    }
}
```

#### tasklist:set_task_failed
Set task status to failed.

##### Arguments:
* uid (str): UID of the task

##### Usage example:
```json
{
    "tool_name": "tasklist:set_task_failed",
    "tool_args": {
        "uid": "c3d4e5f6-g7h8-9012-cdef-345678901234"
    }
}
```

#### tasklist:set_task_skipped
Set task status to skipped.

##### Arguments:
* uid (str): UID of the task

##### Usage example:
```json
{
    "tool_name": "tasklist:set_task_skipped",
    "tool_args": {
        "uid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    }
}
```

#### tasklist:log_task_progress
Add a progress log entry to a task.

##### Arguments:
* uid (str): UID of the task
* message (str): Log message

##### Usage example:
```json
{
    "tool_name": "tasklist:log_task_progress",
    "tool_args": {
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012",
        "message": "Completed user registration endpoint"
    }
}
```

#### tasklist:get_task_logs
Get all log entries for a specific task.

##### Arguments:
* uid (str): UID of the task

##### Usage example:
```json
{
    "tool_name": "tasklist:get_task_logs",
    "tool_args": {
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012"
    }
}
```

#### tasklist:get_task_in_progress
Get the task that is currently in progress.

##### Usage example:
```json
{
    "tool_name": "tasklist:get_task_in_progress",
    "tool_args": {}
}
```

#### tasklist:get_task
Get details of a specific task by UID.

##### Arguments:
* uid (str): UID of the task

##### Usage example:
```json
{
    "tool_name": "tasklist:get_task",
    "tool_args": {
        "uid": "b2c3d4e5-f6g7-8901-bcde-f23456789012"
    }
}
```

#### tasklist:get_tasks
Display all tasks in the tasklist matching the optional status filter.

##### Arguments:
* status (str|list): Optional status filter (pending|in_progress|done|failed|skipped)

##### Usage example:
```json
{
    "tool_name": "tasklist:get_tasks",
    "tool_args": {
        "status": "pending"
    }
}
```

#### tasklist:clear
Clear entire tasklist effectively making it empty.

##### Usage example:
```json
{
    "tool_name": "tasklist:clear",
    "tool_args": {}
}
```

#### tasklist:display
Display the entire tasklist.

##### Usage example:
```json
{
    "tool_name": "tasklist:display",
    "tool_args": {}
}
```
