# Notify User Plugin DOX

## Purpose

- Own the `notify_user` tool for notifications while the chat runs on its own for a longer time.

## Ownership

- `tools/notify_user.py` owns argument validation and dispatch to the shared notification manager.
- The tool logs its message as type `notify_user` with an `icon://notifications Notifying user: <title>` headline.
- `extensions/webui/get_message_handler/` owns the `notify_user` message presentation with the `NTF` badge.
- `extensions/webui/get_process_step_types/` registers the `notify_user` process step type.
- `extensions/webui/page-head/` and `webui/css/` own the badge accent styles.
- `prompts/` owns the tool prompt and the notification-sent framework message.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- `priority` accepts `normal` and `high` names and maps to `NotificationPriority` values; unknown names and types return tool errors instead of raising.
- The tool uses the shared `AgentContext.get_notification_manager()`; it owns no notification storage of its own.
- The WebUI handler registers only for the `notify_user` message type and reuses `drawMessageToolSimple` with code `NTF`.
- Agent notifications use the longer 30 second display time so they survive brief chat switches.
- `prompts/agent.system.tool.notify_user.md` gates sends to a false or stale user picture: a dropped, replaced, or contradicted strategy, plan, or assumption the user has seen; start, resume, continue, attempt, task end, and goal completion are excluded, and delegated work reports to its parent.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with the tool prompt and the shared notification contract.
- Respect intervention flow before raising user-visible notifications.

## Verification

- Import the tool in the framework runtime and run the tool contract tests after changes.
- Run `tests/test_notify_user_tool.py` for the tool execution regression tests.

## Child DOX Index

No child DOX files.
