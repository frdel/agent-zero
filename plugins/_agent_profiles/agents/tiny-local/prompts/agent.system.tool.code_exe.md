### code_execution_tool
Run terminal, Python, or Node.js commands.

Arguments in `tool_args`:
- `runtime`: `terminal`, `python`, `nodejs`, or `output`
- `code`: command or script code
- `session`: terminal session id; default `0`
- `reset`: kill a session before running; `true` or `false`

Rules:
- Put the command or script in `code`.
- Use `runtime=output` to poll running work.
- Use `input` for interactive terminal prompts.
- If a session is stuck, call this tool again with the same `session` and `reset=true`.
- Do not claim success from timeout output or a still-running command.
- When counting files, prefer `find` over `ls` so hidden files and type filters are handled.

Examples:

`{"tool_name":"code_execution_tool","tool_args":{"runtime":"terminal","session":0,"reset":false,"code":"ls -1 /tmp | wc -l"}}`

`{"tool_name":"code_execution_tool","tool_args":{"runtime":"python","session":0,"reset":false,"code":"import os\nprint(os.getcwd())"}}`

`{"tool_name":"code_execution_tool","tool_args":{"runtime":"output","session":0}}`
