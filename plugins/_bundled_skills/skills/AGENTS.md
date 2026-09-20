# Bundled Skills DOX

## Purpose

- Own the bundled Agent Zero skill collection and its agent-facing instructions.
- Keep skill workflows accurate, composable, and safe for runtime loading.

## Ownership

- This subtree is the `_bundled_skills` plugin's `skills/` collection, moved 1:1 from the former core `skills/` directory and later out of the `_skills` feature plugin.
- Each direct skill directory owns its `SKILL.md` and any local supporting files.
- Skills that explain another plugin's tool or UI surface belong under that plugin's `skills/` directory.
- `setup-a0-cli/` owns primary host-connector setup guidance and remains discoverable without a connected CLI.
- User-local skills belong under `usr/skills/`.

## Local Contracts

- Every skill directory must include a `SKILL.md`.
- Skill discovery resolves this collection through the `_bundled_skills` plugin root in `helpers/skills.py`; skill names and file layouts are unchanged, so search, loading, visibility policy, and project overrides keep resolving.
- The plugin follows the standard enabled-state rules; disabling it removes every bundled skill from discovery.
- Do not include secrets, private user data, or environment-specific credentials.
- Skill instructions must be operational and scoped to the skill's purpose.
- Supporting files referenced by a skill must exist relative to that skill directory.
- Keep bundled catalog descriptions within the 100-character prompt preview, with distinct task and environment/format boundaries. Keep lexical triggers separate.

## Work Guidance

- Keep skills focused on repeatable workflows that agents should actively follow.
- Prefer updating an existing skill over creating overlapping skill variants.
- When a skill refers to repository paths, commands, or plugin architecture, keep those references current with source and docs.

## Verification

- Run skill runtime/import tests after changing skill loading assumptions or skill format.
- Manually read changed `SKILL.md` files for broken relative references.

## Child DOX Index

Direct child DOX files:

| Child | Scope |
| --- | --- |
| [a0-create-agent/AGENTS.md](a0-create-agent/AGENTS.md) | Creating Agent Zero agent profiles. |
| [a0-create-plugin/AGENTS.md](a0-create-plugin/AGENTS.md) | Plugin authoring entrypoint with implementation, UI, review, and contribution references. |
| [a0-development/AGENTS.md](a0-development/AGENTS.md) | Broad Agent Zero framework development guidance. |
| [a0-manage-plugin/AGENTS.md](a0-manage-plugin/AGENTS.md) | Plugin Index discovery/recommendations and lifecycle operations. |
| [build-skill/AGENTS.md](build-skill/AGENTS.md) | Building and improving Agent Zero skills. |
| [scheduled-tasks/AGENTS.md](scheduled-tasks/AGENTS.md) | Managing scheduled, planned, and adhoc tasks. |
