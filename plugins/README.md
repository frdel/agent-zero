# Agent Zero - Core Plugins

This directory contains the system-level plugins bundled with Agent Zero.

## Directory Structure

- `plugins/`: Core system plugins. Reserved for framework updates — do not place custom plugins here.
- `usr/plugins/`: The correct location for all user-developed and custom plugins. This directory is gitignored.

## Documentation

For detailed guides on how to create, extend, or configure plugins, refer to:

- [`plugins/AGENTS.md`](AGENTS.md): Bundled and custom plugin architecture, manifest format, extension points, banners, and Plugin Index submission rules.
- [`docs/developer/plugins.md`](../docs/developer/plugins.md): Human-facing developer guide covering the full plugin lifecycle.
- [`AGENTS.md`](../AGENTS.md): Main framework guide and backend context.
- [`_skills/skills/a0-create-plugin/SKILL.md`](_skills/skills/a0-create-plugin/SKILL.md): Agent-facing authoring entrypoint with implementation, review, and contribution references.
- [`_skills/skills/a0-manage-plugin/SKILL.md`](_skills/skills/a0-manage-plugin/SKILL.md): Find useful Index plugins and manage installation, configuration, and lifecycle.

## What a Plugin Can Provide

Plugins are automatically discovered based on the presence of a `plugin.yaml` file. Each plugin can contribute:

- **Backend**: API handlers, tools, helpers, named lifecycle extensions, and implicit `@extensible` hooks under `extensions/python/_functions/...`
- **Frontend**: HTML/JS UI contributions via core extension breakpoints
- **Settings**: Isolated configuration scoped per-project and per-agent profile
- **Activation**: Global and scoped ON/OFF rules via `.toggle-1` and `.toggle-0` files, including advanced per-scope switching in the WebUI
- **Agent profiles**: Plugin-distributed subagent definitions under `agents/<profile>/agent.yaml`

Backend extension layouts:
- `extensions/python/<point>/` for named lifecycle hooks
- `extensions/python/_functions/<module>/<qualname>/<start|end>/` for implicit `@extensible` hooks

Do not use the retired flattened `extensions/python/<module>_<qualname>_<start|end>/` form.

## Plugin Manifest

Every plugin requires a `plugin.yaml` at its root:

```yaml
name: my_plugin              # required for community plugins
title: My Plugin
description: What this plugin does.
version: 1.0.0
settings_sections:
  - agent
per_project_config: false
per_agent_config: false
always_enabled: false
```

## Plugin Script (`execute.py`)

Plugins can include an optional `execute.py` at the plugin root for user-triggered operations such as setup, post-install steps, maintenance, repairs, migrations, or resource refreshes. Users trigger it from the Plugin List UI.

Guidelines:
- Treat it as a manual plugin script, not as the primary way to use the plugin
- Prefer making it safe to rerun, or detect state and explain why a rerun is not appropriate
- Return `0` on success and print progress messages for user feedback
- Use `hooks.py` instead when the behavior is framework-internal or should happen automatically

## Runtime Hooks (`hooks.py`)

Plugins can also include an optional `hooks.py` at the plugin root. The framework loads it on demand and can call exported hook functions by name through `helpers.plugins.call_plugin_hook(...)`.

- `hooks.py` runs inside the **Agent Zero framework runtime and Python environment**.
- Use it for framework-internal work such as install hooks, cache preparation, registration, or filesystem setup.
- If it runs `sys.executable -m pip install ...`, packages are installed into the same Python environment that runs Agent Zero.
- If you need to install into the separate agent runtime or into the system environment, explicitly target that environment from a subprocess by selecting the correct interpreter, virtualenv, or package manager.

In Docker, `hooks.py` normally affects `/opt/venv-a0`; the agent execution runtime is `/opt/venv`.

### Configuration Hook Context

Configuration hooks can distinguish why settings are being read or saved. Pass
`caller="ui"` or `caller="agent"` to `get_plugin_config(...)` or
`save_plugin_config(...)`; calls without it keep the compatible default,
`"api"`.

The hook receives this as `hook_context={"caller": ...}`:

```python
def get_plugin_config(default=None, hook_context=None, **kwargs):
    caller = (hook_context or {}).get("caller", "api")
    if caller == "ui":
        return redact_for_display(default)
    return default
```

Existing hooks need no change: hooks that ignore `hook_context`, including
strict signatures without `**kwargs`, retain their previous behavior. Use the
context only for behavior selection in plugin-controlled flows; it is not an
authorization boundary. A `config.html` alone does not set the caller; the
backend code loading or saving that configuration must pass it explicitly.

## Plugin Index & Community Sharing

The **Plugin Index** at https://github.com/agent0ai/a0-plugins is the community-maintained registry of plugins available to all Agent Zero users.

To share a plugin with the community:

1. Create a standalone GitHub repository with the plugin contents at the repo root. The runtime `plugin.yaml` must include a `name` field matching the intended index folder name. Add a `LICENSE` file at the repo root (required for Plugin Index listings so users have explicit terms of use).
2. Fork `https://github.com/agent0ai/a0-plugins` and add a folder `plugins/<your_plugin_name>/` containing a separate index manifest named `index.yaml` (not `plugin.yaml`):

```yaml
title: My Plugin
description: What this plugin does.
github: https://github.com/yourname/your-plugin-repo
tags:
  - tools
```

Optional additional fields: `screenshots` (up to 5 image URLs).

3. Open a Pull Request. CI validates the submission; a maintainer reviews and merges.

Note: The index `index.yaml` is a **different file with a different schema** from the runtime `plugin.yaml`. Folder names use `^[a-z0-9_]+$` (underscores, no hyphens) and must match the `name` field in the remote `plugin.yaml` exactly.

## Plugin Hub

Agent Zero now includes a built-in Plugin Hub flow through the always-enabled **Plugin Installer** plugin. From the **Plugins** dialog, users can either open the **Browse** tab or click **Install**, which opens the installer modal on its own **Browse** tab.

The Plugin Hub surfaces Plugin Index entries directly in the UI and lets users search, filter, inspect, and install community plugins without leaving Agent Zero.
