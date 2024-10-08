# Contributing to Agent Zero

We welcome contributions from the community to improve Agent Zero!  This guide outlines how to contribute code, documentation, or other improvements.

## Getting Started

1. **Fork the Repository:** Fork the Agent Zero repository on GitHub.
2. **Clone Your Fork:** Clone your forked repository to your local machine.
3. **Create a Branch:** Create a new branch for your changes. Use a descriptive name that reflects the purpose of your contribution (e.g., `fix-memory-leak`, `add-search-tool`, `improve-docs`).

## Making Changes

* **Code Style:** Follow the existing code style.  Agent Zero generally follows PEP 8 conventions.  Use a linter (e.g., `flake8`, `pylint`) to ensure consistency.
* **Testing:** Write unit tests for new features or bug fixes.  Agent Zero uses the `pytest` framework. Ensure your changes pass all existing and new tests.
* **Documentation:**  Update the documentation if your changes affect user-facing functionality.  The documentation is written in Markdown and uses MkDocs.  See the *Building the Documentation Locally* section below.
* **Commit Messages:**  Write clear and concise commit messages that explain the purpose of your changes.

## Submitting a Pull Request

1. **Push Your Branch:** Push your branch to your forked repository on GitHub.
2. **Create a Pull Request:** Create a pull request from your branch to the appropriate branch in the main Agent Zero repository.
   * **For new features, refactoring, or significant changes:** Target the `testing` branch.
   * **For bug fixes, patches, or small improvements:** Target the `development` branch.
3. **Provide Details:** In your pull request description, clearly explain the purpose and scope of your changes. Include relevant context, test results, and any other information that might be helpful for reviewers.
4. **Address Feedback:**  Be responsive to feedback from the community. We love changes, but we also love to discuss them!

## Building the Documentation Locally

If your contribution involves changes to the documentation:

1. **Install Requirements (if you haven't already):** 
    ```bash
    pip install mkdocs-material
    ```
2. **Start the Development Server:** Navigate to the documentation directory in your terminal (`docs`) and run:

   ```bash
   mkdocs serve
   ```

   This will start a local server, and you can preview the documentation in your web browser at the provided address (usually `http://127.0.0.1:8000`).

3. **Build the Documentation:** To build a static HTML version of the documentation:

   ```bash
   mkdocs build
   ```

## Communication

* **Join the Community:** Join the Agent Zero community (INSERT LINKS HERE) to discuss ideas, ask questions, and collaborate with other contributors.
* **Report Issues:** Use the GitHub issue tracker to report bugs or suggest new features.

## Documentation Stack

The documentation is built using [MkDocs](https://www.mkdocs.org/) with the [Material theme](https://squidfunk.github.io/mkdocs-material/).  Familiarity with Markdown and MkDocs is helpful but not strictly required for contributing documentation updates.

We appreciate your contributions and look forward to improving Agent Zero for everyone's benefit!