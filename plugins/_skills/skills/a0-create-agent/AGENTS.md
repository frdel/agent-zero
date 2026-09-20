# Agent Creation Skill DOX

## Purpose

- Own the workflow for creating Agent Zero agent profiles.
- Keep guidance for user, plugin-distributed, and project-scoped profiles accurate.

## Ownership

- `SKILL.md` owns trigger metadata, intake flow, profile blueprint schema, and file creation guidance.

## Local Contracts

- Default new user profiles to `usr/agents/`, not bundled `agents/`.
- Keep `agent.yaml`, prompt inheritance, tools, and extension guidance synchronized with profile loader behavior.
- Do not encourage storing secrets or provider credentials in profiles.
- Optional profile `_model_config/config.json` files contain only an existing global `model_preset` selection; never generate copied model dictionaries or profile-local preset definitions.

## Work Guidance

- Keep intake lightweight and progressive for user-facing profile creation.
- Update examples when the bundled `_example/` or profile schema changes.

## Verification

- Manually read `SKILL.md` for stale paths and blueprint/schema drift.

## Child DOX Index

No child DOX files.
