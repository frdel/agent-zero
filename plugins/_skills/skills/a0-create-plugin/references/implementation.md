# Plugin Implementation

Sources: `/a0/plugins/AGENTS.md`, `/a0/helpers/plugins.py`, `/a0/helpers/api.py`, `/a0/helpers/tool.py`, and `/a0/agent.py`. Read the current contracts before implementation. UI patterns are in `webui.md`; publication is in `contribute.md`.

## Plugin Manifest (plugin.yaml)

Every plugin must have a `plugin.yaml` or it will not be discovered.

```yaml
name: my_plugin              # required for community plugins; must match dir name (^[a-z0-9_]+$)
title: My Plugin
description: What this plugin does.
version: 1.0.0
settings_sections:
  - agent
per_project_config: false
per_agent_config: false
```

`name`: lowercase, numbers, underscores only (`^[a-z0-9_]+$`). Required by CI when submitting to the Plugin Index - must exactly match the index folder name.

`settings_sections` controls which Settings tabs show a subsection for this plugin. Valid values: `agent`, `external`, `mcp`, `developer`, `backup`. Use `[]` for no subsection.

Activation defaults to ON when no toggle rule exists. Set `per_project_config` and/or `per_agent_config` to enable advanced per-scope switching. Core system plugins may also use `always_enabled: true` to lock the plugin permanently ON (reserved for framework use).

---

## Backend API & Context

For a messaging integration that should expose Agent Zero slash commands, read [Channel Commands](channel-commands.md). It covers the shared catalog/resolver, effects, context binding, and transport-specific menus; forwarding slash text alone does not provide full command compatibility.

### Import Paths
- Correct: `from agent import AgentContext, AgentContextType`
- Correct: `from initialize import initialize_agent`
- Correct for plugin-local Python modules under `usr/plugins/<name>/`: `from usr.plugins.<name>.helpers.module import ...`
- Avoid `sys.path` hacks for plugin-local imports
- Avoid symlink-dependent imports like `from plugins.<name>...` for user/community plugins in `usr/plugins/`

### Sending An Authorized Message In The Framework Process
```python
from agent import AgentContext
from agent import UserMessage

context = AgentContext.use(context_id)
if context is None:
    raise ValueError("Context not found")
task = context.communicate(UserMessage("Message text"))
response = await task.result()
```

### Reading Plugin Settings (backend)
```python
from helpers.plugins import get_plugin_config, save_plugin_config

# Runtime (with running agent - resolves project/profile from context)
settings = get_plugin_config("my_plugin", agent=agent) or {}

# Explicit write target (project/profile scope)
save_plugin_config(
    "my_plugin",
    project_name="my-project",
    agent_profile="default",
    settings=settings,
)
```

### Configuration Hook Caller Context

Use caller context only when the same settings need different behavior for a
known origin. An unlabeled call remains compatible and uses `"api"`; a
plugin-controlled runtime path can opt in explicitly:

```python
settings = get_plugin_config("my_plugin", agent=agent, caller="agent") or {}
```

Its `hooks.py` receives `hook_context={"caller": ...}`. For example, a plugin
can redact a stored credential for a UI-specific path while preserving its
normal runtime configuration:

```python
def get_plugin_config(default=None, hook_context=None, **kwargs):
    caller = (hook_context or {}).get("caller", "api")
    return redact_for_display(default) if caller == "ui" else default
```

The available values are `"ui"`, `"agent"`, and `"api"`. Existing hooks do
not need to change: the framework safely ignores this new argument for hooks
that do not accept it. This is behavior metadata, never authorization; do not
use it to grant or deny access to secrets or other protected data. A
`config.html` alone does not set the caller; its backend load/save path must
pass it explicitly.

---

## Directory Layout
```
/a0/usr/plugins/<name>/
  plugin.yaml           # Required manifest
  hooks.py              # Required when setup/dependencies/initialization/cleanup are needed
  execute.py            # Optional non-lifecycle manual action only; omit by default
  default_config.yaml   # Optional default settings fallback
  README.md             # Optional locally; strongly recommended for community plugins
  LICENSE               # Optional locally (shown in Plugin List UI when present); required at repo root for Plugin Index submission
  agents/
    <profile>/agent.yaml # Optional plugin-distributed agent profile
  api/                  # API Handlers (ApiHandler base class)
  tools/                # Tool subclasses
  helpers/              # Shared Python logic
  prompts/              # Prompt templates
  conf/
    model_providers.yaml # Optional: add or override model providers
  extensions/
    python/<extension_point>/  # Named Python lifecycle extensions
    python/_functions/<module>/<qualname>/<start|end>/  # Implicit @extensible hooks
    webui/<point>/      # HTML/JS hook extensions
  webui/
    config.html         # Optional: plugin settings UI
    my-modal.html       # Full plugin pages
    my-store.js         # Alpine stores
```

Do not create the retired flattened extensible path form `extensions/python/<module>_<qualname>_<start|end>/`. The current runtime only resolves the deep `_functions/<module>/<qualname>/<start|end>` layout for implicit `@extensible` hooks.

### Import rule for plugin-local Python code

