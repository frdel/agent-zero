# Plugins And Development Workflow

## Source Anchors

- Plugin contract: `/a0/plugins/AGENTS.md`
- Plugin helper code: `/a0/helpers/plugins.py`
- Plugin entrypoints: `/a0/plugins/_bundled_skills/skills/a0-create-plugin/SKILL.md` and `/a0/plugins/_bundled_skills/skills/a0-manage-plugin/SKILL.md`
- Root development contract: `/a0/AGENTS.md`

## Plugin-First Rule

Plugins are the primary way to extend Agent Zero. A plugin can bundle:

- `plugin.yaml`
- `default_config.yaml`
- `hooks.py` (required for setup, dependencies, initialization, and cleanup)
- `execute.py` (optional non-lifecycle manual action only)
- `tools/`
- `api/`
- `helpers/`
- `prompts/`
- `skills/`
- `extensions/python/`
- `extensions/webui/`
- `webui/`
- plugin-local docs and assets

Use root framework directories only when changing bundled framework behavior itself. For custom or experimental work, use `usr/plugins/<plugin>/` unless the task is explicitly to change a bundled plugin.

## Imports And Runtime

- Bundled plugins under `plugins/` may use `plugins.<plugin_name>...` imports.
- User plugins under `usr/plugins/` should use `usr.plugins.<plugin_name>...` imports.
- Avoid `sys.path` hacks and symlink-dependent imports.
- `hooks.py` runs inside the framework runtime (`/opt/venv-a0` in Docker). Install/update setup and dependency installation belong in `install()`; cleanup and removal of owned dependencies belong in `uninstall()`. Never use `execute.py` for these operations. Follow the required lifecycle contract in `a0-create-plugin`.
- If a plugin must prepare the agent execution runtime or system packages, it must explicitly target that environment in a subprocess.

## Manifest And Configuration

Every plugin needs `plugin.yaml`. Runtime fields include:

- `name`
- `title`
- `description`
- `version`
- `settings_sections`
- `per_project_config`
- `per_agent_config`
- `always_enabled`

Defaults belong in `default_config.yaml`. Runtime user settings belong under `usr/`.

Settings resolution order is project/profile, project, user/profile, user plugin config, then bundled `default_config.yaml`.

## Activation And Cleanup

- Global and scoped activation are independent.
- Activation files use `.toggle-1` for ON and `.toggle-0` for OFF.
- `always_enabled: true` forces ON and disables UI toggles.
- Plugin deletion or disablement should not leave unmanaged services, symlinks, or files outside plugin-owned paths unless explicitly documented with cleanup.

## Routes And UI

Plugin routes:

| Route | Purpose |
|---|---|
| `GET /plugins/<name>/<path>` | Static/plugin web assets. |
| `POST /api/plugins/<name>/<handler>` | Plugin API handler. |
| `POST /api/plugins` | Plugin management actions. |

Plugin settings UIs should bind saved values to `config.*` and modal-only state/actions to `context.*` through `$store.pluginSettingsPrototype`.

Plugin UI errors, warnings, success, and info should use the A0 notification system.

## Workflow

1. For authoring, changes, review or contribution, load `a0-create-plugin` and its relevant references.
2. For finding useful plugins or managing installed ones, load `a0-manage-plugin`.
3. Honor a stated local/community target; ask only if that choice is missing before creating a new plugin.
4. Read `plugins/AGENTS.md` and any plugin-local `AGENTS.md`.
5. Keep changes inside the plugin boundary unless shared framework behavior truly belongs in root code.
6. Update plugin docs/DOX when behavior, configuration, routes, hooks or cleanup changes.

## Verification

- Run plugin-specific tests after changing a bundled plugin.
- Run framework tests for touched tools, API handlers, extension points, settings, or WebUI surfaces.
- Smoke-test external-service, browser, desktop, or connector integrations when practical.
- For discovery banners/cards, verify rendering, dismiss behavior, ordering, and CTA behavior.
