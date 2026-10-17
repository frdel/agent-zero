# Goal Plugin DOX

## Purpose

- Own the built-in chat goal strip, `/goal` slash command, goal state API, and agent-facing goal tools.
- Keep chat goals scoped to the active chat context and stored as user data outside tracked plugin code.

## Ownership

- `plugin.yaml` owns the always-enabled `_goal` plugin metadata.
- `tools/goal.py` owns the single agent-facing goal tool, file-backed state under `usr/plugins/_goal/goals/`, and goal status normalization.
- The tool logs its message as type `goal` with an `icon://flag` verb headline such as `Setting goal`, without quoting argument text; `extensions/webui/get_message_handler/` owns the `AIM` badge presentation and `extensions/webui/get_process_step_types/` registers the type.
- `api/goal.py` owns the WebUI JSON API for reading, editing, pausing, resuming, and deleting goals.
- `commands/` owns the `/goal` slash command contributed to `_commands`.
- `webui/` and `extensions/webui/` own the composer goal strip, Goal mode shortcut, and inline controls.
- `tools/goal.py` and `prompts/agent.system.tool.goal.md` own agent-facing goal inspection, creation, and status updates.
- `tools/response.py` overrides the core response tool so an active goal continues the current monologue.
- `extensions/python/message_loop_prompts_after/` owns injecting the active goal into agent context.

## Local Contracts

- Goal status values are `active`, `paused`, `complete`, and `blocked`.
- The `goal` tool reads legacy action values `show`/`status` for `get`, `set` for `create`, and direct `complete`/`blocked` for `update` with `status`; prompts document only canonical actions.
- Active goals are injected into agent extras; paused and blocked goals remain visible in the UI, while complete goals are hidden.
- Goal records track accumulated active time with `elapsed_seconds` and `active_since`; pausing freezes elapsed time until resume.
- User controls may pause, resume, edit, or delete a goal; destructive delete uses inline confirmation. Model tools may create goals and mark them complete or blocked.
- Saving an edit that reactivates a complete or blocked goal resends the edited objective so agent processing resumes.
- `/goal <objective>` creates the goal and sends the objective as the user message so the agent starts working immediately.
- The composer Goal mode shortcut only prefills `/goal ` and focuses the input; it never sends the command.
- `/goal auto` fills the composer with a prompt asking the agent to create and manage its own goal instead of silently sending a message.
- While a goal is active, response-tool calls are intermediate updates; only completing or blocking the goal restores normal loop termination.
- Goal UI feedback uses toast notifications and inline controls, not modal dialogs.
- Goal state changes publish a context revision through the shared state-push
  lifecycle; the WebUI refreshes on context or revision changes and never polls
  the Goal API while idle.
- Snapshot refreshes run without delaying chat rendering. Clear the previous
  chat's goal when refreshing a new selection; only the latest selected-chat
  request may apply results, and stale requests must not finish a newer load.

## Work Guidance

- Keep goal state in `usr/plugins/_goal/`; do not store runtime goal data in tracked files.
- Keep the goal strip mounted through WebUI extension points instead of modifying core composer templates.
- Keep `_commands` compatibility in mind: `/goal` is a plugin-contributed command and should remain read-only in the command manager.

## Verification

- Run `conda run -n a0 pytest plugins/_goal/tests` after changing `_goal` backend behavior.
- Run `_commands` discovery tests when changing the `/goal` command contribution contract.

## Child DOX Index

No child DOX files.
