# Agent Profiles Plugin DOX

## Purpose

- Own the bundled specialist agent profiles: developer, hacker, researcher, and tiny-local.

## Ownership

- `agents/<profile>/` owns each profile's `agent.yaml` and `prompts/` overrides, moved 1:1 from the core `agents/` directory.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Profile discovery resolves plugin-provided profiles through the standard chain (project > user > plugin > core) in `helpers/subagents.py`; profile names and file layouts are unchanged, so existing settings, subordinate calls, and project overrides keep resolving.
- The plugin declares `always_enabled: true`: profiles are selectable in settings and valid subordinate targets, and disabling the plugin would break agents configured with them.
- Core `agents/` keeps `agent0` (default setting value), the `default` utility profile, and `_example` (reference profile).
- Profile IDs must not collide with core or user profiles; user overrides in `usr/agents/` and project overrides in `.a0proj/agents/` still take precedence over the plugin layer.

## Verification

- Run the agent profile and settings tests, and verify profile discovery in the framework runtime after changes.

## Child DOX Index

No child DOX files.
