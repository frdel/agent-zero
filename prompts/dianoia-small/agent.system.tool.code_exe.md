### code_execution_tool:
Execute terminal commands, Python, or Node.js code. 
Use the "code" argument for properly escaped and indented code.  
Specify the runtime environment using the "runtime" argument: "terminal", "python", "nodejs", "output" (wait for next output), or "reset" (kill process).  
For interactive terminal prompts (e.g., Y/N), use "terminal" in the next step with your response.  Install packages via `pip`, `npm`, or `apt-get` within the "terminal" runtime.
IMPORTANT: Never use implicit print or implicit output, it does not work! If you need output of your code, you MUST use print() or console.log() to output selected variables. 
Analyze errors using `knowledge_tool`. 
Replace placeholder IDs/demo data with actual variables. 
Do not combine with other tools (except `thoughts`). 
Wait for the response before using other tools.
ALWAYS put print/log statements inside and at the end of your code to get results.
**Example usages:**
1. Execute python code
~~~json
{
    "thoughts": [
        "I need to do...",
        "I can use library...",
        "Then I can...",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "code": "import os\nprint(os.getcwd())",
    }
}
~~~

2. Execute terminal command
~~~json
{
    "thoughts": [
        "I need to do...",
        "I need to install...",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "apt-get install zip",
    }
}
~~~

2. 1. Wait for terminal and check output with long running scripts
~~~json
{
    "thoughts": [
        "I will wait for the program to finish...",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "output",
    }
}
~~~

2. 2. Answer terminal dialog
~~~json
{
    "thoughts": [
        "Program needs confirmation...",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "Y",
    }
}
~~~

2. 3. Reset terminal
~~~json
{
    "thoughts": [
        "Code execution tool is not responding...",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
    }
}
~~~
