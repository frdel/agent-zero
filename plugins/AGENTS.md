# Plugins DOX

## Purpose

- Own bundled system plugins shipped with Agent Zero.
- Provide the tracked plugin architecture contract for both bundled plugins and custom plugins developed under ignored `usr/plugins/`.
- Keep plugin behavior discoverable, reversible, and compatible across bundled and custom roots without creating DOX files inside `usr/`.

## Ownership

- Each direct `_plugin_name/` directory owns its `plugin.yaml`, optional `default_config.yaml`, `hooks.py`, API handlers, helpers, tools, prompts, skills, extensions, WebUI assets, and README.
- Plugins may also own `execute.py`, `conf/model_providers.yaml`, plugin-distributed `agents/<profile>/agent.yaml`, static assets, and plugin-local docs.
- `README.md` owns the high-level core plugin architecture summary and community Plugin Index guidance.
- Custom or experimental user plugins belong under `usr/plugins/`, not here, but this file remains their tracked DOX contract.
- Do not create `AGENTS.md` files under `usr/plugins/` unless the user explicitly asks for ignored user-state documentation.

## Local Contracts

- Every plugin directory must include a valid `plugin.yaml`.
- Bundled plugin directory names and manifest `name` values must start with `_` to avoid collisions with community plugins.
- Runtime manifest fields include `name`, `title`, `description`, `version`, `settings_sections`, `per_project_config`, `per_agent_config`, and `always_enabled`.
- Core plugins may use `plugins.<plugin_name>...` imports when they are shipped from this tree.
- User plugins under `usr/plugins/` must use `usr.plugins.<plugin_name>...` imports and avoid `sys.path` hacks or persistent symlink-based imports.
- Plugin extension layouts must use `extensions/python/<point>/`, `extensions/python/_functions/<module>/<qualname>/<start|end>/`, and `extensions/webui/<point>/`.
- The `_functions` extension layout preserves every module and nested qualname segment; do not use retired flattened extension folder names.
- Plugin settings defaults belong in `default_config.yaml`; runtime user settings belong under `usr/`.
- Plugin settings resolution order is project/profile, project, user/profile, user plugin config, then bundled `default_config.yaml`.
- `webui/config.html` settings UIs must bind plugin values to `config.*` and modal state/actions to `context.*` through `$store.pluginSettingsPrototype`.
- Plugin model provider overrides belong in plugin `conf/model_providers.yaml` and merge after base `conf/model_providers.yaml`.
- Global and scoped activation are independent and use `.toggle-1` and `.toggle-0`; `always_enabled: true` forces ON and disables UI toggles.
- `hooks.py` runs in the framework runtime. Explicitly target another runtime if a plugin must prepare the agent execution environment.
- `execute.py` is manual user-triggered setup, maintenance, repair, migration, or refresh work; automatic framework behavior belongs in hooks or lifecycle extensions.
- Plugin routes are `GET /plugins/<name>/<path>`, `POST /api/plugins/<name>/<handler>`, and `POST /api/plugins` for management actions.
- `_a0_connector` WebSocket history replay must stay bounded: emit large chat history as paged `connector_context_snapshot` payloads, keep `last_sequence` as the Agent Zero log-output cursor, and avoid sending an entire long transcript in one frame.
- Frontend plugin HTML extensions live under `extensions/webui/<point>/`, include a root Alpine scope, and use `x-move-*` directives when targeting static breakpoints.
- Frontend plugin JS extensions live under `extensions/webui/<point>/` and export a default function. Custom process-step handlers in `get_message_handler` must also register their log types through `get_process_step_types`; standalone types are omitted. See `skills/a0-create-plugin/references/webui.md` for the handler contract.
- Plugin UI must use the A0 notification system for errors, warnings, success, and info instead of inline success/error boxes.
- Bundled plugin WebUI must author Material Symbols as empty `<x-icon name="lowercase_snake_case"></x-icon>` elements and use `:name` for Alpine-driven icon names. Legacy `.material-symbols-outlined` and `.material-icons-outlined` spans remain runtime-compatible for community plugins, but bundled plugins must not introduce new ligature-text spans.
- Banners and discovery cards are provided through Python `banners` extensions by appending dictionaries with unique `id`, `type`, `priority`, and display fields to the `banners` list.
- Alert banner types are `info`, `warning`, and `error`; discovery card types are `hero` and `feature`.
- Banner/card fields may include `title`, `html`, `description`, `thumbnail`, `icon`, `cta_text`, `cta_action`, and `dismissible` depending on type.
- Community discovery cards should use `type: "feature"`; reserve `hero` cards for core system features.
- Supported discovery CTA actions are `open-plugin-config:<plugin_folder_name>`, `open-plugin-hub`, and `open-url:<url>`.
- Plugin deletion or disablement should not leave unmanaged services, symlinks, or files outside plugin-owned paths unless explicitly documented with cleanup.

