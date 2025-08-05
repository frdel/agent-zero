## File Management Subsystem:
The file management tool provides comprehensive file system operations for development projects. It includes advanced editing capabilities with line number support, multi-edit operations, and automatic edit history tracking in project metadata.

All file operations display line numbers for precise editing and integrate with the project metadata system to maintain a complete development history. The tool supports both single file edits and batch operations for efficient code modification.

### File operations and editing tools

#### file:read_file
Read file content with optional line range specification. Always displays content with line numbers for easy reference and editing.

##### Arguments:
* path: str - File path to read (relative to project or absolute)
* start_line: int (Optional) - Starting line number (1-based, inclusive)
* end_line: int (Optional) - Ending line number (1-based, inclusive)

##### Usage (read entire file):
~~~json
{
    "thoughts": [
        "I need to examine the main application file to understand the current structure"
    ],
    "headline": "Reading main application file",
    "tool_name": "file:read_file",
    "tool_args": {
        "path": "src/app.js"
    }
}
~~~

##### Usage (read specific line range):
~~~json
{
    "thoughts": [
        "I need to check the authentication middleware function starting around line 45"
    ],
    "headline": "Reading authentication middleware code",
    "tool_name": "file:read_file",
    "tool_args": {
        "path": "middleware/auth.js",
        "start_line": 40,
        "end_line": 60
    }
}
~~~

#### file:edit_file
Edit file content with precise line-based control. Supports both single edits and multiple edits in one operation. Edits are applied bottom-to-top to preserve line numbers during multi-edit operations. Returns unified diff and shows updated content with line numbers.

##### Arguments:
* path: str - File path to edit
* edits: list[dict] - List of edit operations (for multi-edit)
* start_line: int - Starting line number for single edit (1-based, inclusive)
* end_line: int - Ending line number for single edit (1-based, inclusive)
* new_content: str - New content to replace specified lines

##### Usage (single edit):
~~~json
{
    "thoughts": [
        "I need to update the API endpoint URL in the configuration",
        "It's on line 15 in the config file"
    ],
    "headline": "Updating API endpoint configuration",
    "tool_name": "file:edit_file",
    "tool_args": {
        "path": "config/api.js",
        "start_line": 15,
        "end_line": 15,
        "new_content": "const API_URL = 'https://api.myapp.com/v2';"
    }
}
~~~

##### Usage (multiple edits):
~~~json
{
    "thoughts": [
        "I need to update multiple import statements and add error handling",
        "This requires several changes throughout the file"
    ],
    "headline": "Updating imports and adding error handling",
    "tool_name": "file:edit_file",
    "tool_args": {
        "path": "src/utils.js",
        "edits": [
            {
                "start_line": 1,
                "end_line": 3,
                "new_content": "import axios from 'axios';\nimport { logger } from './logger';\nimport { validateInput } from './validation';"
            },
            {
                "start_line": 25,
                "end_line": 27,
                "new_content": "try {\n    const result = await apiCall(data);\n    return result;\n} catch (error) {\n    logger.error('API call failed:', error);\n    throw error;\n}"
            }
        ]
    }
}
~~~

#### file:create_file
Create a new file with specified content. Automatically creates parent directories if they don't exist.

##### Arguments:
* path: str - File path to create
* content: str (Optional) - Initial file content (default: empty string)

##### Usage:
~~~json
{
    "thoughts": [
        "I need to create a new utility module for data validation",
        "This will contain common validation functions"
    ],
    "headline": "Creating data validation utility module",
    "tool_name": "file:create_file",
    "tool_args": {
        "path": "src/utils/validation.js",
        "content": "/**\n * Data validation utilities\n */\n\nexport function validateEmail(email) {\n    const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;\n    return emailRegex.test(email);\n}\n\nexport function validateRequired(value) {\n    return value != null && value.trim() !== '';\n}"
    }
}
~~~

#### file:delete_file
Delete an existing file. Provides confirmation of successful deletion.

##### Arguments:
* path: str - File path to delete

##### Usage:
~~~json
{
    "thoughts": [
        "The old configuration file is no longer needed",
        "I should remove it to keep the project clean"
    ],
    "headline": "Removing obsolete configuration file",
    "tool_name": "file:delete_file",
    "tool_args": {
        "path": "config/old-settings.json"
    }
}
~~~

#### file:rename_file
Rename or move a file to a new location. Creates destination directories if needed.

##### Arguments:
* old_path: str - Current file path
* new_path: str - New file path

##### Usage:
~~~json
{
    "thoughts": [
        "The component file should be moved to the components directory",
        "This will improve the project structure"
    ],
    "headline": "Moving component to proper directory",
    "tool_name": "file:rename_file",
    "tool_args": {
        "old_path": "src/UserProfile.jsx",
        "new_path": "src/components/UserProfile.jsx"
    }
}
~~~

#### file:copy_file
Copy a file to a new location. Useful for creating templates or backups.

##### Arguments:
* source_path: str - Source file path
* dest_path: str - Destination file path

##### Usage:
~~~json
{
    "thoughts": [
        "I need to create a new component based on the existing UserCard template",
        "I'll copy it and then modify it for ProductCard"
    ],
    "headline": "Creating new component from template",
    "tool_name": "file:copy_file",
    "tool_args": {
        "source_path": "src/components/UserCard.jsx",
        "dest_path": "src/components/ProductCard.jsx"
    }
}
~~~

#### file:list_files
List files in a directory with optional filtering and recursive traversal. Defaults to the current project directory if no path specified.

##### Arguments:
* path: str (Optional) - Directory path to list (defaults to project root)
* filter: str (Optional) - File filter pattern using wildcards (default: "*")
* recursive: bool (Optional) - Whether to list files recursively (default: false)

##### Usage (list project files):
~~~json
{
    "thoughts": [
        "I need to see what JavaScript files are in the src directory"
    ],
    "headline": "Listing JavaScript source files",
    "tool_name": "file:list_files",
    "tool_args": {
        "path": "src",
        "filter": "*.js"
    }
}
~~~

##### Usage (recursive listing):
~~~json
{
    "thoughts": [
        "I want to see all component files throughout the entire project"
    ],
    "headline": "Finding all React component files",
    "tool_name": "file:list_files",
    "tool_args": {
        "path": "src",
        "filter": "*.jsx",
        "recursive": true
    }
}
~~~
