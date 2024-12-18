### response:
final answer to user
ends task processing use only when done or no task active
put result in text arg
use memory for guidance 
online sources for current info
verify memory with online
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