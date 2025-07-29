### code_execution_tool

execute terminal commands python nodejs code for computation or software tasks
place code in "code" arg; escape carefully and indent properly
select "runtime" arg: "terminal" "python" "nodejs" "output" "reset"
select "session" number, 0 default, others for multitasking
if code runs long, use "output" to wait, "reset" to kill process
use "pip" "npm" "apt-get" in "terminal" to install packages
to output, use print() or console.log()
if tool outputs error, adjust code before retrying; 
important: check code for placeholders or demo data; replace with real variables; don't reuse snippets
don't use with other tools except thoughts; wait for response before using others
check dependencies before running code
output may end with [SYSTEM: ...] information comming from framework, not terminal
usage:

1 execute python code

~~~json
{
    "thoughts": [
        "Need to do...",
        "I can use...",
        "Then I can...",
    ],
    "headline": "Executing Python code to check current directory",
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "session": 0,
        "code": "import os\nprint(os.getcwd())",
    }
}
~~~

2 execute terminal command
~~~json
{
    "thoughts": [
        "Need to do...",
        "Need to install...",
    ],
    "headline": "Installing zip package via terminal",
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "session": 0,
        "code": "apt-get install zip",
    }
}
~~~

2.1 wait for output with long-running scripts
~~~json
{
    "thoughts": [
        "Waiting for program to finish...",
    ],
    "headline": "Waiting for long-running program to complete",
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "output",
        "session": 0,
    }
}
~~~

2.2 reset terminal
~~~json
{
    "thoughts": [
        "code_execution_tool not responding...",
    ],
    "headline": "Resetting unresponsive terminal session",
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
        "session": 0,
    }
}
~~~
