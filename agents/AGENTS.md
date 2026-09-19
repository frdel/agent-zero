# Agent Profiles DOX

## Purpose

- Own bundled agent profiles, profile-specific prompts, and profile-local tools.
- Keep profile behavior understandable without requiring edits to core framework prompts.

## Ownership

- Each direct profile directory owns its `agent.yaml`, optional `prompts/`, optional `tools/`, and optional `extensions/`.
- `_example/` demonstrates profile layout, is not selectable, and should stay
  suitable as a reference.
- Specialist profiles (developer, hacker, researcher, tiny-local) live in the
  `_agent_profiles` plugin; this directory keeps `agent0`, `default`, and `_example`.
- User-created local profiles belong under `usr/agents/`, not here, unless they are intended to ship with the product.

## Local Contracts

- `agent.yaml` is the profile entry point and must stay valid YAML.
- Profile prompt overrides should be narrow and named to match the core prompt they extend or replace.
- Profile main prompts must not advertise configurable capabilities; put such
  guidance in policy-filtered profile tool prompts.
- Profile-local tools must follow the same `Tool` contract as root `tools/`.
- Do not put secrets, provider API keys, local paths, or user-specific settings in bundled profiles.

## Work Guidance

- Prefer small profile-specific prompt files over duplicating large core prompts.
- Keep examples generic and runnable in a clean checkout.
- When changing profile behavior, check how the WebUI profile picker and backend profile loader discover profiles.

## Verification

- Run `pytest` or targeted tests covering profile loading when changing `agent.yaml` structure or profile discovery.
- Manually inspect YAML validity for changed profiles if no targeted test exists.

## Child DOX Index

Direct child DOX files:

| Child | Scope |
| --- | --- |
| [_example/AGENTS.md](_example/AGENTS.md) | Reference profile demonstrating profile-local prompts, tools, and extensions. |
| [agent0/AGENTS.md](agent0/AGENTS.md) | Main user-facing Agent Zero profile metadata. |
| [default/AGENTS.md](default/AGENTS.md) | Base profile metadata and inherited prompt specifics. |
| [developer/AGENTS.md](developer/AGENTS.md) | Software development specialist profile. |
| [hacker/AGENTS.md](hacker/AGENTS.md) | Cyber security and penetration testing specialist profile. |
| [researcher/AGENTS.md](researcher/AGENTS.md) | Research, data analysis, and reporting specialist profile. |
| [tiny-local/AGENTS.md](tiny-local/AGENTS.md) | Small/local model profile with an action-first communication prompt. |
