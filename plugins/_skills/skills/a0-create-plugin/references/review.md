# Review A Plugin

Sources: `/a0/plugins/AGENTS.md`, `/a0/helpers/plugins.py`, `/a0/helpers/tool.py`, `/a0/helpers/api.py`, and the relevant plugin/UI contracts. Use `implementation.md` and `webui.md` for examples; verify current source when they disagree.

Scale review to the change and requested risk. For a full audit, cover each group below and report PASS/WARN/FAIL with file/line evidence. For a small fix, verify its behavior and affected contracts without inventing unrelated work.

## Manifest And Structure

- Parse `plugin.yaml`; verify title, description, version, settings sections and scope flags. New community names must match the eventual Index folder and use lowercase letters, digits and underscores without a leading underscore.
- Check custom runtime placement under `usr/plugins/`, or the standalone repository root for packaging. Bundled plugins are a separate, explicitly requested scope.
- Check actual extension discovery: `extensions/python/<point>/`, `extensions/python/_functions/<module>/<qualname>/<start|end>/`, and `extensions/webui/<point>/`. Preserve every module and nested class/function segment in implicit hooks.
- Inspect the API/tool/helper/prompt/skill/assets/config files the plugin uses. Do not reject legitimate extra files, supported manifest fields, or a plugin without a UI just because a checklist omits them.
- A root LICENSE is optional for local-only use but required for community contribution; README should explain setup, dependencies, behavior and cleanup.

## Code And Configuration

- For channel integrations, use [Channel Commands](channel-commands.md) to verify enabled-context discovery, custom precedence, authorization before resolution, effect handling, and a tested once-only handoff into the agent.

- Use `AgentContext` and `UserMessage` from `agent`, API handlers from `helpers.api`, and `Tool`/`Response` from `helpers.tool`.
- User-plugin imports use `usr.plugins.<name>...`; no `sys.path` hacks or symlink-dependent imports.
- Read effective settings through `get_plugin_config`; save only intended scope/fields and preserve unowned settings. Caller metadata is not authorization.
- Keep configurable tool guidance policy-filtered. Validate complete JSON examples and exact tool IDs/args.
- Gate store-dependent Alpine content, use separate `createStore` modules, bind settings to `config.*`, and use framework notifications. Verify real breakpoint names and existing geometry.
- **FAIL** if setup, dependency installation/removal, required initialization, update migrations, or uninstall cleanup uses `execute.py` or requires a manual Execute/post-install step. Require `hooks.py:install()` and `hooks.py:uninstall()` for the applicable operations, with `pre_update()` when needed. Verify reruns, failure cleanup, and the actual target interpreter; task-runtime dependencies do not prove framework readiness.
- For custom message handlers, verify the `get_process_step_types` hook registers every custom type rendered with `drawProcessStep`, the original handler argument is passed as `log`, and the result includes `element`. Test live/replayed records followed by hidden utilities and histories longer than 50 steps; standalone handlers must remain undeclared.
- Track plugin-owned side effects and cleanup. Removing a plugin must not remove shared packages/services needed by other features.

## Security And Reliability

- No credentials or private runtime files in source, logs, artifacts or screenshots.
- Preserve authentication/CSRF and enforce authorization at entry points. Validate untrusted input, file paths, archives, subprocess arguments and network destinations as appropriate.
- Identify code execution, external communication, access to secrets, obfuscation, and instructions that attempt to override the agent/user. Evaluate reachability and actual impact rather than flagging every network call as malicious.
- Handle failure without corrupting data. Check resource cleanup, concurrent access, retry behavior and reruns when relevant.
- A security scan can supplement review; it is not a guarantee of safety. `a0-manage-plugin` documents the scanner API.

## Runtime And Contribution Readiness

1. Prove source matches the named runtime. Compile/import with the framework interpreter and run relevant tests.
2. Exercise the changed tool/API/UI path with representative inputs; verify effective scope, output and failure behavior. Tests alone do not prove a live UI feature.
3. Remove only test artifacts you created. Report checks not run and dependencies that prevented verification.
4. For community publication, check current Index names and repository URLs for duplicates using `a0-manage-plugin`'s discovery reference. Related purpose is overlap to explain, not automatic rejection.
5. Resolve blocking defects and publication requirements before following `contribute.md`. Local-only work does not need a public repository or Index PR.

Return findings with severity, evidence, impact and the smallest useful fix. Distinguish local usability from community readiness. Do not claim passed checks that were only inferred.
