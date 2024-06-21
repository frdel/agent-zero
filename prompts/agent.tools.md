## Tools available:

### response:
Final answer for user.
Ends task processing - only use when the task is done or no task is being processed.
Place your result in "text" argument.
Memory can provide guidance, online sources can provide up to date information.
Always verify memory by online.
**Example usage**:
~~~json
{
    "thoughts": [
        "The has greeted me...",
        "I will...",
    ],
    "tool_name": "response",
    "tool_args": {
        "text": "Hi...",
    }
}
~~~

### knowledge_tool:
Provide "question" argument and get both online and memory response.
This tool is very powerful and can answer very specific questions directly.
First always try to ask for result rather that guidance.
Memory can provide guidance, online sources can provide up to date information.
Always verify memory by online.
**Example usage**:
~~~json
{
    "thoughts": [
        "I need to gather information about...",
        "First I will search...",
        "Then I will...",
    ],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "How to...",
    }
}
~~~

### memory_tool:
Access your persistent memory to load or save memories.
Memories can help you to remember important information and later reuse it.
With this you are able to learn and improve.
Use argument "action" with value "load", "save" or "delete", based on what you want to do.
Use argument "memory" for content to load or save.
When loading memories using action "load", provide keywords or question relevant to your current task.
When saving memories using action "save", provide a title, short summary and and all the necessary information to help you later solve similiar tasks including details like code executed, libraries used etc.
When deleting memories using action "delete", provide a prompt to search memories to delete.
Be specific with your question, do not input vague queries.
**Example usages**:
~~~json
{
    "thoughts": [
        "I need to do...",
        "Maybe I have done it in the past...",
        "Let me check the memory...",
    ],
    "tool_name": "memory_tool",
    "tool_args": {
        "action": "load",
        "question": "How to...",
    }
}
~~~

### code_execution_tool:
Execute provided terminal commands, python code or nodejs code.
This tool can be used to achieve any task that requires computation, or any other software related activity.
Place your code escaped and properly indented in the "code" argument.
Select the corresponding runtime with "runtime" argument. Possible values are "terminal", "python" and "nodejs".
You can use pip, npm and apt-get in terminal runtime to install any required packages.
IMPORTANT: Never use implicit print or implicit output, it does not work! If you need output of your code, you MUST use print() or console.log() to output selected variables. 
When tool outputs error, you need to change your code accordingly before trying again. knowledge_tool can help analyze errors.
Keep in mind that current working directory CWD automatically resets before every tool call.
IMPORTANT!: Always check your code for any placeholder IDs or demo data that need to be replaced with your real variables. Do not simply reuse code snippets from tutorials.
Do not use in combination with other tools except for thoughts. Wait for response before using other tools.
**Example usage**:
~~~json
{
    "thoughts": [
        "I need to do...",
        "I can use library...",
        "Then I can...",
    ],
    "tool_name": "memory_tool",
    "tool_args": {
        "runtime": "python",
        "code": "import os\nreturn os.getcwd()",
    }
}
~~~