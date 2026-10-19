# sidebar-extensions Extension DOX

## Purpose

- Inject the `_scheduler` plugin tasks section into the sidebar extension point.

## Local Contracts

- The extension point `sidebar-extensions` is rendered by the core `left-sidebar.html` inside the `#extensions-section` container; this plugin contributes the tasks list HTML there.
- The contribution is a thin `x-component` reference to the plugin-owned tasks list under `/plugins/_scheduler/webui/`.

## Verification

- Load the WebUI with the plugin enabled and confirm the Tasks section renders without console errors.
- The plugin is `always_enabled`, so it cannot be disabled for an absence check; instead confirm the core `left-sidebar.html` still renders its empty `#extensions-section` container when no plugin contributes to the `sidebar-extensions` point.
