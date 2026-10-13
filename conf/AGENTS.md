# Configuration Defaults DOX

## Purpose

- Own repository-shipped configuration defaults and templates.
- Keep clean-checkout defaults safe, portable, and free of user-specific state.

## Ownership

- `model_providers.yaml` defines built-in provider metadata and LiteLLM wiring defaults.
- `*.default.gitignore` files define templates copied or used for generated user/project/workdir directories.
- Runtime user settings belong under ignored `usr/` local state and are not documented with local DOX files.

## Local Contracts

- Do not commit API keys, provider secrets, local account identifiers, or private endpoints.
- Keep provider IDs and settings keys stable unless all loaders, UI references, migrations, and tests are updated.
- Defaults must work in a clean checkout and in Docker.
- Chat Completions is the transport default; providers intentionally using Responses must set `a0_api_mode: responses` explicitly.
- Local provider defaults omit `api_key`: LiteLLM handles unauthenticated endpoints, while saved or explicit keys remain available for authenticated servers. Static dummy keys would override saved keys. OAuth compatibility keys belong to the OAuth plugin's connected-account hook.
- Prefer native LiteLLM routes for shipped providers; keep endpoint overrides for Nebius Token Factory and Z.AI Coding. Model-list `default_base` is independent of LiteLLM's inference defaults.
- Venice chat uses `veniceai` with `venice_parameters` in `extra_body`; Venice embeddings and the Agent Zero proxy retain their OpenAI-compatible routes. OpenRouter embeddings use the native route and retain Agent Zero attribution headers.
- Venice and Agent Zero API chat defaults select `a0_prompt_cache_mode: prompt_cache_key` for cache routing. Explicit model kwargs may override the mode; embeddings must not inherit it.
- Templates must avoid accidentally unignoring private runtime content.

## Work Guidance

- Prefer adding provider metadata here only when it is broadly useful to shipped Agent Zero.
- Keep comments concise and operational.
- Coordinate provider changes with model settings UI, plugin model overrides, and docs.

## Verification

- Run targeted model/provider tests after changing `model_providers.yaml`.
- Check generated ignore templates manually when changing `*.default.gitignore`.

## Child DOX Index

No child DOX files.
