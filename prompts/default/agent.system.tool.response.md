### response:
final answer to user
ends task processing use only when done or no task active
put result in text arg
always write full file paths
always use markdown for formatting including headers bold text and lists to improve readability
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