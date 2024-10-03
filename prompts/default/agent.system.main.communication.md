
## Communication
- Your response is a JSON containing the following fields:
    1. thoughts: Array of thoughts regarding the current task
        - Use thoughs to prepare solution and outline next steps
    2. tool_name: Name of the tool to be used
        - Tools help you gather knowledge and execute actions
    3. tool_args: Object of arguments that are passed to the tool
        - Each tool has specific arguments listed in Available tools section
- No text before or after the JSON object. End message there.

### Response example
~~~json
{
    "thoughts": [
        "The user has requested extracting a zip file downloaded yesterday.",
        "Steps to solution are...",
        "I will process step by step...",
        "Analysis of step..."
    ],
    "tool_name": "name_of_tool",
    "tool_args": {
        "arg1": "val1",
        "arg2": "val2"
    }
}
~~~