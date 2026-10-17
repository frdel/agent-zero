# Telegram Integration Plugin DOX

## Purpose

- Own Telegram bot integration for Agent Zero with polling, webhook, per-user sessions, and file exchange.

## Ownership

- `helpers/bot_manager.py` owns bot lifecycle.
- `helpers/handler.py` and `helpers/telegram_client.py` own message routing, replies, and Telegram API interaction.
- `helpers/slash_commands.py` adapts the shared Commands resolver and effects to Telegram replies, menus, session bindings, exports, and compaction confirmation.
- `helpers/settings_ui.py` owns Telegram plugin toggles and tool-permission menus, delegating writes to the existing plugin and Agent Editor owners.
- `hooks.py` normalizes saved/read bot configurations, supplies stable names for unnamed bots, and rejects duplicate names on save.
- `helpers/dependencies.py` and `requirements.txt` own framework-runtime dependency bootstrap.
- `api/`, `prompts/`, `extensions/`, `default_config.yaml`, `plugin.yaml`, `README.md`, and `webui/` own tests/webhook endpoints, prompt fragments, hooks, settings, metadata, docs, and UI.
- `webui/config.html` is the sole plugin WebUI, including bot setup and connection checks.

## Local Contracts

- Treat bot tokens, chat IDs, attachments, and user data as sensitive.
- Keep allowed-user, group-mode, project, model, and `/send` controls enforced.
- Resolve raw commands before adding the Telegram message envelope; its closing marker prevents queued/rendered text from being interpreted as a second postfix command. Custom/project definitions override bundled commands; keep Telegram's existing integration aliases and pickers for unoverridden commands.
- `/commands` discovers the current chat's effective commands on each use. The native Telegram menu registers global commands at startup, maps hyphens to underscores, and obeys Telegram's name/description/count limits.
- Render text/script results and supported effects in Telegram. Browser-only settings return guidance instead of pretending to open a modal; host computer permissions remain controlled by Launcher/CLI.
- Permission callbacks bind canonical tool IDs to the current context/project/profile, revalidate the live catalog, and refuse changes during an active run. Required tools stay outside the menu. Plugin toggles are instance-wide, protect always-enabled plugins, and keep Telegram/Commands enabled so the connection remains controllable.
- `/new` creates and binds a fresh context without resetting the previous chat. `/clear` retains Telegram's existing reset behavior. Compaction confirms the current idle context and uses the existing backup-producing compactor.
- Restart bots when their token, delivery mode, group mode, webhook URL, or webhook secret changes. Polling may start on the next job-loop tick after saving settings.
- Webhook dispatch requires an active webhook and a matching nonempty secret header. Setup requires a random 32–256 character secret using letters, digits, `_` or `-`; polling and webhook removal revoke HTTP delivery.
- Install Telegram dependencies into the framework runtime only when required.
- Keep project and agent-profile configuration scopes available through the shared plugin settings modal.
- Agent profile picker actions change the top-level chat profile and must
  preserve existing subordinate agent profiles. Picker rows and direct matches
  use the shared presentation catalog while current status may still report an
  existing chat that uses the utility profile.
- Explicit agent picker selections record the `agent_profile_manually_set`
  context flag so project-default reconciliation cannot override them.
- Model picker status shows the effective preset; clearing a chat override returns to its scoped preset rather than assuming `Default`.

## Work Guidance

- Coordinate bot lifecycle changes with job-loop hooks and settings reload behavior.
- WebUI store initialization must ignore Alpine registration calls without a configuration object.

## Verification

- Smoke-test connection checks, polling or webhook delivery, per-user context reuse, attachments, and replies when practical.
- Run `PYTHONPATH=. conda run -n a0 python -m pytest -q tests/test_telegram_commands.py tests/test_telegram_webhook_security.py` for command routing, menu bounds, configuration normalization, and bot lifecycle regressions.

## Child DOX Index

No child DOX files.
