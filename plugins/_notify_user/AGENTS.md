# Notify User Plugin DOX

## Purpose

- Own the `notify_user` tool for out-of-band user notifications.

## Ownership

- `tools/notify_user.py` owns argument validation and dispatch to the shared notification manager.
- `prompts/` owns the tool prompt and the notification-sent framework message.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Notification types and priorities are validated against `helpers.notification` enums; invalid values return tool errors instead of raising.
- The tool uses the shared `AgentContext.get_notification_manager()`; it owns no notification storage of its own.

## Verification

- Import the tool in the framework runtime and run the tool contract tests after changes.

## Child DOX Index

No child DOX files.
