# Agent Profiles

Provides the bundled specialist agent profiles: developer, hacker, researcher, and tiny-local. Each profile directory owns its `agent.yaml` and profile prompt overrides; resolution follows the standard agent discovery chain (project > user > plugin > core).

The plugin follows the standard enabled-state rules; if you disable it, profiles selected in existing settings and subordinate calls that rely on it stop resolving. The core `agents/` directory keeps `agent0`, the `default` utility profile, and the `_example` reference profile.
