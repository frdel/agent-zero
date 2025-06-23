## Canvas Tool
create and manage interactive visual artifacts for user interface
display HTML CSS JavaScript Python Markdown content in canvas panel
canvas slides in from right side of screen seamlessly integrated with chat

### canvas_tool
create update show list canvas artifacts
- action: "create" "update" "show" "list"
- content: HTML CSS JS Python Markdown code
- type: "html" "css" "javascript" "python" "markdown"
- title: display name for artifact
- description: optional description
- canvas_id: required for update/show operations

usage:

1 create HTML canvas artifact
~~~json
{
    "thoughts": [
        "I need to create an interactive HTML demo...",
        "I'll make a canvas with HTML and CSS...",
    ],
    "tool_name": "canvas_tool",
    "tool_args": {
        "action": "create",
        "type": "html",
        "title": "Interactive Demo",
        "description": "A demonstration of HTML5 features",
        "content": "<div style='padding: 20px; text-align: center;'><h1>Hello Canvas!</h1><button onclick='alert(\"Canvas works!\")'>Click me</button></div>"
    }
}
~~~

2 create Python code display
~~~json
{
    "thoughts": [
        "User wants to see the Python code...",
        "I'll display it in canvas for better visualization...",
    ],
    "tool_name": "canvas_tool", 
    "tool_args": {
        "action": "create",
        "type": "python",
        "title": "Data Analysis Script",
        "content": "import pandas as pd\nimport matplotlib.pyplot as plt\n\n# Load and analyze data\ndf = pd.read_csv('data.csv')\nresult = df.groupby('category').sum()"
    }
}
~~~

3 update existing canvas
~~~json
{
    "thoughts": [
        "Need to update the canvas with new content...",
        "I have the canvas ID from previous creation...",
    ],
    "tool_name": "canvas_tool",
    "tool_args": {
        "action": "update",
        "canvas_id": "a1b2c3d4",
        "content": "<div style='background: linear-gradient(45deg, #ff6b6b, #4ecdc4); padding: 40px; color: white; text-align: center;'><h1>Updated Canvas!</h1></div>"
    }
}
~~~

4 show existing canvas
~~~json
{
    "thoughts": [
        "User asked to see previous canvas...",
        "I'll display the existing one...",
    ],
    "tool_name": "canvas_tool",
    "tool_args": {
        "action": "show",
        "canvas_id": "a1b2c3d4"
    }
}
~~~

5 list all canvas artifacts
~~~json
{
    "thoughts": [
        "Let me check what canvas artifacts exist...",
    ],
    "tool_name": "canvas_tool",
    "tool_args": {
        "action": "list"
    }
}
~~~

### Canvas Best Practices:
- use canvas for visual demonstrations interactive examples data visualizations
- create self-contained HTML with inline CSS JavaScript
- include responsive design meta viewport tags
- use semantic HTML proper styling
- canvas automatically opens when created updated shown
- canvas persists between conversations via file system
- provide meaningful titles descriptions for organization
- canvas supports real-time updates during agent responses
- ideal for: demos tutorials visualizations interactive tools prototypes