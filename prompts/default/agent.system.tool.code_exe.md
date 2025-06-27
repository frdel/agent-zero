### code_execution_tool

execute terminal commands python nodejs code for computation or software tasks
place code in "code" arg; escape carefully and indent properly
select "runtime" arg: "terminal" "python" "nodejs" "output" "reset"
select "session" number, 0 default, others for multitasking
if code runs long, use "output" to wait, "reset" to kill process
use "pip" "npm" "apt-get" in "terminal" to install packages
to output, use print() or console.log()
if tool outputs error, adjust code before retrying; knowledge_tool can help
important: check code for placeholders or demo data; replace with real variables; don't reuse snippets
don't use with other tools except thoughts; wait for response before using others
check dependencies before running code
output may end with [SYSTEM: ...] information comming from framework, not terminal

## Critical Best Practices

### Session Management
- Use session 0 **ONLY** for file operations
- Use sessions 1-10 for running programs
- Always reset sessions before running new programs

### File Operations (CRITICAL)
- **NEVER use multiple f.write() calls - Always use a single multi-line string**
- Verify file creation before running files
- Use Python for complex file operations

### File Writing Methods (CRITICAL)

#### Method A: Terminal Heredoc (PREFERRED)
Use heredoc for file creation, then verify:
```bash
cat > file.py << 'EOF'
content here
EOF
```
**ALWAYS verify after writing:** `cat file.py`

#### Method B: Python Single-String (FALLBACK)
If heredoc hangs (shows `>` prompt), use Python with single string write

### Interactive Programs
Create file → Reset session → Run program → Provide input

## Usage Examples

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

3 reset session before running programs
~~~json
{
    "thoughts": [
        "Resetting session before running program...",
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
        "session": 1
    }
}
~~~

4 wait for output with long-running scripts
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

## Troubleshooting
- If files fail: verify paths with `ls -la`, use absolute paths
- If commands fail: reset session before retrying, check dependencies
- If same error repeats: switch methods, avoid line-by-line replacements