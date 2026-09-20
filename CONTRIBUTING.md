# Contributing to Agent Zero

This file is the GitHub-visible entry point for contributors.

For the full contribution workflow, start with:

- [`docs/guides/contribution.md`](docs/guides/contribution.md) — fork, sync, branch, validation, and pull-request flow
- [`docs/developer/sharing-and-safety.md`](docs/developer/sharing-and-safety.md) — how to decide whether a change should go upstream, into a plugin repository, into a skills repository, or remain private
- [`docs/developer/plugins.md`](docs/developer/plugins.md) — plugin structure and Plugin Index submission
- [`docs/developer/contributing-skills.md`](docs/developer/contributing-skills.md) — skill authoring and publication

## Quick rules

- Search open and recently closed upstream PRs before opening a new one.
- Use the branch currently adopted by comparable active upstream PRs or explicit maintainer guidance.
- Keep one focused change per PR whenever practical.
- Keep the source branch available on your fork until the PR is merged or intentionally closed.
- Include exact tests run, or clearly explain why validation was blocked.
- Do not include secrets, `.env` files, local virtual environments, or machine-specific artifacts in a PR.

## Choosing the right place to share work

- **Core bugfix or docs for Agent Zero itself:** contribute back to `agent0ai/agent-zero` from a public fork.
- **Community plugin:** publish the plugin in its own public repository, then submit it to `agent0ai/a0-plugins`.
- **Reusable skill:** contribute it to Agent Zero's bundled skills collection under `plugins/_bundled_skills/skills/` or publish it in a dedicated public repository/collection.
- **Private experiment, customer-specific code, local R&D, or sensitive material:** keep it out of public forks and upstream PRs.

If you're unsure, use the decision guide in [`docs/developer/sharing-and-safety.md`](docs/developer/sharing-and-safety.md).
