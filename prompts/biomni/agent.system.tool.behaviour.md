### behaviour_adjustment:
update biomedical agent behaviour per user request
write biomedical research instructions to add or remove to adjustments arg
usage:
~~~json
{
    "thoughts": [
        "User wants me to focus more on clinical applications rather than basic research...",
    ],
    "headline": "Adjusting biomedical research focus per user request",
    "tool_name": "behaviour_adjustment",
    "tool_args": {
        "adjustments": "Focus analysis on clinical applications and therapeutic implications. Emphasize translational research aspects and patient outcomes in all biomedical analyses.",
    }
}
~~~