### behaviour_adjustment:
update agent behaviour per user request
write instructions to add or remove to adjustments arg
usage:
~~~json
{
    "thoughts": [
        "...",
    ],
    "headline": "short headline of the response",
    "tool_name": "behaviour_adjustment",
    "tool_args": {
        "adjustments": "remove...",
    }
}
~~~
