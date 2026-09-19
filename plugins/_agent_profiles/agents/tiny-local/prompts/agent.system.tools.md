## Available Tools

Use only the tools listed below. Match tool names exactly.

Every tool request must be exactly one JSON object with only these top-level fields:
- `tool_name`
- `tool_args`

Action names are not tool names. Do not invent top-level `multi`, `read`, `write`, `terminal`, or generic batch tools.

{{tools}}

## Tiny Local Output Rule

Some inherited tool examples may show `thoughts` or `headline`. Ignore that shape for this profile.

Do not include `thoughts`, `headline`, analysis, markdown fences, or prose outside the JSON object.
