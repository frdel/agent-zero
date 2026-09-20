---
name: a0-create-plugin
description: "Build, improve, review or publish Agent Zero plugins; local or community, with focused references."
version: 2.0.0
tags: [plugins, create, develop, review, publish, debug]
triggers:
  - create plugin
  - build plugin
  - new plugin
  - develop plugin
  - write plugin
  - plugin template
  - improve plugin
  - review plugin
  - audit plugin
  - validate plugin
  - check plugin
  - plugin review
  - is my plugin correct
  - plugin checklist
  - contribute plugin
  - publish plugin
  - share plugin
  - submit plugin
  - contribute to plugin hub
  - community plugin
  - open source plugin
  - debug plugin
  - troubleshoot plugin
  - fix plugin
  - plugin not working
  - plugin not loading
  - plugin not showing
  - plugin broken
  - plugin error
  - plugin missing
  - plugin crash
  - how does the plugin system work
---

# Agent Zero Plugin Development

Use this entrypoint to build or improve a plugin, review it, or prepare community contribution. For finding useful existing plugins and installing/updating them, use `a0-manage-plugin`.

## Establish The Target

Honor an explicit local-only or community-contribution request. For a new plugin, if the user has not said which, ask once: "Should this stay local, or be prepared for community contribution?" Do not ask again when the answer is already in the conversation. For an existing plugin, inspect its location/repository and requested outcome; clarify only an unresolved distribution choice.

- Local: work in `/a0/usr/plugins/<name>/`. No public repository or Index submission needed.
- Community: develop and test locally, then prepare a standalone repository and a separate Plugin Index submission using `references/contribute.md`.
- Existing bundled plugin work: edit its tracked owner only when that is the requested task. New custom plugins do not belong in `/a0/plugins/`.

## Required Lifecycle Contract

**Plugin setup, dependency installation, required initialization, and uninstall cleanup MUST use lifecycle functions in the plugin-root `hooks.py`. Never put these operations in `execute.py`, and never require an Execute button or manual post-install command to make a plugin usable.**

- `install()` prepares dependencies and initializes the plugin automatically after installation and again after updates. Make it safe to rerun.
- `pre_update()` stops plugin-owned processes or prepares state before an update when needed.
- `uninstall()` stops plugin-owned processes, removes registrations, and removes plugin-owned dependencies/resources before the framework deletes the plugin directory. Preserve shared dependencies and unrelated user data.
- Keep lifecycle ownership in `hooks.py`; it may delegate to plugin-local helpers. If boot-time initialization is needed, a startup extension may call the same helper or hook; it does not replace install/uninstall hooks.
- Omit `execute.py` unless there is a separate, explicitly requested manual operation unrelated to setup, dependency installation, required initialization, updates, or removal.

## Read Only What The Task Needs

After loading this skill, use `skills_tool` with `action: "read_file"`, `skill_name: "a0-create-plugin"`, and the reference path:

| Work | Reference |
|---|---|
| Manifest, layout, backend, tools, settings, hooks, runtime verification | `references/implementation.md` |
| Channel integrations: shared slash commands, effects, menus, authorization | [references/channel-commands.md](references/channel-commands.md) |
| Alpine stores, settings UI, `x-overflow` controls, notifications, custom message/process-step handlers | [references/webui.md](references/webui.md) |
| Review existing code or verify a completed change | `references/review.md` |
| Standalone repository, license, Index entry, validation and PR | `references/contribute.md` |

## Working Flow

1. Inspect the existing plugin and relevant source. Read `/a0/AGENTS.md`, `/a0/plugins/AGENTS.md`, and the closest applicable contracts.
2. Load the implementation reference, plus the UI reference if needed. Build only the requested capability; reuse existing helpers and patterns.
3. Keep `plugin.yaml` at the plugin root. Use stable underscore names for new custom plugins. Keep credentials and runtime state out of published source.
4. Verify the real target runtime, not just the checkout. Use the framework Python for backend/plugin checks. Read `references/review.md` before declaring the work complete; report actual checks and remaining limitations.
5. For local work, deliver the working plugin and usage instructions. For community work, continue through the contribution reference within the user's publication authorization. Preparing a plugin is not the same as publishing it or merging its Index PR.

## Brief Troubleshooting

Follow the first failing boundary: root `plugin.yaml` and correct directory; global/project/profile toggle and effective config; imports in the framework runtime; API auth/CSRF and route; extension path/breakpoint; store import and gate. Inspect the relevant server/browser error before editing. Use management APIs for lifecycle refreshes; do not manually rerun install/uninstall hooks as a diagnostic or delete state to hide the failure.

## Finish

Report the feature, usage, live verification, and any unresolved limits. For community work, distinguish repository publication, PR creation, CI results, and actual merge. Follow an existing request to commit or publish; otherwise keep changes ready for review.
