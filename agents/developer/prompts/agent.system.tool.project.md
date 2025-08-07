## Project Management Subsystem:
The project management tool enables developers to initialize, select, and manage development projects with comprehensive metadata tracking. When a project is selected or created, it automatically establishes the working context for all file operations and provides rich project information including history, configuration, and documentation.

The tool creates and maintains a `.metadata` file that tracks project information, development instructions, and complete edit history for comprehensive project awareness.

### Tools to manage development projects

#### project:select_or_create
Select an existing project directory or create a new one with automatic metadata initialization. This establishes the project context for all subsequent development operations and enables automatic project layout injection into the agent's system prompt.

##### Arguments:
* path: str - The project directory path (can be relative or absolute)
* description: str (Optional) - Project description for metadata file
* instructions: str (Optional) - Initial development instructions for the project

##### Usage (create new project):
~~~json
{
    "thoughts": [
        "I need to create a new React project with specific setup instructions",
        "This will be a e-commerce frontend application"
    ],
    "headline": "Creating new React e-commerce project",
    "tool_name": "project:select_or_create",
    "tool_args": {
        "path": "./my-ecommerce-frontend",
        "description": "React-based e-commerce frontend application with modern UI components",
        "instructions": "Set up React with TypeScript, implement responsive design, integrate with REST API backend, and include user authentication features"
    }
}
~~~

##### Usage (select existing project):
~~~json
{
    "thoughts": [
        "The user wants to work on an existing project",
        "I should select the project directory they specified"
    ],
    "headline": "Selecting existing project for development",
    "tool_name": "project:select_or_create",
    "tool_args": {
        "path": "/home/user/projects/my-web-app"
    }
}
~~~
