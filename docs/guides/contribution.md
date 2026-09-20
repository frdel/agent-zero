# Contributing to Agent Zero

Contributions to improve Agent Zero are very welcome!  This guide outlines how to contribute code, documentation, or other improvements.

## Getting Started

- See [Development Setup](../setup/dev-setup.md) for a local development environment.
- See [Create a Small Plugin](create-plugin.md) before building a new plugin.
- Use [DeepWiki for Agent Zero](https://deepwiki.com/agent0ai/agent-zero) for architecture and source-linked internals.

1. **Fork the Repository:** Fork the Agent Zero repository on GitHub.
2. **Clone Your Fork:** Clone your forked repository to your local machine.
3. **Create a Branch:** Create a new branch for your changes. Use a descriptive name that reflects the purpose of your contribution (e.g., `fix-memory-leak`, `add-search-tool`, `improve-docs`).

## Making Changes

- **Code Style:** Follow the existing code style. Agent Zero generally follows PEP 8 conventions.
- **Documentation:** Update the documentation if your changes affect user-facing functionality. The documentation is written in Markdown.
- **Commit Messages:** Write clear and concise commit messages that explain the purpose of your changes.

## Submitting a Pull Request

1. **Push Your Branch:** Push your branch to your forked repository on GitHub.
2. **Create a Pull Request:** Create a pull request from your branch to the appropriate branch in the main Agent Zero repository.
   - Search open and recently closed upstream PRs for overlapping work before opening a new one.
   - Target the branch currently used for comparable active upstream contributions or explicit maintainer guidance. Do not assume `development` is always correct.
   - Keep the source branch available on your fork until the pull request is merged or intentionally closed.
3. **Provide Details:** In your pull request description, clearly explain the purpose and scope of your changes. Include relevant context, test results, and any other information that might be helpful for reviewers.
4. **Address Feedback:**  Be responsive to feedback from the community. We love changes, but we also love to discuss them!

## Working With Forks Safely

When contributing from a fork, prefer the standard GitHub flow:

1. **Fork the repository publicly** if the branch may become the head branch of an upstream pull request.
2. **Add an `upstream` remote** that points to `agent0ai/agent-zero`.
3. **Sync your fork regularly** before starting new work so your branch starts from the current upstream target branch.
4. **Create one focused branch per change** (for example, one bugfix, one plugin, or one docs update).
5. **Open the pull request across forks** by explicitly selecting the upstream base repository/branch and your fork/compare branch.

If your fork contains GitHub Actions workflows, be careful with GitHub's "Allow edits and access to secrets by maintainers" option. Only enable it when you are comfortable with maintainers editing workflow files on the fork branch.

## Choosing The Right Publication Path

- **Core bugfixes and docs for Agent Zero itself:** prepare them in a clean fork/clone of `agent-zero` and open a PR back to the upstream repository.
- **Community plugins:** publish the plugin in its own public repository, then submit it to [`agent0ai/a0-plugins`](https://github.com/agent0ai/a0-plugins).
- **Skills:** develop locally in `usr/skills/`, then move stable skills to `plugins/_skills/skills/` for Agent Zero contributions or publish them in a dedicated public repository/collection.
- **Private experiments, credentials, local R&D, or customer-specific assets:** keep them out of public forks and upstream pull requests.

For a contributor-focused decision guide that covers fixes, plugins, skills, and
what should stay private, see [Sharing and Safety](../developer/sharing-and-safety.md).

## Documentation Stack

- Write local docs for practical setup, screenshots, and user workflows.
- Point architecture and deep internals to [DeepWiki](https://deepwiki.com/agent0ai/agent-zero).
- Use GitHub Flavored Markdown when it helps: tables, task lists, callouts, and fenced code blocks.
