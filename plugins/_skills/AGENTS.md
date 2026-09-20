# Skills Plugin DOX

## Purpose

- Own the bundled skill collection plus current-chat skill loading, hidden skill configuration, and profile-level visibility policy.

## Ownership

- `skills/` owns the bundled Agent Zero skill collection, moved 1:1 from the former core `skills/` directory; `skills/AGENTS.md` owns its local contract.
- `hooks.py` owns skill config normalization.
- `api/skills_catalog.py` owns skill catalog access and loading selected skills into chat history.
- `webui/` owns skill settings UI and store.
- `default_config.yaml`, `plugin.yaml`, `README.md`, and `LICENSE` own defaults, metadata, docs, and license.

## Local Contracts

- Skills selected in `webui/` load into the current chat history only; do not store them as scope defaults.
- Loaded skills are append-only from the user UI because their instructions live in chat history.
- Store configured skills in normalized portable paths.
- Hidden skills affect catalog/search/load visibility but must not remove loaded skill history.
- A profile visibility policy has an explicit future-skill default. It limits discovery and new loading without pinning skills or removing history-loaded instructions.
- Chat visibility overrides may reverse legacy `hidden_skills`, but cannot re-enable a skill blocked by profile policy.

## Work Guidance

- Coordinate skill loading changes with `skills_tool`, loaded-skill history reattachment, and settings UI.

## Verification

- Run skill runtime/catalog tests or smoke-test active, hidden, global, project, and chat-scope behavior after changes.

## Child DOX Index

Direct child DOX files:

| Child | Scope |
| --- | --- |
| [skills/AGENTS.md](skills/AGENTS.md) | Bundled Agent Zero skill collection and its skill-level contracts. |
