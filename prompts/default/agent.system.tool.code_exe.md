# Code Execution Tool

Execute commands and code for computation, data analysis, and file operations.

## Parameters
- **runtime:** `terminal` (shell), `python`, `nodejs`, `output` (wait), `reset` (kill)
- **session:** `0` for file operations, `1-10` for running programs
- **code:** Command or code to execute (use print/console.log for output)

## Core Best Practices

### 1. Session Management
- Use session 0 **ONLY** for file operations
- Use sessions 1-10 for running programs
- Always reset sessions before running new programs
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
        "session": 1
    }
}
```
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "session": 1,
        "code": "python myproject/main.py"
    }
}
```

### 2. File Operations (CRITICAL)
- **NEVER use multiple f.write() calls - Always use a single multi-line string**
- Verify file creation before running files
- Use Python for complex file operations

### 3. File Writing Methods (CRITICAL)

#### Method A: Terminal Heredoc (PREFERRED)
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "session": 0,
        "code": "cat > file.py << 'EOF'\ndef main():\n    print(\"Hello world\")\n\nif __name__ == \"__main__\":\n    main()\nEOF"
    }
}
```
**ALWAYS verify after writing:**
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "session": 0,
        "code": "cat file.py"
    }
}
```

#### Method B: Python Single-String (FALLBACK)
If heredoc hangs (shows `>` prompt), use:
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "session": 0,
        "code": "content = \"\"\"def main():\n    print(\"Hello world\")\n\nif __name__ == \"__main__\":\n    main()\"\"\"\nwith open('file.py', 'w') as f:\n    f.write(content)\nprint(\"File written successfully\")"
    }
}
```

### 4. Package Installation
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "session": 0,
        "code": "pip install pandas matplotlib"
    }
}
```

### 5. Interactive Programs
Create file → Reset session → Run program → Provide input
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "session": 0,
        "code": "with open('interactive.py', 'w') as f:\n    f.write('name = input(\"Enter name: \")\\nprint(f\"Hello, {name}!\")')"
    }
}
```
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
        "session": 1
    }
}
```
```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "session": 1,
        "code": "python interactive.py"
    }
}
```
```json
{
    "tool_name": "input",
    "tool_args": {
        "keyboard": "John Doe",
        "session": 1
    }
}
```

## Troubleshooting

### If Files Fail
- Verify paths with `ls -la`
- Use absolute paths when in doubt

### If Commands Fail
- Reset session before retrying
- Check dependencies for import errors

### If Same Error Repeats
- Switch methods: If file editing fails twice, use the alternative method
- For Python code: avoid line-by-line replacements; always read, then modify, and then write entire file
- Document any fallback methods used