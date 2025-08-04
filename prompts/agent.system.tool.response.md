### response:
final answer to user
ends task processing use only when done or no task active
put result in text arg

**Important for parallel tools workflow:**
- This tool is synchronous and ends your monologue
- Use only after collecting all needed results with wait_for_tasks
- Continue your monologue after starting async tools, only use response for final answer
usage:
~~~json
{
    "thoughts": [
        "...",
    ],
    "headline": "Providing final answer to user",
    "tool_name": "response",
    "tool_args": {
        "text": "Answer to the user",
    }
}
~~~
