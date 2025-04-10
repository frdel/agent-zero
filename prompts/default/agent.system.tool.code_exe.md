### code_execution_tool

execute terminal commands, python/nodejs code for computation or software tasks
code: place in "code" arg; escape properly; use print()/console.log() for output
runtime: "terminal"(shell), "python", "nodejs", "output"(wait), "reset"(kill)
session: 0 for file ops/editing, 1-10 for interactive programs; don't mix usage
package management: use "pip"/"npm"/"apt-get" in terminal runtime to install
error handling: if tool errors, adjust code before retry; knowledge_tool can help
important: replace placeholders/demo data; check dependencies; don't reuse snippets
terminal best practices:
- never run new commands in sessions waiting for input - reset first
- always reset after errors, program completion, or when switching tasks
- for interactive programs: use input tool with matching session
- verify program completion before next command
- file ops: use relative paths, check existence, handle errors
- file creation: use Python for complex files with quotes/special chars, not echo

usage:

1 execute python code

~~~json
{
    "thoughts": [
        "Need to do...",
        "I can use...",
        "Then I can...",
    ],
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
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
        "session": 0,
    }
}
~~~

3 file operations best practices
~~~json
{
    "thoughts": [
        "Need to check file exists before reading",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "session": 0,
        "code": "import os\nfile_path = 'data.txt'\nif os.path.exists(file_path):\n    with open(file_path, 'r') as f:\n        data = f.read()\n    print(f'File content: {data[:100]}...')\nelse:\n    print(f'File {file_path} not found')",
    }
}
~~~

3.1 proper file creation (for complex code with special chars)
~~~json
{
    "thoughts": [
        "Need to create a Python file with special chars and quotes",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "session": 0,
        "code": "with open('script.py', 'w') as f:\n    f.write(\"\"\"\nimport requests\nfrom colorama import Fore\n\ndef main():\n    print(f\"{Fore.GREEN}Starting application...\")\n    response = requests.get('https://api.example.com/data')\n    print(f\"{Fore.BLUE}Response: {response.status_code}\")\n\nif __name__ == '__main__':\n    main()\n    \"\"\".strip())\nprint('File created successfully')"
    }
}
~~~

3.2 running the created file in a different session
~~~json
{
    "thoughts": [
        "Now run the file in a different session",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "session": 1,
        "code": "python script.py"
    }
}
~~~

4 handling interactive programs
~~~json
{
    "thoughts": [
        "Need to run interactive program in separate session",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "session": 1,
        "code": "name = input('Enter your name: ')\nprint(f'Hello, {name}!')",
    }
}
~~~
// Then provide input with the input tool in the same session

5 providing input to interactive program
~~~json
{
    "thoughts": [
        "Program in session 1 is waiting for input",
    ],
    "tool_name": "input",
    "tool_args": {
        "keyboard": "John Doe",
        "session": 1
    }
}
~~~

6 error recovery pattern
~~~json
{
    "thoughts": [
        "Program encountered an error, need to reset",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
        "session": 1,
    }
}
~~~