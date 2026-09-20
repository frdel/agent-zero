---
name: a0-manage-plugin
description: "Find useful Plugin Index matches; inspect, scan, install, update and manage Agent Zero plugins."
version: 2.0.0
tags: [plugins, discovery, recommend, install, update, scan, manage, plugin-hub]
triggers:
  - find plugins
  - useful plugins
  - recommend plugins
  - recommend a plugin
  - plugin recommendations
  - scan plugin index
  - browse plugins
  - search plugins
  - plugin hub
  - plugin index
  - list plugins
  - install plugin
  - uninstall plugin
  - remove plugin
  - delete plugin
  - update plugin
  - scan plugin
  - enable plugin
  - disable plugin
---

# Agent Zero Plugin Management

Use this skill to find useful existing plugins and manage installed ones. For building, changing code, review or contribution, load `a0-create-plugin`.

## Choose The Workflow

| Need | Read |
|---|---|
| Search the Plugin Index, compare candidates, recommend useful plugins | `references/discovery.md` |
| Security scan, install, update, config, enable/disable or remove | `references/lifecycle.md` |

Read references through `skills_tool` with `action: "read_file"`, `skill_name: "a0-manage-plugin"`, and the file path. API examples reuse the session/CSRF client in `/a0/plugins/_bundled_skills/skills/a0-development/references/operate-agent-zero.md`. Load `a0-development` before reading that reference through `skills_tool`; discover the correct live origin.

## Discovery Discipline

Start with the user's outcome and existing capabilities. Search the current Index by task vocabulary and synonyms, inspect plausible candidates, then recommend a small shortlist with reasons and requirements. Use the whole catalog for broad requests; do not mistake the first page of keyword matches for the best plugins.

Distinguish browsing the Index from running the model-based security scanner. Discovery does not install plugins, execute their code, or authorize scans of every match. Report advertised capabilities separately from verified behavior; include already-installed status and any external services, credentials or costs the candidate needs.

## Lifecycle Discipline

Use framework management APIs so hooks, caches and UI state stay consistent. Confirm the requested plugin and scope before changing it. Third-party plugins execute code in the Agent Zero environment: explain that risk and offer a security scan once before install, respecting an earlier scan choice. Do not turn an install or removal request into repeated confirmation prompts when the user has already specified the action and target.

**Installation and removal must run the plugin's `hooks.py` lifecycle through these APIs. Never use `execute.py` or ask the user to click Execute for setup, dependency installation, required initialization, or uninstall cleanup.** If a plugin requires such a step, treat it as a plugin defect and route the fix to `a0-create-plugin`; do not silently use the manual workaround.

Verify the API result and read back installed/config/toggle state. Preserve unrelated scoped overrides and local code changes. Do not use raw Git pulls or folder deletion as substitutes for normal lifecycle APIs.

For a broken plugin, first check its identity, installation, effective toggle/config and relevant error. If the failure is in plugin code, use the brief troubleshooting guidance in `a0-create-plugin`.
