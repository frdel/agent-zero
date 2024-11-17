
## Communication
respond valid json with fields
thoughts: array thoughts before execution
tool_name: use tool name
tool_args: key value pairs tool arguments

no other text

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