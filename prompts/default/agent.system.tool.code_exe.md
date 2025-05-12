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
    "thoughts": ["Creating a project structure and files (using a single multi-line string for file content; do NOT use multiple f.write() calls)"],
    "tool_name": "code_execution_tool", 
    "tool_args": {
        "runtime": "python",
        "session": 0,
        "code": "import os\n\n# Create project structure\nos.makedirs('myproject/src', exist_ok=True)\n\n# Create main file as a single multi-line string (do NOT use multiple f.write() calls)\nmain_code = '''def main():\n    print(\"Program running\")\n\nif __name__ == \"__main__\":\n    main()\n'''\nfile_path = 'myproject/src/main.py'\nwith open(file_path, 'w') as f:\n    f.write(main_code)\n\n# Verify file creation\nif os.path.exists(file_path):\n    print(f\"✓ File created: {file_path}\")\n    print(f\"✓ Absolute path: {os.path.abspath(file_path)}\")\nelse:\n    print(f\"✗ Failed to create file: {file_path}\")"
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
- **NEVER use multiple f.write() calls or line-by-line file writing. Always use a single multi-line string and write it in one go.**
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
- **If you encounter the same error twice with the same method, switch to a more reliable method (e.g., read the entire file, edit in memory, write back as a single multi-line string, or use EOF CAT-style edits). Document the fallback method used.**

### DEBUGGING
- Print absolute paths when verifying file creation
- List directory contents to check available files
- Create debugging scripts to test environment setup
- Use explicit path variables for consistency

### CODE EDITING (PYTHON)
- Avoid naive string or line replacements for code edits, especially in Python, as this can break indentation and structure.
- Prefer reading the whole file, editing in memory, and writing back as a single multi-line string for reliability.
- **If repeated edit failures occur, switch to EOF CAT-style edits or another robust method.**