## Work Guidance

- Prefer plugin-local helpers for behavior used only by one plugin.
- Use shared `helpers/` only for reusable framework behavior.
- Use the notification system for plugin UI feedback.
- Keep plugin README and docs current when user-visible plugin behavior changes.
- Check configuration before injecting setup or discovery banners so configured plugins do not keep advertising setup.
- Use highly unique banner IDs prefixed by plugin name.
- Browser tool prompts must preserve the existing-tab workflow: when a user refers to an already-open URL, tab, or page title, guide agents to `list` and then `set_active` or `navigate` by `browser_id` instead of blindly opening a new tab.
- When preparing community plugins, keep plugin contents at the standalone repository root with `plugin.yaml`, `README.md`, and a root `LICENSE`.
- Plugin Index submissions use a separate `index.yaml` under `a0-plugins/plugins/<name>/`; do not confuse it with runtime `plugin.yaml`.

## Verification

- Run plugin-specific tests after changing a bundled plugin.
- Run framework tests for touched extension points, API handlers, tools, settings, or WebUI surfaces.
- For plugins with external services or browser/desktop integrations, perform a targeted smoke check when practical.
- For banner/discovery changes, verify the Welcome Screen renders alert banners, feature cards, dismiss behavior, priority ordering, and CTA behavior.

## Child DOX Index

Direct child DOX files:

