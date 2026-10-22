# Documentation DOX

## Purpose

- Own human-facing documentation, screenshots, setup guides, developer guides, and documentation assets.
- Keep docs accurate to current source behavior and practical user workflows.

## Ownership

- `README.md`, `quickstart.md`, `guides/`, and `setup/` cover user-facing setup and workflows.
- `guides/local-folders.md` owns Docker bind-mount examples and persistence guidance; `guides/launcher.md#workspace-storage` owns Launcher storage choices and folder mappings.
- `developer/` covers compact developer references and source handoffs.
- `plans/` covers implementation plans, migration notes, and staged technical roadmaps.
- `res/` contains documentation images and other documentation assets.

## Local Contracts

- Prefer local docs for practical workflows and direct users to DeepWiki for source-linked internals when appropriate.
- Do not document secrets, private deployment details, unreleased credentials, or user-specific runtime state.
- Screenshots and assets must be relevant to the documented UI state and should be updated when UI changes make them misleading.
- Keep links relative inside the docs tree unless they intentionally point to external community or reference resources.

## Work Guidance

- Update docs in the same change when user-visible behavior, setup steps, settings names, plugin workflows, or UI labels change.
- Keep user guides task-oriented and avoid duplicating architecture contracts already owned by source-adjacent DOX files.
- When editing screenshots or binary assets, avoid unrelated metadata churn.

## Verification

- Check changed internal links manually or with an available link checker.
- For setup or Docker docs, verify commands against current scripts and Docker files.

## Child DOX Index

No child DOX files.
