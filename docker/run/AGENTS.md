# Docker Runtime Image DOX

## Purpose

- Own the runnable Agent Zero image context and local compose example.
- Install Agent Zero from a selected branch onto the base image and prepare runtime entrypoints.

## Ownership

- `Dockerfile` owns branch-based image assembly, exposed ports, and container startup command.
- `docker-compose.yml` owns the local compose service example.
- `build.txt` owns maintainer build and push command notes.
- `fs/exe/` owns runtime entrypoint, supervisor, self-update, Node eval, and service scripts.
- `fs/ins/` owns preinstall, installation, virtualenv, Playwright, SSH, and postinstall scripts.
- Files under `fs/` are copied to container root during the runtime build.

## Local Contracts

- `BRANCH` is required for branch-based Docker builds.
- Preserve exposed ports for SSH, HTTP, and tunneled services unless docs and workflows are updated together.
- Keep the two-runtime Python model aligned with the root contract.
- Retain the Python 3.13-compatible ATK, LibreOffice/UNO, and Xpra pins in `fs/ins/install_additional.sh`. Resolve them from the signed Debian `forky` archive dated `20260624T000000Z` and Xpra `trixie`, using build-scoped APT options that preserve normal Kali sources. Refresh Xpra through `plugins/_desktop/helpers/refresh_xpra_index.sh` from the cloned repository; its signed compressed index avoids upstream's empty ARM64 `Packages` metadata without clearing the Debian indexes.
- Do not bake secrets, local `.env` values, or user data into the image.
- Runtime startup must ensure `/a0/usr/uploads` exists before supervised services start.
- Runtime startup seeds APT package lists in the background only when no package index is cached (fresh images clear these at build time). Normal restarts skip the refresh; installation scripts and plugin hooks refresh metadata when installing packages.
- Runtime startup raises the soft open-file limit toward `A0_NOFILE_LIMIT` (default `65535`) before supervisord starts, bounded by the container hard limit.
- Self-update user-data backups skip Time Travel shadow history under `usr/.time_travel/` and transient Desktop agent state.
- Self-update rollback stashes use immutable Git object IDs for creation checks and restoration; resolve the matching reflog selector only when dropping that stash, preserving unrelated entries. Failed restoration retains the stash.
- Self-update waits up to 180 seconds for the updated or restored WebUI health check by default; `A0_SELF_UPDATE_HEALTH_TIMEOUT_SECONDS` may override it.
- Successful or already-current self-updates refresh an installed Codex CLI with npm on a best-effort basis; missing CLIs and registry failures must not block Agent Zero startup.

## Work Guidance

- Keep startup scripts explicit about framework runtime versus execution runtime.
- Coordinate tag, branch, and publishing changes with GitHub workflow automation.

## Verification

- Build `docker/run` when changing Dockerfile or install scripts.
- Smoke-test container startup after entrypoint, supervisor, port, or compose changes.

## Child DOX Index

No child DOX files.