Use the fully qualified `usr.plugins.<plugin_name>...` path for plugin-local
imports. This lets plugins keep a normal `helpers/` directory without renaming
it to `<name>_helpers`, and it avoids both `sys.path` mutation and symlink
installation steps.

Good:

```python
from usr.plugins.my_plugin.helpers.runtime import do_work
import usr.plugins.my_plugin.helpers.state as state
```

Avoid:

```python
sys.path.insert(0, ...)
from helpers.runtime import do_work

from plugins.my_plugin.helpers.runtime import do_work
```

## Required Lifecycle Hooks (`hooks.py`)

**All plugin setup, dependency installation, required initialization, and uninstall cleanup MUST be owned by functions in the plugin-root `hooks.py`. These operations MUST NOT live in `execute.py`, including when described as manual setup, post-install, repair, or maintenance.** Installation through the Plugins UI/API must leave the plugin ready to use without an Execute button or an extra setup command.

The framework calls exported functions through `helpers.plugins.call_plugin_hook(...)`:

| Hook | When it runs | Responsibility |
|---|---|---|
| `install()` | After Git/ZIP installation and again after a successful code update | Prepare dependencies, required assets/state, migrations, registrations, and initialization. Safe to rerun without duplicating resources or overwriting user data. |
| `pre_update()` | Immediately before updating plugin code | Stop plugin-owned processes or prepare state when required. |
| `uninstall()` | Before the framework deletes the custom plugin directory | Stop owned processes, unregister integrations, and remove plugin-owned dependencies and resources. |

Hooks run inside the **Agent Zero framework runtime**, not the separate agent execution environment, and may be sync or async. Keep lifecycle entrypoints in `hooks.py`; delegate implementation to plugin-local helpers as needed. For example, with the corresponding helper functions implemented by the plugin:

```python
from usr.plugins.my_plugin.helpers import runtime


def install():
    runtime.install_dependencies()
    runtime.initialize()


def pre_update():
    runtime.stop()


def uninstall():
    runtime.stop()
    runtime.unregister()
    runtime.remove_owned_dependencies()
```

Use plugin-owned dependency directories where possible so cleanup is precise. Reuse compatible shared dependencies; never uninstall shared packages or services needed by Agent Zero or another plugin. Remove owned services, symlinks, registrations, and generated resources too; directory deletion alone does not undo external side effects. Preserve unrelated data and document any plugin-owned user data that uninstall deletes.

Check subprocess results and raise on setup failure rather than reporting success. Clean up partial initialization so install/update can be retried. Required setup must not be deferred solely to first-use API handlers or startup extensions. If initialization must run again at boot, let the startup extension call the same hook or initialization helper while respecting disabled state.

### Manual Actions (`execute.py`)

Omit `execute.py` by default. It is only for a separate, explicitly requested manual action unrelated to the plugin lifecycle, such as exporting a diagnostic report. Never use it to install/uninstall dependencies, perform required setup or initialization, apply required update migrations, or remove the plugin. Renaming lifecycle work as maintenance does not change this rule.

### Environment targeting rules
- If `hooks.py` runs `sys.executable -m pip install ...`, it installs into the same Python environment that is running Agent Zero.
- That is correct for dependencies needed by the plugin inside the framework runtime.
- If the dependency is meant for the separate agent runtime or for OS-level tools, do **not** assume the current environment is correct.

Instead, explicitly switch targets in a subprocess:
- invoke the exact Python interpreter for the target runtime
- activate the target virtualenv in the subprocess before running `pip`
- run the relevant OS package manager from a subprocess configured for the intended environment

In Docker, this usually means `hooks.py` affects `/opt/venv-a0` unless you intentionally target `/opt/venv` or another environment.

---


## API And Tool Contracts

An API handler extends `helpers.api.ApiHandler`, keeps authentication/CSRF defaults, validates input, and returns a dict or Flask response. Its route is `/api/plugins/<name>/<handler>`. See `a0-development` references for HTTP examples; do not import live server contexts into a separate shell process to control the WebUI.

An agent tool extends `helpers.tool.Tool` and returns `helpers.tool.Response`:

```python
from helpers.tool import Tool, Response

class MyTool(Tool):
    async def execute(self, text: str = "", **kwargs) -> Response:
        return Response(message=text, break_loop=False)
```

Provide its callable contract in a policy-filtered `agent.system.tool.*.md` prompt. Do not advertise configurable tools in unconditional system fragments. Keep examples complete and valid JSON.

## Local Verification

Verify the named Docker runtime and source sync first. Use `/opt/venv-a0/bin/python` for framework imports and hooks, and `/opt/venv/bin/python` only for task-runtime code. Compile changed Python, run focused tests, then exercise the actual API/tool/UI path. For lifecycle changes, exercise normal install, repeated install/update, and uninstall through management APIs using isolated test data; confirm readiness without Execute and removal of owned dependencies without touching shared ones. Check effective configuration, plugin toggles, and cleanup. A successful import is not a live behavior test.

For local-only plugins, a GitHub repository and Index submission are unnecessary. Do not add dependencies, pages, tools, or hooks that the requested feature does not need.
