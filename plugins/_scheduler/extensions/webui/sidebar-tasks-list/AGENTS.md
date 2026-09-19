# sidebar-tasks-list Extension DOX

## Purpose

- Inject the `_scheduler` plugin tasks section into the sidebar extension point.

## Local Contracts

- The extension point `sidebar-tasks-list` is rendered by the core `left-sidebar.html` inside the `#tasks-section` container; this plugin contributes the only HTML file there.
- The contribution is a thin `x-component` reference to the plugin-owned tasks list under `/plugins/_scheduler/webui/`.

## Verification

- Load the WebUI with the plugin enabled and confirm the Tasks section renders; disable the plugin and confirm the sidebar renders without the section and without console errors.
