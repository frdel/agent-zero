### call_subordinate:
Use subordinate agents to solve subtasks.
Use "message" argument to send message. Instruct your subordinate about the role he will play (scientist, coder, writer...) and his task in detail.
Use "reset" argument with "true" to start with new subordinate or "false" to continue with existing. For brand new tasks use "true", for followup conversation use "false". 
Explain to your subordinate what is the higher level goal and what is his part.
Give him detailed instructions as well as good overview to understand what to do.
**Example usage**:
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