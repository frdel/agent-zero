# Home

Welcome to the Agent Zero full documentation.
The documentation is built using [MkDocs](https://www.mkdocs.org/) and the [Material theme](https://squidfunk.github.io/mkdocs-material/).

## Project layout

    docker/    # Dockerfiles and related files for building Docker image
    docs/
    instruments/
    knowledge/
    logs/
    memory/
    prompts/
    python/
    tests/
    tmp/
    webui/
    work_dir/

## Building the Documentation Locally

To build and preview the documentation locally, follow these steps:

1. **Install MkDocs:** If you don't have MkDocs installed, run:
   ```bash
   pip install mkdocs-material
   ```

2. **Start the Development Server:** Navigate to the root of this repository in your terminal and run:
   ```bash
   mkdocs serve
   ```
   This will start a local development server, and you can view the documentation in your web browser at the address it provides (usually `http://127.0.0.1:8000`).  The preview will automatically update as you make changes to the documentation source files.

3. **Build the Documentation:** To generate a static HTML version of the documentation, use:
   ```bash
   mkdocs build
   ```
   This will create a `site` directory containing the HTML files.

## Live Documentation

The live documentation is published via GitHub Pages and can be found at: [https://3clyp50.github.io/agent-zero/].

## Contributing

Contributions to the documentation are very welcome! Please see the [Contributing guidelines](docs/contribution.md) for more information.