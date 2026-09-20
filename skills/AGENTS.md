# Bundled Skills Pointer DOX

## Purpose

- Keep the historical `skills/` path documented for contributors and older references.
- Point readers to the current bundled skill collection instead of duplicating its contracts.

## Ownership

- The bundled skill collection lives in `plugins/_skills/skills/`; that subtree owns all skill-level contracts, including `plugins/_skills/skills/AGENTS.md`.
- This file owns nothing else and must not hold skills, `SKILL.md` files, or local assets.

## Local Contracts

- Skill discovery ignores this directory: `helpers/skills.py` resolves bundled skills through the always-enabled `_skills` plugin root only.
- Do not add skill directories here; new bundled skills belong in `plugins/_skills/skills/`, and plugin-specific skills belong in their owning plugin.
- Keep this pointer short and current; move any detailed guidance to the owning plugin DOX.

## Work Guidance

- Update this file only when the bundled collection location or its owning plugin changes again.
- Keep skill authoring, placement, and verification rules in `plugins/_skills/skills/AGENTS.md`.

## Verification

- Confirm no `SKILL.md` exists under this directory and that skill runtime tests still resolve bundled skills from the plugin root.

## Child DOX Index

No child DOX files.
