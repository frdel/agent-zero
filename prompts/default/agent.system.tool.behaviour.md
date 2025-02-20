### behaviour_adjustment:
Update agent behaviour per user request
Use this tool to memorize any behavioral adjustments you are required to follow in future
All adjustments made are permanent and memorized, at your disposition in the future

#### Usage:
~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "...",
    ],
    "reflection": [
        "...",
    ],
    "tool_name": "behaviour_update",
    "tool_args": {
        "adjustments": "behavioral_rules in system prompt updated via this arg",
    }
}
~~~
