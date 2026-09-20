# Skills

Skills is a built-in Agent Zero plugin that manages current-chat skill loading
and layered skill visibility, including profile-level policy from Agent Editor.

## What It Does

- loads selected skills into current-chat history
- hides noisy skills from the model-facing available catalog, skill search, and load access
- shows loaded skills without offering removal, because loaded skill bodies are part of chat history
- lets users hide or show skills live per conversation
- supports global/project settings plus profile-level Agent Editor visibility policy
- links directly to the built-in Skills list
- links directly to the active project's Skills section when a project is active

## Why This Exists

Agent Zero already supports loading skills dynamically with `skills_tool`, and already has great built-in skill management surfaces. What it did not have was a lightweight way to use that same history-backed skill loading from the Skills screen.

Skills fills that gap as a bundled built-in plugin.

The plugin also owns the bundled Agent Zero skill collection under `skills/`, moved 1:1 from the former core `skills/` directory. The shared skill discovery and loaded-skill ledger live in `helpers/skills.py`, and this plugin focuses on the bundled collection, catalog UI, chat loading, and visibility. The plugin is always enabled so the bundled skills stay discoverable.

## Notes

- selected skills are appended to current-chat history using the same metadata shape as `skills_tool`
- loaded skills are not removable from the UI; future context compaction may reattach their bodies from the loaded-skill ledger
- hidden skills are stored as control data, not injected into the prompt
- hidden skill paths are stored in normalized `/a0/...` form so configs stay portable across development and Docker-style layouts
- if a configured hidden skill is not visible in the current agent scope, it is skipped quietly instead of breaking catalog builds
- profile visibility uses sparse Allowed/Blocked exceptions with an explicit
  default for future skills; allowing a skill does not load or pin it
