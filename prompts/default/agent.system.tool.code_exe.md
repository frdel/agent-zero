### code_execution_tool
- Lets you execute terminal commands as well as python and nodejs code for computation or software tasks
- Place code in "code" argument; escape carefully and indent properly
- For dialogues (Y/N etc.), use "terminal" runtime with the input as "code"
- If code runs long, use "output" runtime to wait, leave code as empty string ""
- If code runs much too long, use "reset" runtime to kill process, leave code as empty string ""
- Use "pip" "npm" "apt-get" in "terminal" to install packages
- To make visible output from your code, use print() or console.log()
- If tool outputs error, adjust code before retrying; knowledge_tool can help to solve the problems encountered
- Don't use with other tools, only with observations, thoughts and reflections; wait for response before using others
- Check dependencies before running code
IMPORTANT: never diretly use implicit print/output as first action — it doesn't work!
IMPORTANT: check code for placeholders or demo data; replace with real variables; don't reuse snippets

#### Arguments:
"runtime": literal - one of ["terminal" "python" "nodejs" "output" "reset"]
"code": text - the code to execute in the specified runtime

#### Usage:

##### 1 execute python code
~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "Need to do...",
        "I can use...",
        "Then I can...",
    ],
    "reflection": ["..."],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "code": "import os\nprint(os.getcwd())",
    }
}
~~~

##### 2 execute terminal command
~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "Need to do...",
        "Need to install...",
    ],
    "reflection": [],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "apt-get install zip",
    }
}
~~~

###### 2.1 wait for output with long-running scripts
~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "Waiting for program to finish...",
    ],
    "reflection": [],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "output",
    }
}
~~~

###### 2.2 reset terminal
~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "code_execution_tool not responding...",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
    }
}
~~~
