# Startup Migration Extensions DOX

## Purpose

- Own backend startup migrations.

## Ownership

- Ordered Python files in this folder own idempotent migration steps that run during startup.

## Local Contracts

- Migrations must be safe to run repeatedly.
- Preserve user data and create backups or reversible paths when changing durable state.
- Keep long-running work bounded and observable.
- `_05_framework_dependencies.py` applies the LiteLLM/OpenAI pins, PostgreSQL driver, and shared security floors from root `requirements.txt` on Docker startup. Already-current and non-Docker environments skip installation; failures stop startup. Extend its package scope when future core dependency changes need self-update installation.
- After changing framework packages, reuse `helpers.process.restart_process()` before serving requests so imported SDK modules are refreshed. Keep installation within 60 seconds to leave startup time within older self-updaters' health-check window; Git rollback does not restore Python packages.
- `_10_self_update_manager.py` may replace `/exe/self_update_manager.py` from the repository copy when the installed runtime updater is stale; it must validate required safety markers and keep a backup before replacement.
- Required updater capabilities include immutable rollback-stash identity (`get_top_stash_oid`), so runtimes using moving stash selectors are upgraded on startup.
- After synchronizing a stale self-update manager, `_10_self_update_manager.py` starts that manager's best-effort Codex CLI refresh in the background so the update that introduces the hook does not need a second restart.

## Work Guidance

- Add migrations only for durable state changes that cannot be handled lazily elsewhere.

## Verification

- Smoke-test startup on a clean checkout and on representative existing user state when practical.

## Child DOX Index

No child DOX files.
