# Agent Zero: MCP Server Integration Guide

This guide explains how to configure and utilize external tool providers through the Model Context Protocol (MCP) with Agent Zero. This allows Agent Zero to leverage tools hosted by separate local or remote MCP-compliant servers.

## What are MCP Servers?

MCP servers are external processes or services that expose a set of tools that Agent Zero can use. Agent Zero acts as an MCP *client*, consuming tools made available by these servers. The integration supports two main types of MCP servers:

1.  **Local Stdio Servers**: These are typically local executables that Agent Zero communicates with via standard input/output (stdio).
2.  **Remote SSE Servers**: These are servers, often accessible over a network, that Agent Zero communicates with using Server-Sent Events (SSE), usually over HTTP/S.

## How Agent Zero Consumes MCP Tools

Agent Zero discovers and integrates MCP tools dynamically:

1.  **Configuration**: You define the MCP servers Agent Zero should connect to in its configuration.
2.  **Tool Discovery**: Upon initialization (or when settings are updated), Agent Zero connects to each configured and enabled MCP server and queries it for the list of available tools, their descriptions, and expected parameters.
3.  **Dynamic Prompting**: The information about these discovered tools is then dynamically injected into the agent's system prompt. A placeholder like `{{tools}}` in a system prompt template (e.g., `prompts/default/agent.system.mcp_tools.md`) is replaced with a formatted list of all available MCP tools. This allows the agent's underlying Language Model (LLM) to know which external tools it can request.
4.  **Tool Invocation**: When the LLM decides to use an MCP tool, Agent Zero's `process_tools` method identifies it as an MCP tool and routes the request to the appropriate `MCPConfig` helper, which then communicates with the designated MCP server to execute the tool.

## Configuration

### Configuration File

The primary location for user-specific Agent Zero settings, including MCP server configurations, is:

*   `tmp/settings.json`

This file is created or updated when you save settings, typically through Agent Zero's settings UI (if available).

### The `mcp_servers` Setting

Within `tmp/settings.json`, the MCP servers are defined under the `"mcp_servers"` key.

*   **Value Type**: The value for `"mcp_servers"` must be a **JSON formatted string**. This string itself contains an **array** of server configuration objects.
*   **Default Value**: If `tmp/settings.json` does not exist, or if it exists but does not contain the `"mcp_servers"` key, Agent Zero will use a default value of `""` (an empty string). This means no MCP servers are configured by default.
*   **Updating**: The recommended way to set or update this value is through Agent Zero's settings UI. When you save settings via the UI, the current configuration (including your MCP server definitions) is written to `tmp/settings.json`.
*   **For Existing `settings.json` Files (After an Upgrade)**: If you have an existing `tmp/settings.json` from a version of Agent Zero prior to MCP server support, the `"mcp_servers"` key will likely be missing. To add this key to your file (initially with an empty string value if you don't configure any servers immediately):
    1.  Ensure you are running the version of Agent Zero that includes MCP server support. If you are using Docker, this might involve rebuilding or pulling the latest image.
    2.  Run Agent Zero.
    3.  Access the settings UI.
    4.  Save the settings. Even if you don't make any changes in the UI during this session, saving will write the complete current settings structure (including `"mcp_servers": ""`) to your `tmp/settings.json` file. You can then populate it with your server configurations as needed.

### MCP Server Configuration Structure

Here are templates for configuring individual servers within the `mcp_servers` JSON array string:

**1. Local Stdio Server**

```json
{
    "name": "My Local Tool Server",
    "description": "Optional: A brief description of this server.",
    "command": "python", // The executable to run (e.g., python, /path/to/my_tool_server)
    "args": ["path/to/your/mcp_stdio_script.py", "--some-arg"], // List of arguments for the command
    "env": { // Optional: Environment variables for the command's process
        "PYTHONPATH": "/path/to/custom/libs:.",
        "ANOTHER_VAR": "value"
    },
    "encoding": "utf-8", // Optional: Encoding for stdio communication (default: "utf-8")
    "encoding_error_handler": "strict", // Optional: How to handle encoding errors. Can be "strict", "ignore", or "replace" (default: "strict").
    "disabled": false // Set to true to temporarily disable this server without removing its configuration.
}
```

**2. Remote SSE Server**

```json
{
    "name": "My Remote API Tools",
    "description": "Optional: Description of the remote SSE server.",
    "url": "https://api.example.com/mcp-sse-endpoint", // The full URL for the SSE endpoint of the MCP server.
    "headers": { // Optional: Any HTTP headers required for the connection.
        "Authorization": "Bearer YOUR_API_KEY_OR_TOKEN",
        "X-Custom-Header": "some_value"
    },
    "timeout": 5.0, // Optional: Connection timeout in seconds (default: 5.0).
    "sse_read_timeout": 300.0, // Optional: Read timeout for the SSE stream in seconds (default: 300.0, i.e., 5 minutes).
    "disabled": false
}
```

**Example `mcp_servers` value in `tmp/settings.json`:**

Remember, the entire array must be a string within the main JSON structure. Quotes within this string must be escaped.

```json
{
    // ... other settings ...
    "mcp_servers": "[{\\\"name\\\": \\\"MyPythonTools\\\", \\\"command\\\": \\\"python3\\\", \\\"args\\\": [\\\"mcp_scripts/my_server.py\\\"], \\\"disabled\\\": false}, {\\\"name\\\": \\\"ExternalAPI\\\", \\\"url\\\": \\\"https://data.example.com/mcp\\\", \\\"headers\\\": {\\\"X-Auth-Token\\\": \\\"supersecret\\\"}, \\\"disabled\\\": false}]",
    // ... other settings ...
}
```

**Key Configuration Fields:**

*   `"name"`: A unique name for the server. This name will be used to prefix the tools provided by this server (e.g., `my_server_name.tool_name`). The name is normalized internally (converted to lowercase, spaces and hyphens replaced with underscores).
*   `"disabled"`: A boolean (`true` or `false`). If `true`, Agent Zero will ignore this server configuration.
*   `"url"`: **Required for Remote SSE Servers.** The endpoint URL.
*   `"command"`: **Required for Local Stdio Servers.** The executable command.
*   `"args"`: Optional list of arguments for local Stdio servers.
*   Other fields are specific to the server type and mostly optional with defaults.

## Using MCP Tools

Once configured and discovered:

*   **Tool Naming**: MCP tools will appear to the agent with a name prefixed by the server name you defined, e.g., if your server is named `"MyPythonTools"` and it offers a tool named `"calculate_sum"`, the agent will know it as `mypythontools.calculate_sum`.
*   **Agent Interaction**: The agent's LLM can then request to use these tools like any other built-in tool, by outputting a JSON structure specifying the `tool_name` and `tool_args`.
*   **Execution Flow**: Agent Zero's `process_tools` method prioritizes looking up the tool name in the `MCPConfig`. If found, the execution is delegated to the corresponding MCP server. If not found as an MCP tool, it then attempts to find a local/built-in tool with that name.

This setup provides a flexible way to extend Agent Zero's capabilities by integrating with various external tool providers without modifying its core codebase. 