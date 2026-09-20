# Development Skill DOX

## Purpose

- Own the broad Agent Zero development guide used by agents extending the framework.
- Route user-requested application operations through existing HTTP APIs with explicit target IDs and verified results.
- Keep architecture, tools, extensions, API, agents, prompts, projects, plugins, runtime, and skills guidance in sync with the repository.

## Ownership

- `SKILL.md` owns the concise development entry point, routing workflow, path conventions, and reference map.
- `references/` owns detailed source-grounded development references loaded on demand.

## Local Contracts

- Keep paths and examples current with source files and DOX contracts.
- Route plugin authoring/review/contribution to `a0-create-plugin` and discovery/lifecycle operations to `a0-manage-plugin`.
- Do not duplicate long contracts that belong in narrower AGENTS.md files when a reference is enough.
- Reference files must identify current source or DOX anchors and avoid hardcoded default WebUI ports.

## Work Guidance

- Update this skill after durable framework workflow, extension, tool, API, prompt, or profile changes.
- Keep examples operational and compatible with the current helper classes.
- Keep `SKILL.md` lean; move detailed schemas, examples, and topic-specific guidance to `references/`.

## Verification

- Manually read `SKILL.md` and changed reference files for stale architecture references, broken relative paths, and specialist-skill duplication.
- Load the skill after reference-map changes and confirm `skills_tool` exposes the expected reference file tree.

## Child DOX Index

Direct child DOX files:

| Child | Scope |
| --- | --- |
| [references/AGENTS.md](references/AGENTS.md) | Source-grounded development references loaded by this skill. |
