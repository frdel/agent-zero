# Extensibility framework in Agent Zero

> [!NOTE]
> Agent Zero is built with extensibility in mind. It provides a framework for creating custom extensions, agents, instruments, and tools that can be used to enhance the functionality of the framework.

## Extensible components
- The Python framework controlling Agent Zero is built as simple as possible, relying on independent smaller and modular scripts for individual tools, API endpoints, system extensions and helper scripts.
- This way individual components can be easily replaced, upgraded or extended.

Here's a summary of the extensible components:

### Extensions
Extensions are components that hook into specific points in the agent's lifecycle. They allow you to modify or enhance the behavior of Agent Zero at predefined extension points. The framework uses a plugin-like architecture where extensions are automatically discovered and loaded.

#### Extension Points
Agent Zero provides several extension points where custom code can be injected:

- **agent_init**: Executed when an agent is initialized
- **before_main_llm_call**: Executed before the main LLM call is made
- **message_loop_start**: Executed at the start of the message processing loop
- **message_loop_prompts_before**: Executed before prompts are processed in the message loop
- **message_loop_prompts_after**: Executed after prompts are processed in the message loop
- **message_loop_end**: Executed at the end of the message processing loop
- **monologue_start**: Executed at the start of agent monologue
- **monologue_end**: Executed at the end of agent monologue
- **reasoning_stream**: Executed when reasoning stream data is received
- **response_stream**: Executed when response stream data is received
- **system_prompt**: Executed when system prompts are processed

#### Extension Mechanism
The extension mechanism in Agent Zero works through the `call_extensions` function in `agent.py`, which:

1. Loads default extensions from `/python/extensions/{extension_point}/`
2. Loads agent-specific extensions from `/agents/{agent_profile}/extensions/{extension_point}/`
3. Merges them, with agent-specific extensions overriding default ones based on filename
4. Executes each extension in order

#### Creating Extensions
To create a custom extension:

1. Create a Python class that inherits from the `Extension` base class
2. Implement the `execute` method
3. Place the file in the appropriate extension point directory:
   - Default extensions: `/python/extensions/{extension_point}/`
   - Agent-specific extensions: `/agents/{agent_profile}/extensions/{extension_point}/`

**Example extension:**

```python
# File: /agents/_example/extensions/agent_init/_10_example_extension.py
from python.helpers.extension import Extension

class ExampleExtension(Extension):
    async def execute(self, **kwargs):
        # rename the agent to SuperAgent0
        self.agent.agent_name = "SuperAgent" + str(self.agent.number)
```

#### Extension Override Logic
When an extension with the same filename exists in both the default location and an agent-specific location, the agent-specific version takes precedence. This allows for selective overriding of extensions while inheriting the rest of the default behavior.

For example, if both these files exist:
- `/python/extensions/agent_init/example.py`
- `/agents/my_agent/extensions/agent_init/example.py`

The version in `/agents/my_agent/extensions/agent_init/example.py` will be used, completely replacing the default version.

### Tools
Tools are modular components that provide specific functionality to agents. They are invoked by the agent through tool calls in the LLM response. Tools are discovered dynamically and can be extended or overridden.

#### Tool Structure
Each tool is implemented as a Python class that inherits from the base `Tool` class. Tools are located in:
- Default tools: `/python/tools/`
- Agent-specific tools: `/agents/{agent_profile}/tools/`

#### Tool Override Logic
When a tool with the same name is requested, Agent Zero first checks for its existence in the agent-specific tools directory. If found, that version is used. If not found, it falls back to the default tools directory.

**Example tool override:**

```python
# File: /agents/_example/tools/response.py
from python.helpers.tool import Tool, Response

# example of a tool redefinition
# the original response tool is in python/tools/response.py
# for the example agent this version will be used instead

class ResponseTool(Tool):
    async def execute(self, **kwargs):
        print("Redefined response tool executed")
        return Response(message=self.args["text"] if "text" in self.args else self.args["message"], break_loop=True)
```

#### Tool Execution Flow
When a tool is called, it goes through the following lifecycle:
1. Tool initialization
2. `before_execution` method
3. `execute` method (main functionality)
4. `after_execution` method

### API Endpoints
API endpoints expose Agent Zero functionality to external systems or the user interface. They are modular and can be extended or replaced.

API endpoints are located in:
- Default endpoints: `/python/api/`

Each endpoint is a separate Python file that handles a specific API request.

