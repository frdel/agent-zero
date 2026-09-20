# Sharing and Safety Guide

This guide helps contributors decide **what to share**, **where to share it**, and **what must stay private**.

## Start with the decision tree

### 1. Is this change meant for the Agent Zero core repository?

Use the main `agent-zero` contribution flow when the change directly improves the framework itself, for example:

- a bugfix in `webui/`, `helpers/`, `api/`, `tools/`, `extensions/`, or `docs/`
- a test that belongs with core framework behavior
- documentation for built-in functionality

If yes:

1. Fork `agent0ai/agent-zero` publicly.
2. Add `upstream` to your local clone.
3. Sync from `upstream/main` (or the currently used upstream target branch).
4. Create a focused branch.
5. Open the PR across forks.

See [`../guides/contribution.md`](../guides/contribution.md) for the detailed workflow.

### 2. Is this a community plugin?

Use a **dedicated public plugin repository** when the work is a standalone plugin that users can install independently.

Typical signals:

- it lives cleanly under `usr/plugins/<plugin_name>/`
- it has its own `plugin.yaml`
- it can evolve independently from the core repository
- it should be discoverable in the Plugin Hub

If yes:

1. Put the plugin contents at the root of its own repository.
2. Include `plugin.yaml`, `README.md`, and `LICENSE`.
3. Test it locally from `usr/plugins/`.
4. Submit its `index.yaml` entry to `agent0ai/a0-plugins`.

See [`agent0ai/a0-plugins`](https://github.com/agent0ai/a0-plugins) for the
current Plugin Index rules and packaging details.

### 3. Is this a reusable skill?

Use the **skills workflow** when the work is mainly procedural knowledge in `SKILL.md` form.

Typical signals:

- it teaches the agent how to perform a task
- it is portable across Agent Zero, Cursor, Claude Code, or Copilot-style ecosystems
- it lives naturally under `usr/skills/` during development

If yes:

1. Develop it locally in `usr/skills/`.
2. Validate the structure and examples.
3. Move it into `plugins/_bundled_skills/skills/` for an Agent Zero contribution, or publish it in a dedicated public repository/collection.

See [`contributing-skills.md`](contributing-skills.md) for the authoring standard.

### 4. Should this stay private?

Keep the work **out of public forks and upstream PRs** when it includes any of the following:

- credentials, tokens, API keys, `.env` files, or customer secrets
- local-only experiments, snapshots, or temporary branch archaeology
- customer-specific logic or data
- machine-specific configuration, caches, local virtual environments, or editor debris
- plugin or skill prototypes that are not ready for public review

If yes, keep it in a private repository, in `usr/`, or outside the public contribution path entirely.

## Safe publication rules

### Public forks and pull requests

- Use a **public, pushable fork** for any branch that may become the head branch of an upstream PR.
- Keep the source branch alive until the PR is merged or intentionally closed.
- Search open and recently closed upstream PRs before opening a new one.
- Choose the base branch from current upstream practice; do not hardcode `development` if active comparable PRs target `main`.
- Record the exact tests you ran.

### Allow edits from maintainers

GitHub lets you allow maintainers to edit a branch on your fork.

If the fork branch contains GitHub Actions workflows, GitHub may show **"Allow edits and access to secrets by maintainers"**. Treat this carefully:

- only enable it when you are comfortable with maintainers editing workflow files on that branch
- do not leave sensitive values or private automation in a fork branch you plan to share publicly

### Files that usually do not belong in public contributions

- `.env`
- `.venv/`
- editor settings such as `.vscode/settings.json`
- temporary notes, scratch files, or machine-specific backups
- unrelated formatting churn
- private reports or internal strategy docs

## Recommended repository model

For teams or maintainers juggling both private R&D and public contributions, this split keeps things sane:

1. **Private workspace or backup repository**
   - plugin experiments
   - customer-specific work
   - snapshots and branch archaeology
   - internal notes and strategy

2. **Clean fix-only clone for upstream-facing work**
   - only branches that may become public PRs
   - synced from upstream
   - no snapshots, no unrelated experiments

3. **Public fork used only for PR head branches**
   - only focused, reviewable public branches
   - no internal scratch branches

## Before you publish anything

- Confirm the work belongs in the chosen publication path.
- Remove secrets and local-only artifacts.
- Check for overlapping upstream work.
- Make sure the diff is narrow and reviewer-friendly.
- Verify the test evidence you plan to mention.
- Make sure the branch source is public if it will back an upstream PR.
