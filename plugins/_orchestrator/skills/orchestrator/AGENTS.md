# orchestrator Skill - AGENTS.md

## Purpose

- Teach Agent Zero how to delegate work to external terminal/headless coding agents only after the skill is loaded.
- Keep generic orchestration rules in `SKILL.md` and agent-specific command runbooks in `references/`.
- Provide copy-ready command patterns for A0 Headless, Codex CLI, Claude Code, Cursor CLI, Gemini CLI, Grok Build, Hermes Agent, and OpenCode through reference files.

## Ownership

- Owns `SKILL.md`.
- Owns per-agent references under `references/`.
- Does not own adapter status detection, UI state, or installation APIs.

## Local Contracts

- Front matter must allow `code_execution_tool`, `code_execution_remote`, and `memory`.
- The body must explicitly state that no `terminal_agent` tool exists.
- The setup flow must ask or recall host-vs-container preference for each coding agent before running non-A0 adapters.
- The host flow must use A0 CLI `code_execution_remote`; the container flow must check install, install only the requested CLI if missing, probe version/help, run a smoke prompt, handle auth/setup with the user, then retry before the real task.
- Agent-specific commands, auth quirks, install hints, and smoke prompts belong in the matching `references/<agent>.md` file.
- `SKILL.md` must tell agents to read only the relevant reference file before acting.
- Claude Code reference guidance must avoid plain `claude` and bare `claude auth login` until the user chooses `--claudeai`, `--console`, `--sso`, or external API-key auth.
- Claude Code API-key auth must source Agent Zero secrets from `/a0/usr/.env`, not from the workdir.
- Gemini CLI container runs must use `§§secret(GEMINI_API_KEY)` when that key is in Agent Zero secrets; do not assume it is exported from `/a0/usr/.env`.
- If a full-screen Claude Code TUI is already open, the Claude reference must reset the terminal session instead of sending Enter or `/login`.
- Root shells must not use Claude Code `bypassPermissions`; non-root shells may use it as the default non-interactive mode.
- Long-running commands should stay in a shell session and be polled there.
- Computer Use must not be used to drive coding-agent terminals or TUIs.

## Work Guidance

- Put exact commands in fenced bash blocks when the agent needs to execute them.
- State boundaries in imperative language so Agent Zero follows them during chat.
- Keep expected smoke responses deterministic.
- Keep `SKILL.md` short; put growing per-agent details in references.

## Verification

- Run:
  ```bash
  docker exec 8dc967046cda bash -lc 'cd /a0 && /opt/venv-a0/bin/python plugins/_orchestrator/tests/test_status_adapters.py'
  ```

## Child DOX Index

| Child | Scope |
| --- | --- |
| [references/AGENTS.md](references/AGENTS.md) | Per-agent command, setup, auth, smoke, and real-task runbooks. |
