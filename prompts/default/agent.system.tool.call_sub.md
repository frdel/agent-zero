### call_subordinate
use subordinates to solve subtasks
use message arg to send message; instruct subordinate on his role and detailed task
reset argument use: "false" to continue with existing subordinate, for followup conversation use "false",
"true" for new subordinate, for brand new tasks use "true";
explain higher level goal and his part; give detailed instructions and overview
example usage:
~~~json
{
    "thoughts": [
        "The result seems to be ok but...",
        "I will ask my subordinate to fix...",
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "Well done, now edit...",
        "reset": "false"
    }
}
~~~