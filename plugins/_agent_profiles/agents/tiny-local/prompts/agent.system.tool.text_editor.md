### text_editor
Read, write, or patch Markdown and plain text files.

Actions in `tool_args.action`:
- `read`: read a file
- `write`: create or overwrite a file
- `patch`: edit an existing file

Common arguments:
- `path`: absolute file path
- `content`: full file content for `write`
- `open_in_canvas`: set `true` when the user explicitly asks to open a Markdown file in the Canvas or Editor

Rules:
- Use this tool for `.md` and plain text files.
- Use `write` to create a new Markdown file.
- If the user asks to open the file in the Canvas or Editor, include `"open_in_canvas": true` in the same `write` or `patch` call.
- After a successful write or patch result, do not repeat the same tool call. Use the `response` tool unless a different action is needed.

Examples:

`{"tool_name":"text_editor","tool_args":{"action":"write","path":"/a0/usr/workdir/TODO.md","content":"# TODO\n- [ ] First item\n","open_in_canvas":true}}`

`{"tool_name":"text_editor","tool_args":{"action":"read","path":"/a0/usr/workdir/TODO.md"}}`

`{"tool_name":"text_editor","tool_args":{"action":"patch","path":"/a0/usr/workdir/TODO.md","old_text":"- [ ] First item","new_text":"- [x] First item"}}`
