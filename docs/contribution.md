## Building the Documentation Locally

To build and preview the documentation locally, make sure to have Python installed, and follow these steps:

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

## Contributing

Contributions to the documentation are very welcome! Please see the [Contributing guidelines](docs/contribution.md) for more information.

The documentation is built using [MkDocs](https://www.mkdocs.org/) and the [Material theme](https://squidfunk.github.io/mkdocs-material/).