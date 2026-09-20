# Plugin Creation Skill DOX

## Purpose

- Own the workflow for creating, extending, or modifying Agent Zero plugins.
- Keep full-stack plugin conventions accurate for API, tools, extensions, settings UI, and WebUI integration.

## Ownership

- `SKILL.md` owns authoring intent, local/community intake, the reference map, and brief troubleshooting.
- `references/` owns implementation examples, UI patterns, review checks, and community contribution.

## Local Contracts

- New custom plugins must default to `usr/plugins/`.
- Setup, dependencies, required initialization, and uninstall cleanup belong to plugin-root `hooks.py` lifecycle functions; never recommend `execute.py` for these operations. Keep examples and review checks consistent with this rule.
- Honor an explicit local/community choice; ask once when it is unknown before creating a new plugin.
- Keep review and contribution discoverable through this entrypoint; do not recreate separate router/debug/review/contribution skills.
- Keep plugin manifest, settings, extension layout, Store Gating, and notification guidance synchronized with `plugins/AGENTS.md` and WebUI contracts.
- Do not recommend hardcoding secrets, bypassing auth, or persistent unmanaged side effects.

## Work Guidance

- Update this skill when plugin loader, Plugin Hub, settings modal, extension, or WebUI patterns change.
- Keep code examples short and aligned with current helper APIs.

## Verification

- Manually read `SKILL.md` for stale paths and broken handoffs to related plugin skills.

## Child DOX Index

| Child | Scope |
| --- | --- |
| [references/AGENTS.md](references/AGENTS.md) | On-demand authoring, review, and contribution guides. |
