# integration_commands.py DOX

## Purpose

- Own the `integration_commands.py` helper module.
- This module parses external integration slash commands such as project/model/send controls.
- Keep this file-level DOX profile synchronized with `integration_commands.py` because this directory is intentionally flat.

## Ownership

- `integration_commands.py` owns the runtime implementation.
- `integration_commands.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Public command helpers are `extract_command_line`, `parse_command`, `resolve_command`, `telegram_menu_commands`, `command_names`, `help_text`, `unknown_command_text`, and `try_handle_command`.
- Internal handlers own queue, status, session, lifecycle, toggle, project, model-preset, and agent-profile commands.
- Notable constants are `COMMAND_REGISTRY`, `_CLEAR_VALUES`, and `_MODEL_INHERIT_VALUES`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem writes, model calls, plugin state, settings/state persistence.
- Imported dependency areas include: `__future__`, `helpers`, `helpers.persist_chat`, `helpers.state_monitor_integration`, `plugins._model_config.helpers`, `re`, `typing`.
- `/agent` switches the top-level chat profile and preserves existing
  subordinate agent profiles. Choices come from the shared presentation
  catalog, though status may report an existing chat using the utility profile.
- Explicit `/agent` selection records the `agent_profile_manually_set` context
  data flag so manual selections are protected from project-default
  reconciliation in `helpers/projects.py`.
- `/model <preset>` stores a per-chat global preset reference, `/model inherit` clears it, and status always reports the effective scoped-or-chat preset. `Default` is a real selectable preset, not an alias for clearing the chat selection.

## Key Concepts

- Important called helpers/classes include `mq.get_queue`, `mq.send_all_aggregated`, `mark_dirty_for_context`, `projects.activate_project`, `initialize_agent`, `model_config.get_effective_preset_name`, `model_config.get_presets`, `context.get_data`, `context.set_data`, and `save_tmp_chat`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_subagent_profiles.py`

## Child DOX Index

No child DOX files.
