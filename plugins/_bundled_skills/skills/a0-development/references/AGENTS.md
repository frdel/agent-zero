# A0 Development References DOX

## Purpose

- Own focused reference files loaded by the `a0-development` skill on demand.
- Keep detailed framework-development guidance grounded in current source files and nearest DOX contracts.

## Ownership

- `architecture-runtime.md` owns runtime, path, discovery-order, and port-boundary guidance.
- `dox-workflow.md` owns the edit and closeout workflow for DOX-governed changes.
- `tools.md` owns core and plugin tool development contracts.
- `extensions.md` owns backend and frontend extension contracts.
- `api-webui.md` owns HTTP API handler, WebSocket, and WebUI extension development guidance.
- `operate-agent-zero.md` owns authenticated API usage and project, chat, task, and application-operation workflows.
- `agents-prompts-skills-projects.md` owns profiles, prompt fragments, skills, and project metadata guidance.
- `plugins-workflow.md` owns plugin-first placement and handoff guidance.

## Local Contracts

- Every reference file must list source anchors or DOX anchors that can be checked in the repository.
- Prefer pointing to narrower `AGENTS.md` files instead of copying long subtree contracts.
- Keep examples minimal and compatible with the current helper classes.
- Operation examples must distinguish HTTP payloads from agent-tool arguments, identify scope and side effects, and verify returned IDs/state.
- Do not include hardcoded default WebUI ports or environment-specific credentials.

## Work Guidance

- Update the focused reference file when source or DOX changes make its guidance stale.
- If a reference starts duplicating a specialist skill, shorten it and hand off to that skill instead.
- Treat checked-in examples as examples, not authority, when they conflict with current discovery code.

## Verification

- Manually read changed references for broken relative paths, stale source anchors, and duplicated specialist-skill material.
- After changing reference names, load `a0-development` and confirm the file tree exposes the new paths through `skills_tool`.

## Child DOX Index

No child DOX files.
