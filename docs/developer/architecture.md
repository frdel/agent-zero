# Architecture

Agent Zero architecture is now documented in
[DeepWiki for Agent Zero](https://deepwiki.com/agent0ai/agent-zero).

Use DeepWiki when you want source-linked explanations of:

- the agent loop and message flow;
- Web UI internals;
- plugin discovery and lifecycle;
- projects, memory, tools, and scheduler internals;
- backend APIs and WebSocket behavior;
- deployment and runtime structure.

This local page intentionally stays short so the repository does not maintain a
second, stale architecture manual.

## Practical Starting Points

| Goal | Start here |
| --- | --- |
| Install or update Agent Zero | [Installation Guide](../setup/installation.md) |
| Learn the Web UI | [Usage Guide](../guides/usage.md) |
| Create a focused workspace | [Projects Guide](../guides/projects.md) |
| Use the Browser | [Browser Guide](../guides/browser.md) |
| Connect host files and shell | [A0 CLI Connector](../guides/a0-cli-connector.md) |
| Build plugins | [Plugins](plugins.md) |
| Build extensions | [Extensions](extensions.md) |
| Configure MCP | [MCP Configuration](mcp-configuration.md) |
| Enable durability and recovery | [Durability](durability.md), [PostgreSQL workers](durability-postgres.md) |

If you are changing core behavior, read the relevant DeepWiki page first, then
inspect the source in this repository before editing.
