# Wait Plugin DOX

## Purpose

- Own the `wait` tool for pausing agent execution until a duration or timestamp.

## Ownership

- `tools/wait.py` owns argument parsing, validation, and agent-facing tool behavior.
- `helpers/wait.py` owns intervention-aware waiting and remaining-time formatting.
- `prompts/` owns the tool prompt and the wait-complete framework message.
- `extensions/webui/` owns the tool's message presentation.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Duration waits extend the target time by observed intervention pauses; `until` waits keep the absolute target.
- Waiting loops must keep calling `agent.handle_intervention()` so pause/abort stays responsive.
- `tools/wait.py` logs `type="wait"` through a `get_log_object()` override; `extensions/webui/get_message_handler/wait-handler.js` renders it with badge `HLD` and `get_process_step_types/wait-types.js` registers the type for raw-log grouping.
- The plugin owns the historical `progress` presentation: the core `drawMessageProgress` handler and its dispatch case were removed, and old chat logs carrying `type="progress"` route through this plugin's handler.

## Verification

- Run the focused scheduler/wait-related tests under `tests/` after changes.

## Child DOX Index

No child DOX files.