### Helpers
Helper modules provide utility functions and shared logic used across the framework. They support the extensibility of other components by providing common functionality.

Helpers are located in:
- Default helpers: `/python/helpers/`

### Prompts
Prompts define the instructions and context provided to the LLM. They are highly extensible and can be customized for different agents.

Prompts are located in:
- Default prompts: `/prompts/`
- Agent-specific prompts: `/agents/{agent_profile}/prompts/`

#### Prompt Features
Agent Zero's prompt system supports several powerful features:

##### Variable Placeholders
Prompts can include variables using the `{{var}}` syntax. These variables are replaced with actual values when the prompt is processed.

**Example:**
```markdown
# Current system date and time of user
- current datetime: {{date_time}}
- rely on this info always up to date
```

##### Dynamic Variable Loaders
For more advanced prompt customization, you can create Python files with the same name as your prompt files. These Python files act as dynamic variable loaders that generate variables at runtime.

When a prompt file is processed, Agent Zero automatically looks for a corresponding `.py` file in the same directory. If found, it uses this Python file to generate dynamic variables for the prompt.

**Example:**
If you have a prompt file `agent.system.tools.md`, you can create `agent.system.tools.py` alongside it:

```python
from python.helpers.files import VariablesPlugin
from python.helpers import files

class Tools(VariablesPlugin):
    def get_variables(self, file: str, backup_dirs: list[str] | None = None) -> dict[str, Any]:
        # Dynamically collect all tool instruction files
        folder = files.get_abs_path(os.path.dirname(file))
        folders = [folder]
        if backup_dirs:
            folders.extend([files.get_abs_path(d) for d in backup_dirs])
        
        prompt_files = files.get_unique_filenames_in_dirs(folders, "agent.system.tool.*.md")
        
        tools = []
        for prompt_file in prompt_files:
            tool = files.read_file(prompt_file)
            tools.append(tool)
        
        return {"tools": "\n\n".join(tools)}
```

Then in your `agent.system.tools.md` prompt file, you can use:
```markdown
# Available Tools
{{tools}}
```

This approach allows for highly dynamic prompts that can adapt based on available extensions, configurations, or runtime conditions. See existing examples in the `/prompts/` directory for reference implementations.

##### File Includes
Prompts can include content from other prompt files using the `{{ include "./path/to/file.md" }}` syntax. This allows for modular prompt design and reuse.

**Example:**
```markdown
# Agent Zero System Manual

{{ include "./agent.system.main.role.md" }}

{{ include "./agent.system.main.environment.md" }}

{{ include "./agent.system.main.communication.md" }}
```

#### Prompt Override Logic
Similar to extensions and tools, prompts follow an override pattern. When the agent reads a prompt, it first checks for its existence in the agent-specific prompts directory. If found, that version is used. If not found, it falls back to the default prompts directory.

**Example of a prompt override:**

```markdown
> !!!
> This is an example prompt file redefinition.
> The original file is located at /prompts.
> Only copy and modify files you need to change, others will stay default.
> !!!

## Your role
You are Agent Zero, a sci-fi character from the movie "Agent Zero".
```

This example overrides the default role definition in `/prompts/agent.system.main.role.md` with a custom one for a specific agent profile.

## Subagent Customization
Agent Zero supports creating specialized subagents with customized behavior. The `_example` agent in the `/agents/_example/` directory demonstrates this pattern.

### Creating a Subagent

1. Create a directory in `/agents/{agent_profile}/`
2. Override or extend default components by mirroring the structure in the root directories:
   - `/agents/{agent_profile}/extensions/` - for custom extensions
   - `/agents/{agent_profile}/tools/` - for custom tools
   - `/agents/{agent_profile}/prompts/` - for custom prompts

### Example Subagent Structure

```
/agents/_example/
├── extensions/
│   └── agent_init/
│       └── _10_example_extension.py
├── prompts/
│   └── ...
└── tools/
    ├── example_tool.py
    └── response.py
```

In this example:
- `_10_example_extension.py` is an extension that renames the agent when initialized
- `response.py` overrides the default response tool with custom behavior
- `example_tool.py` is a new tool specific to this agent

## Best Practices
- Keep extensions focused on a single responsibility
- Use the appropriate extension point for your functionality
- Leverage existing helpers rather than duplicating functionality
- Test extensions thoroughly to ensure they don't interfere with core functionality
- Document your extensions to make them easier to maintain and share
