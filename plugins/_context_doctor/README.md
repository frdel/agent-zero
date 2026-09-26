# Context Doctor

Repairs model tool call JSON before sending it to history and tool processing.

## Behavior

- Uses `json_repair` after native parsing has completed.
- Accepts only complete Agent Zero tool calls (`tool_name` and object `tool_args`).
- Stores repaired tool calls as compact JSON; log kvps retain streamed reasoning and add transformed fields.
- Expands blank-line-separated thoughts into separate entries after repair when the split strategy is enabled.
- Core recovery validates standalone leaked XML/native calls against offered tools before this plugin; rejected or truncated calls use bounded retries.
- Preserves rejected/multiple envelopes and keeps quoted tool examples non-executable.
- Optionally replaces non-tool XML-like output with `{}`.
