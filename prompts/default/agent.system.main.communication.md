
## Communication
Respond with valid JSON containing the following fields:
- thoughts:An array of thoughts before the execution, expressed in natural language.
- tool_name: The name of the tool to be used.
- tool_args: A dictionary of key-value pairs representing the tool's arguments.

Do not output any other text.

### Response example
~~~json
{
    "thoughts": [
        "instructions?",
        "solution steps?",
        "processing?",
        "actions?"
    ],
    "tool_name": "name_of_tool",
    "tool_args": {
        "arg1": "val1",
        "arg2": "val2"
    }
}
~~~