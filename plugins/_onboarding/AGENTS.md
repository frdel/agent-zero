# Onboarding Plugin DOX

## Purpose

- Own the built-in first-time onboarding wizard for model configuration.

## Ownership

- `plugin.yaml` owns metadata and always-enabled status.
- `webui/` owns onboarding providers, wizard store, modal/page markup, and thumbnail.

## Local Contracts

- Keep onboarding provider choices synchronized with model configuration and provider metadata.
- OpenCode Go is the `opencode` cloud choice, with setup at `https://opencode.ai/auth` and default chat and utility model `glm-5.3-flash`.
- Do not ask for or expose API keys outside approved settings/API flows.
- Avoid blocking already-configured users with unnecessary onboarding prompts.
- Completion updates the selected global model preset (normally immutable-name `Default`); advanced setup opens that preset in the shared editor.

## Work Guidance

- Coordinate provider changes with `_model_config` and `_oauth` when account-backed providers are involved.

## Verification

- Smoke-test first-run onboarding, provider selection, completion, and skip/close behavior after changes.

## Child DOX Index

No child DOX files.
