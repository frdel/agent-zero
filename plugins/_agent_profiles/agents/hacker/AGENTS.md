# Hacker Agent Profile DOX

## Purpose

- Own the bundled cyber security and penetration testing specialist profile.
- Keep security-audit behavior scoped to this profile instead of default agent behavior.

## Ownership

- `agent.yaml` owns title, description, and delegation context for security work.
- `prompts/` owns security-specific prompt overrides when present.

## Local Contracts

- Keep the profile focused on authorized security analysis, vulnerability research, and defensive audit tasks.
- Do not add secrets, target-specific credentials, or local environment assumptions.
- Preserve the framework tool-call contract and safety expectations.

## Work Guidance

- Keep security instructions operational and bounded to legitimate testing contexts.
- Coordinate broad safety changes with core prompts and relevant tests.

## Verification

- Manually inspect `agent.yaml` for valid YAML after edits.
- Run prompt/profile tests when changing profile discovery or security prompt behavior.

## Child DOX Index

No child DOX files.
