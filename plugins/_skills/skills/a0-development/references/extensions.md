# Extensions

## Source Anchors

- Extension base and discovery: `/a0/helpers/extension.py`
- Backend extension DOX: `/a0/extensions/AGENTS.md`, `/a0/extensions/python/AGENTS.md`
- WebUI extension DOX: `/a0/extensions/webui/AGENTS.md`
- Plugin extension contract: `/a0/plugins/AGENTS.md`
- Example profile note: `/a0/agents/_example/AGENTS.md`

## Python Extension Contract

Backend extensions derive from `helpers.extension.Extension`:

```python
from helpers.extension import Extension

class MyExtension(Extension):
    async def execute(self, **kwargs):
        ...
```

`self.agent` may be `None` for startup or non-agent hooks. Match the arguments supplied by the hook point. Keep imports light because many extensions run in hot paths.

## Python Discovery Layout

`helpers.extension._get_extension_classes(...)` discovers backend extension classes through:

```text
extensions/python/<extension_point>/
```

using `helpers.subagents.get_paths(agent, "extensions/python", extension_point)`.

Common locations:

| Location | Use |
|---|---|
| `extensions/python/<point>/` | Built-in framework extension. |
| `plugins/<plugin>/extensions/python/<point>/` | Bundled plugin extension. |
| `usr/plugins/<plugin>/extensions/python/<point>/` | User plugin extension. |
| `usr/extensions/python/<point>/` | Standalone user extension. Prefer plugin packaging for durable features. |
| Project/profile roots resolved by `helpers.subagents.get_paths(...)` | Scope-specific extension overrides when discovery supports the path. Verify before copying examples. |

The checked-in `_example` profile contains an older-looking `agents/_example/extensions/agent_init/...` sample. Current discovery code expects `extensions/python/<point>`. Treat source code and DOX as authority before copying profile extension layout.

## Ordering And Overrides

- Files are sorted by filename. Numeric prefixes like `_10_`, `_20_`, `_50_` control order.
- Use gaps between prefixes so future extensions can fit between them.
- Discovery de-duplicates by module filename, preserving the first occurrence by search priority.
- Do not bypass secret masking, auth, persistence, or cleanup extensions for convenience.

## Implicit `@extensible` Hooks

Functions decorated with `@extensible` emit two implicit hook points:

```text
_functions/<module>/<qualname>/start
_functions/<module>/<qualname>/end
```

The path preserves every module segment and nested qualname segment. Example:

```text
helpers.something.Outer.Inner.__init__
```

becomes:

```text
_functions/helpers/something/Outer/Inner/__init__/start
_functions/helpers/something/Outer/Inner/__init__/end
```

Extensions receive a mutable `data` dict with `args`, `kwargs`, `result`, and `exception`. They may mutate inputs, short-circuit by setting `result`, or force/clear an exception.

Do not use retired flattened `_functions` folder names.

## Current Built-In Python Hook Directories

Directory-backed built-in hook points currently include:

```text
agent_init
banners
before_main_llm_call
error_format
hist_add_before
hist_add_tool_result
job_loop
message_loop_end
message_loop_prompts_after
message_loop_prompts_before
message_loop_start
monologue_end
monologue_start
process_chain_end
reasoning_stream
reasoning_stream_chunk
reasoning_stream_end
response_stream
response_stream_chunk
response_stream_end
startup_migration
system_prompt
tool_execute_after
tool_execute_before
user_message_ui
util_model_call_before
webui_ws_connect
webui_ws_disconnect
webui_ws_event
```

This list comes from the current `extensions/python/` tree. Re-check the tree before claiming the complete current set.

## WebUI Extension Points

Frontend extension files live under:

```text
extensions/webui/<point>/
plugins/<plugin>/extensions/webui/<point>/
usr/plugins/<plugin>/extensions/webui/<point>/
```

Current built-in WebUI extension directories include:

```text
fetch_api_call_after
fetch_api_call_before
get_message_handler
initFw_end
json_api_call_after
json_api_call_before
right-canvas-panels
right_canvas_register_surfaces
set_messages_after_loop
set_messages_before_loop
webui_ws_push
```

Plugin frontend HTML extensions should include a root Alpine scope and use `x-move-*` directives when targeting static breakpoints. JS extensions export a default function.

## Verification

- Run targeted lifecycle, prompt, stream, WebSocket, or WebUI extension tests for changed hook points.
- Smoke-test startup for `agent_init`, `startup_migration`, and `system_prompt` changes when practical.
- Check the exact directory path used by `helpers.extension` before adding profile or plugin extension files.
