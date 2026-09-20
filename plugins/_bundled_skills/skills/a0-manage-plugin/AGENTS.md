# Plugin Management Skill DOX

## Purpose

- Own the workflow for browsing, scanning, installing, updating, enabling, disabling, and uninstalling Agent Zero plugins.

## Ownership

- `SKILL.md` owns discovery/lifecycle routing and authorization boundaries.
- `references/` owns current Index search, candidate assessment, and management API procedures.

## Local Contracts

- Keep Plugin Hub URLs, install API behavior, scan expectations, and activation semantics current.
- Distinguish Index discovery from model-based security scans and installation; metadata is not verified capability or safety.
- Handle missing/null Index fields and check installed status separately from scoped activation.
- Warn about third-party plugin execution risk before install workflows.
- Do not recommend unmanaged deletion outside plugin-owned paths.
- Install/update/remove APIs invoke `hooks.py` lifecycle functions; never recommend `execute.py` or manual setup/uninstall commands as a substitute. Route missing lifecycle implementation to `a0-create-plugin`.

## Work Guidance

- Update this skill when installer, scanner, validator, Plugin Index, or toggle behavior changes.
- Keep diagnostics and install examples consistent with plugin helper APIs.

## Verification

- Manually read `SKILL.md` for stale endpoints, paths, and security guidance.

## Child DOX Index

| Child | Scope |
| --- | --- |
| [references/AGENTS.md](references/AGENTS.md) | Index discovery and plugin lifecycle APIs. |
