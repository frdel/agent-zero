# Plugin Lifecycle Operations

Sources: `/a0/plugins/_plugin_installer/api/plugin_install.py`, `/a0/plugins/_plugin_installer/helpers/install.py`, `/a0/api/plugins.py`, `/a0/helpers/plugins.py`, and `/a0/plugins/_plugin_scan/api/plugin_scan_run.py`.

Use the authorized session/CSRF client from `/a0/plugins/_skills/skills/a0-development/references/operate-agent-zero.md`. Discover the live origin; do not assume an internal or published port. The session cookie and `X-CSRF-Token` header are sufficient; do not invent an additional required CSRF cookie. Preserve login and CSRF protections.

## Security Scan

Offer the scan once before installing third-party code, unless the user already chose whether to scan. It executes model-driven analysis and can take several minutes; browsing the Index is a separate operation. Do not claim a scan guarantees safety.

POST `/api/plugins/_plugin_scan/plugin_scan_run` with:

```json
{
  "git_url": "https://github.com/OWNER/REPOSITORY",
  "checks": ["structure", "codeReview", "agentManipulation", "remoteComms", "secrets", "obfuscation"]
}
```

Use a sufficiently long client timeout for this synchronous scan. The current handler returns `ok`, `git_url` and a Markdown `report`; do not assume a separate structured verdict field. Read the report, present its findings, and distinguish a safe-looking result, caution, serious issues, or inconclusive/error. If it reveals a new material risk, resolve that with the user before installation. Respect a prior decision to skip scanning; do not repeatedly offer it or label an unscanned plugin as scanned.

## Install

For Git installation:

```python
result = api("plugins/_plugin_installer/plugin_install", {
    "action": "install_git",
    "git_url": "https://github.com/OWNER/REPOSITORY",
    "plugin_name": "plugin_id",
})
```

Use the actual Index identity; do not overwrite an existing plugin. `git_token` is optional for a private repository; do not log it. A ZIP install uses multipart form fields `action=install_zip` and file field `plugin_file`, not a JSON body.

The framework validates and places the plugin under `usr/plugins/`, runs `hooks.py:install()` for dependency setup and required initialization, and refreshes state. No `execute.py` or manual post-install step should be needed; treat that requirement as a plugin defect and use `a0-create-plugin` to fix it. Re-fetch the Index or plugin list to verify installed identity; inspect effective activation separately. Do not import framework installation helpers into the separate task-code runtime.

## Update

Inspect the installed repository's current commit, configured remote/branch, and local changes. A matching manifest version does not prove it is current. Compare the actual tracking branch or Index commit; remote default-branch HEAD is not automatically the installed branch.

```python
result = api("plugins/_plugin_installer/plugin_install", {
    "action": "update_plugin", "plugin_name": "plugin_id",
})
```

This path runs `hooks.py:pre_update()`, updates the repository, reruns `hooks.py:install()`, and refreshes framework state. On `dirty_tree_conflict`, inspect the reported files and preserve local edits; do not force-reset or uninstall/reinstall to hide the conflict. Verify returned commit/version and behavior. Non-Git installs need an explicitly planned replacement with local configuration/data preserved.

## Configure Or Enable/Disable

`POST /api/plugins` supports `get_config`, `get_default_config`, `save_config`, `get_toggle_status` and `toggle_plugin`. Supply `plugin_name` and the intended `project_name`/`agent_profile` where applicable.

```python
api("plugins", {
    "action": "toggle_plugin", "plugin_name": "plugin_id", "enabled": True,
    "project_name": "", "agent_profile": "",
})
```

Empty scope fields mean global scope. Do not clear scoped overrides unless requested. Preserve unknown configuration fields when saving and keep secrets out of output. `always_enabled` core plugins cannot be disabled. Use API responses and effective scope checks, not only the presence of a toggle file.

## Remove

For a user-requested uninstall of an identified custom plugin:

```python
api("plugins", {"action": "delete_plugin", "plugin_name": "plugin_id"})
```

The standard path runs `hooks.py:uninstall()` to stop owned processes, remove registrations, and clean up plugin-owned dependencies/resources, then removes the custom plugin directory and refreshes state. Never substitute `execute.py` or a manual dependency-removal command; shared dependencies must remain intact. Explain material data loss before acting if it was not clear in the request. Core plugins cannot be uninstalled this way; disabling is separate and may also be restricted. Scoped configuration may remain after uninstall; do not delete it unless requested.

If normal lifecycle operations fail, inspect the error and plugin-owned state. Manual repair requires a concrete recovery plan; raw folder deletion skips hooks and raw toggle writes skip framework refresh. Do not automatically perform them as fallbacks.

## Verify

Check HTTP and body-level success, installed state, requested scope and the actual relevant behavior. Avoid arbitrary restarts of a busy instance. Return the action and evidence, not a claim based only on files being present.