| Child | Scope |
| --- | --- |
| [_a0_connector/AGENTS.md](_a0_connector/AGENTS.md) | HTTP and WebSocket connector integration with remote tools and runtime bridges. |
| [_agent_editor/AGENTS.md](_agent_editor/AGENTS.md) | Deterministic sparse agent-profile editor API, helpers, and WebUI. |
| [_browser/AGENTS.md](_browser/AGENTS.md) | Playwright browser tool, helpers, viewer, and browser panel UI. |
| [_chat_branching/AGENTS.md](_chat_branching/AGENTS.md) | Chat branching from an existing message. |
| [_chat_compaction/AGENTS.md](_chat_compaction/AGENTS.md) | Full-chat compaction into a summary message. |
| [_chat_naming/AGENTS.md](_chat_naming/AGENTS.md) | Built-in manual and Utility Model-assisted chat naming. |
| [_commands/AGENTS.md](_commands/AGENTS.md) | Built-in slash command manager, command file discovery, and chat composer slash picker. |
| [_context_doctor/AGENTS.md](_context_doctor/AGENTS.md) | Tool-call JSON repair and compact persistence before default dispatch. |
| [_context_window/AGENTS.md](_context_window/AGENTS.md) | Context-window token accounting, API, composer indicator, and visibility control. |
| [_code_execution/AGENTS.md](_code_execution/AGENTS.md) | Terminal, Python, and Node.js execution tools and shell runtimes. |
| [_desktop/AGENTS.md](_desktop/AGENTS.md) | Linux desktop runtime, sessions, and desktop surface. |
| [_discovery/AGENTS.md](_discovery/AGENTS.md) | Welcome-screen plugin discovery cards and promotions. |
| [_document_query/AGENTS.md](_document_query/AGENTS.md) | Document parsing, indexing, and Q&A tools. |
| [_editor/AGENTS.md](_editor/AGENTS.md) | Shared text/code editor surface and sessions. |
| [_email_integration/AGENTS.md](_email_integration/AGENTS.md) | IMAP/Exchange polling and SMTP reply integration. |
| [_error_retry/AGENTS.md](_error_retry/AGENTS.md) | Critical exception retry lifecycle hooks. |
| [_goal/AGENTS.md](_goal/AGENTS.md) | Built-in chat goal strip, `/goal` slash command, and agent-facing goal tools. |
| [_infection_check/AGENTS.md](_infection_check/AGENTS.md) | Prompt-injection safety analysis before tool execution. |
| [_kokoro_tts/AGENTS.md](_kokoro_tts/AGENTS.md) | Local Paradee/Kokoro text-to-speech integration. |
| [_memory/AGENTS.md](_memory/AGENTS.md) | Optional persistent recall plugin, knowledge import, tools, and dashboard; do not assume it is enabled outside this plugin. |
| [_migrate_agents/AGENTS.md](_migrate_agents/AGENTS.md) | Built-in migration of chats, projects, memories, instructions, and skills from supported agent harnesses. |
| [_model_config/AGENTS.md](_model_config/AGENTS.md) | Model selection, presets, API-key checks, and scoped overrides. |
| [_oauth/AGENTS.md](_oauth/AGENTS.md) | OAuth-backed model-provider connections and local proxy routes. |
| [_office/AGENTS.md](_office/AGENTS.md) | LibreOffice office artifacts and office canvas sessions. |
| [_onboarding/AGENTS.md](_onboarding/AGENTS.md) | First-time model onboarding wizard. |
| [_orchestrator/AGENTS.md](_orchestrator/AGENTS.md) | External terminal coding-agent orchestration skill, adapter status, and settings UI. |
| [_pin_to_top/AGENTS.md](_pin_to_top/AGENTS.md) | Built-in chat, task, and project-folder sidebar pinning. |
| [_plugin_installer/AGENTS.md](_plugin_installer/AGENTS.md) | Plugin install and update flows from ZIP, Git, and Plugin Index. |
| [_plugin_scan/AGENTS.md](_plugin_scan/AGENTS.md) | LLM-guided security scanner for third-party plugins. |
| [_plugin_validator/AGENTS.md](_plugin_validator/AGENTS.md) | Plugin manifest, structure, convention, and security validator. |
| [_promptinclude/AGENTS.md](_promptinclude/AGENTS.md) | Promptinclude scanning and prompt injection. |
| [_sidebar_folders/AGENTS.md](_sidebar_folders/AGENTS.md) | Project folder presentation, filters, sorting, drag ordering, and chat project moves. |
| [_skills/AGENTS.md](_skills/AGENTS.md) | Active and hidden skill configuration and prompt injection. |
| [_telegram_integration/AGENTS.md](_telegram_integration/AGENTS.md) | Telegram bot integration and per-user chat sessions. |
| [_text_editor/AGENTS.md](_text_editor/AGENTS.md) | Native text read, write, and patch tool. |
| [_time_travel/AGENTS.md](_time_travel/AGENTS.md) | Workspace history, diff, travel, snapshot, and revert flows. |
| [_tool_access/AGENTS.md](_tool_access/AGENTS.md) | Always-on project/profile tool-policy execution gate. |
| [_notify_user/AGENTS.md](_notify_user/AGENTS.md) | Out-of-band user notification tool. |
| [_wait/AGENTS.md](_wait/AGENTS.md) | Wait tool for duration and timestamp pauses. |
| [_whatsapp_integration/AGENTS.md](_whatsapp_integration/AGENTS.md) | WhatsApp Baileys bridge integration. |
| [_whats_new/AGENTS.md](_whats_new/AGENTS.md) | Version-gated What's New showcase modal, card list, and startup trigger. |
| [_whisper_stt/AGENTS.md](_whisper_stt/AGENTS.md) | Whisper speech-to-text integration. |
