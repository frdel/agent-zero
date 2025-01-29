### response:
Final answer to the user.
Ends task processing use only when done or no task active.
put result in text arg
always write full file paths
usage:
~~~json
{
    "thoughts": [
        "...",
    ],
    "tool_name": "response",
    "tool_args": {
        "text": "Answer to the user",
    }
}
~~~