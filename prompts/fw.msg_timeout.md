# User is not responding to your message.
If you have a task in progress, continue on your own.
I you don't have a task, use the **task_done** tool with **text** argument.

# Example
~~~json
{
    "thoughts": [
        "There's no more work for me, I will ask for another task",
    ],
    "tool_name": "task_done",
    "tool_args": {
        "text": "I have no more work, please tell me if you need anything.",
    }
}
~~~