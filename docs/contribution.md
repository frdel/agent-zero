# Contributing to Agent Zero

Contributions to improve Agent Zero are very welcome!  This guide outlines how to contribute code, documentation, or other improvements.

## Getting Started

1. **Fork the Repository:** Fork the Agent Zero repository on GitHub.
2. **Clone Your Fork:** Clone your forked repository to your local machine.
3. **Create a Branch:** Create a new branch for your changes. Use a descriptive name that reflects the purpose of your contribution (e.g., `fix-memory-leak`, `add-search-tool`, `improve-docs`).
    *   **Set up your Development Environment:** If you plan to contribute code, ensure you have a full development environment set up. Follow the [In-Depth Guide for Full Binaries Installation](./installation.md#in-depth-guide-for-full-binaries-installation).

## Making Changes

*   **Code Style:** Aim to follow existing code style. Agent Zero generally adheres to PEP 8 conventions. If you use an IDE, configuring it to highlight PEP 8 issues is recommended.
* **Documentation:**  Update the documentation if your changes affect user-facing functionality. The documentation is written in Markdown.
* **Commit Messages:**  Write clear and concise commit messages that explain the purpose of your changes.
### Testing
- If your contribution involves code changes (new features or bug fixes), please test your changes thoroughly.
- If you are adding a new feature, consider adding tests for it if a testing framework is in place. (Currently, we are working on expanding our test coverage.)
- Ensure existing tests pass with your changes. (Details on running tests will be added here as the test suite evolves.)

## Submitting a Pull Request

1. **Push Your Branch:** Push your branch to your forked repository on GitHub.
2. **Create a Pull Request:** Create a pull request from your branch to the appropriate branch in the main Agent Zero repository.
   * Target the `development` branch.
    *   The project maintainers will review your PR. Please be responsive to any feedback or questions to help expedite the process.
    *   If your PR addresses a specific GitHub issue, please mention the issue number in your PR description (e.g., 'Fixes #123').
3. **Provide Details:** In your pull request description, clearly explain the purpose and scope of your changes. Include relevant context, test results, and any other information that might be helpful for reviewers.
4. **Address Feedback:**  Be responsive to feedback from the community. We love changes, but we also love to discuss them!

## Reporting Bugs or Suggesting Features

The easiest way to contribute is by reporting bugs or suggesting new features!

-   **Check Existing Issues:** Before submitting, please check the [GitHub Issues](https://github.com/frdel/agent-zero/issues) to see if your bug or feature request has already been reported.
-   **Bug Reports:** If you're reporting a bug, please include:
    -   Clear steps to reproduce the issue.
    -   What you expected to happen.
    -   What actually happened.
    -   Your Agent Zero version and relevant environment details (OS, Docker version, Python version if applicable).
-   **Feature Requests:** If you're suggesting a feature, please describe:
    -   The proposed feature clearly.
    -   The problem it solves or the value it adds.
    -   Any potential implementation ideas (optional).

## Documentation Contributions

Our documentation is written in Markdown. We highly value contributions that improve clarity, add examples, or correct information. If you're new to Markdown, it's a simple and powerful way to write formatted text, and many great tutorials are available online. Your efforts to make the documentation better for all users are greatly appreciated!