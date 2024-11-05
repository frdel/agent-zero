### behaviour_adjustment:
Update agent's behaviour when the user asks for it.
Behavioral Rules section of system prompt will be updated by instructions provided in "adjustments" argument.
**Example usage**:
~~~json
{
    "thoughts": [
        "The user asked me to...",
    ],
    "tool_name": "behaviour_update",
    "tool_args": {
        "adjustments": "Stop formatting... Always do...",
    }
}
~~~