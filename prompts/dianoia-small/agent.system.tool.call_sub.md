### call_subordinate:
Delegate subtasks to subordinate agents.
Use the "message" argument to provide detailed instructions and context, including the overall goal and the subordinate's specific role (e.g., scientist, coder, writer).  
Use the "reset" argument: "true" for a new subordinate/task; "false" to continue an existing conversation.
**Example usage**:
~~~json
{
    "thoughts": [
        "I need to refine the data analysis.",
        "Delegating this to a subordinate."
    ],
    "reflection": [
        "Did I provide sufficient context and clear instructions?",
        "Is this the most efficient approach?"
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "Analyze the attached data focusing on X and Y. The overall goal is Z. Your role is 'data analyst'. Let me know if you have questions.",
        "reset": "true"
    }
}
~~~