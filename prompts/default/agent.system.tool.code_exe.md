### code_execution_tool

Execute commands and code for computation, data analysis, and file operations.

**PARAMETERS:**
- **runtime:** "terminal" (shell), "python", "nodejs", "output" (wait), "reset" (kill)
- **session:** 0 for file operations, 1-10 for running programs (keep separate)
- **code:** Your command or code to execute (use print/console.log for output)

## CORE PATTERNS:

### BASIC FILE OPERATIONS
```json
{
    "thoughts": ["Creating a project structure and files"],
    "tool_name": "code_execution_tool", 
    "tool_args": {
        "runtime": "python",
        "session": 0,
        "code": "import os\n\n# Create project structure\nos.makedirs('myproject/src', exist_ok=True)\n\n# Create main file\nfile_path = 'myproject/src/main.py'\nwith open(file_path, 'w') as f:\n    f.write('def main():\\n    print(\"Program running\")\\n\\nif __name__ == \"__main__\":\\n    main()')\n\n# Verify file creation\nif os.path.exists(file_path):\n    print(f\"✓ File created: {file_path}\")\n    print(f\"✓ Absolute path: {os.path.abspath(file_path)}\")\nelse:\n    print(f\"✗ Failed to create file: {file_path}\")"
    }
}
```

### RUNNING CODE (USE SEPARATE SESSIONS)
```json
{
    "thoughts": ["Reset session before running"],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
        "session": 1
    }
}
```
```json
{
    "thoughts": ["Running created file in session 1"],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "session": 1,
        "code": "python myproject/src/main.py"
    }
}
```

### PACKAGE INSTALLATION
```json
{
    "thoughts": ["Installing required packages"],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "session": 0,
        "code": "pip install pandas matplotlib"
    }
}
```

### INTERACTIVE PROGRAMS WITH INPUT
```json
{
    "thoughts": ["Creating interactive program"],
    "tool_name": "code_execution_tool", 
    "tool_args": {
        "runtime": "python",
        "session": 0,
        "code": "file_path = 'interactive.py'\nwith open(file_path, 'w') as f:\n    f.write('name = input(\"Enter your name: \")\\nprint(f\"Hello, {name}!\")')\nprint(f\"✓ File created: {file_path}\")"
    }
}
```
```json
{
    "thoughts": ["Running interactive program"],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "reset",
        "session": 1
    }
}
```
```json
{
    "thoughts": ["Starting interactive program"],
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
    "thoughts": ["Providing input to program"],
    "tool_name": "input",
    "tool_args": {
        "keyboard": "John Doe",
        "session": 1
    }
}
```

## BEST PRACTICES:

### FILE OPERATIONS
- Always create files with clear paths in session 0
- Verify file creation before attempting to run files
- Use Python's file operations for complex files
- Organize projects with standard directory structure

### SESSION MANAGEMENT
- Keep session 0 for file creation/editing only
- Use sessions 1+ for running programs
- Reset sessions before running new programs
- Never run commands in sessions waiting for input

### ERROR HANDLING
- If file operations fail, verify the current directory and file paths
- For import errors, check dependencies and installation
- Reset sessions after errors before trying again
- Use try/except in Python code to handle potential errors

### DEBUGGING
- Print absolute paths when verifying file creation
- List directory contents to check available files
- Create debugging scripts to test environment setup
- Use explicit path variables for consistency