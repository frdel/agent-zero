# Bundled Skills Plugin DOX

## Purpose

- Own the bundled Agent Zero skill collection as an always-available plugin skill root.

## Ownership

- `skills/` owns the bundled skill collection, moved 1:1 from the former `_skills` plugin.
- `skills/AGENTS.md` owns the collection's skill-level contracts.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- The plugin declares `always_enabled: true` so bundled skills keep resolving independently of the `_skills` feature plugin and other toggles; disabling it would remove every bundled skill from discovery.
- The plugin owns no runtime code; discovery resolves `skills/` through the standard plugin skill-root scan in `helpers/skills.py`.
- Skill loading, visibility policy, and the catalog API stay owned by the `_skills` plugin.

## Work Guidance

- Add or edit skills only under `skills/`, following its collection contract.

## Verification

- Run the skill runtime, catalog, and scan tests after moving or adding skills, and confirm `helpers/skills.py` resolves every bundled skill through this plugin root.

## Child DOX Index

| Child | Scope |
| --- | --- |
| [skills/AGENTS.md](skills/AGENTS.md) | Bundled skill collection and its skill-level contracts. |
