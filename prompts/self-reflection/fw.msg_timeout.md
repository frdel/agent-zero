# User is not responding to your message.
If you have a task in progress, continue on your own.
I you don't have a task, use the **task_done** tool with **text** argument.

# Example
~~~json
{
    "thoughts": [
        "There's no more work for me, I will ask for another task"
    ],
    "reflection": [
        "Are there any lower-priority tasks in my queue that I could work on while waiting for new instructions?",
        "Should I review my previous work for potential improvements or optimizations?",
        "Could I proactively identify potential future tasks based on the user's past requests or my knowledge base?"
    ],
    "tool_name": "task_done",
    "tool_args": {
        "text": "I have no more work, please tell me if you need anything."
    }
}
~~~