# Tools

## Source Anchors

- Tool base class: `/a0/helpers/tool.py`
- Core tool contract: `/a0/tools/AGENTS.md`
- Tool dispatch path: `/a0/agent.py`
- Skills tool reference-file behavior: `/a0/tools/skills_tool.py`
- Example profile tool: `/a0/agents/_example/tools/example_tool.py`
- Prompt fragments: `/a0/prompts/AGENTS.md`

## Contract

All tools derive from `helpers.tool.Tool` and implement:

```python
from helpers.tool import Tool, Response

class MyTool(Tool):
    async def execute(self, **kwargs) -> Response:
        return Response(message="done", break_loop=False)
```

`Response` fields:

| Field | Meaning |
|---|---|
| `message` | Text appended as the tool result and shown back to the agent. |
| `break_loop` | `True` stops the current message loop. |
| `additional` | Optional metadata added with the tool result. |

`Tool` instances receive `agent`, `name`, `method`, `args`, `message`, and `loop_data`. Use `self.method` for method-style tools such as `skills_tool:load`.

## Locations

| Location | Use |
|---|---|
| `tools/` | Core framework tools. Use only for bundled framework behavior. |
| `plugins/<plugin>/tools/` | Bundled plugin tools. |
| `usr/plugins/<plugin>/tools/` | User plugin tools. This is the preferred place for custom plugin work. |
| `agents/<profile>/tools/` | Profile-local tools. Verify current discovery before relying on profile examples. |

Most new tools should be packaged in a plugin, not added directly to root `tools/`.

## Prompt Contract

Every tool needs an agent-facing prompt fragment so the model knows the tool name, JSON shape, arguments, and when to use it.

Common locations:

- Core tool prompt: `prompts/agent.system.tool.<tool_name>.md`
- Plugin tool prompt: `plugins/<plugin>/prompts/agent.system.tool.<tool_name>.md`
- User plugin prompt: `usr/plugins/<plugin>/prompts/agent.system.tool.<tool_name>.md`
- Profile override prompt: `agents/<profile>/prompts/agent.system.tool.<tool_name>.md`

When changing a tool name, argument shape, output behavior, safety rule, or `break_loop` behavior, update its prompt and tests together.

## Progress And Interventions

- Use `await self.set_progress(...)` when progress should be visible through the tool-output update extension.
- `self.add_progress(...)` only accumulates local progress text.
- For long-running or external-result workflows, follow `tools/AGENTS.md` and use `await self.agent.handle_intervention(...)` where pause/intervention flow matters.
- Sanitize and mask secrets before logging or returning outputs.

## Core Tool DOX

Direct files under `tools/*.py` require matching `tools/*.py.dox.md`. The companion file owns purpose, arguments, output, `break_loop`, side effects, prompt contract notes, dependencies, and verification.

Plugin tool documentation belongs in that plugin's docs or DOX contract, not in root `tools/`.

## Verification

- Run targeted tests for changed tools.
- Run prompt/snapshot tests when tool instructions or output shape changes.
- For direct root tools, verify every `tools/*.py` has a matching `.py.dox.md`.
- If the tool is plugin-scoped, also run plugin-specific checks from the plugin's `AGENTS.md`.
