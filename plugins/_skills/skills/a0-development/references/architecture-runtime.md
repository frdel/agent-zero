# Architecture And Runtime

## Source Anchors

- Root contract: `/a0/AGENTS.md`
- WebUI entry point: `/a0/run_ui.py`
- Runtime arguments and WebUI port resolution: `/a0/helpers/runtime.py`
- Docker Python runtimes: `/a0/docker/base/fs/ins/install_python.sh`
- Docker framework activation: `/a0/docker/run/fs/ins/setup_venv.sh`
- Docker UI launch manager: `/a0/docker/run/fs/exe/self_update_manager.py`
- Search/discovery roots: `/a0/helpers/subagents.py`, `/a0/helpers/skills.py`, `/a0/helpers/projects.py`

## Runtime Split

Agent Zero has two Docker Python runtimes:

| Runtime | Python | Purpose |
|---|---|---|
| `/opt/venv-a0` | 3.12.4 | Framework runtime. Runs the WebUI backend, API, scheduler, agent loop, framework imports, plugin hooks, and framework-side tools. |
| `/opt/venv` | 3.13 | Agent execution runtime. Use for Python code executed on behalf of the agent or user task dependencies. |

Use `/opt/venv-a0` for framework import checks, WebUI startup checks, API/plugin hook behavior, and `py_compile` of framework code inside Docker. Use `/opt/venv` only when the feature explicitly targets agent/user code execution.

Do not claim a package works in the framework because it imports in `/opt/venv`, and do not claim user-code execution works because it imports in `/opt/venv-a0`.

## Ports And URLs

Do not hardcode a WebUI default port in guidance. Discover the effective URL from:

- WebUI startup output.
- Launcher or Docker published-port mapping.
- Explicit `--host` and `--port` arguments.
- `WEB_UI_HOST` and `WEB_UI_PORT` environment configuration.
- Live container inspection when the task targets a running runtime.

`helpers.runtime.get_web_ui_port()` has a code fallback, and the Docker UI manager passes an internal container port. Those are implementation details, not a stable user-facing URL contract.

## Root Paths

- `/a0/` means the framework root inside the Docker runtime.
- In a local checkout, `/a0/` in documentation maps to the repository root.
- `usr/` contains user state, projects, settings, skills, plugins, chats, and workdirs.
- `tmp/` contains runtime caches and generated working files.
- Do not document ignored `usr/` or `tmp/` changes unless explicitly asked.

When the user names a live Dockerized runtime, the live `/a0` tree is a separate artifact. Verify the file sync or runtime state directly before treating checkout code as live behavior.

## Project Layout

Key root areas:

| Path | Purpose |
|---|---|
| `agent.py` | `Agent`, `AgentContext`, `AgentConfig`, prompt reading, tool loop. |
| `initialize.py` | Framework initialization and background loop startup. |
| `models.py` | Model provider and LiteLLM transport configuration. |
| `run_ui.py` | Flask/Socket.IO ASGI WebUI startup. |
| `api/` | HTTP API handlers and `ws_*.py` WebSocket handlers. |
| `helpers/` | Shared framework utilities and base contracts. |
| `tools/` | Core tool implementations. |
| `extensions/` | Built-in backend and WebUI extension points. |
| `plugins/` | Bundled system plugins. |
| `agents/` | Bundled agent profiles. |
| `prompts/` | Core prompt fragments. |
| `plugins/_skills/skills/` | Bundled skills. |
| `webui/` | Alpine.js frontend shell, components, CSS, assets, and vendor code. |

## Discovery Order

Agent-specific path resolution is handled by `helpers.subagents.get_paths(...)`. In broad terms, project and user/profile paths have higher priority than plugin and bundled defaults, then user root/plugin roots, then base defaults. Inspect `helpers/subagents.py` for exact order before changing discovery behavior.

Skill discovery is handled by `helpers.skills.get_skill_roots(...)`. Skills may come from the bundled `plugins/_skills/skills/` collection, user `usr/skills/`, project metadata, agent profile folders, and other plugin roots. Loaded skills can expose additional files via `skills_tool action=read_file`.

## Development Bias

- Prefer plugins for new capabilities.
- Prefer `helpers/` only for reusable framework behavior.
- Prefer small, source-backed changes over broad rewrites.
- If an example conflicts with source discovery code or DOX, treat the example as stale until verified.
