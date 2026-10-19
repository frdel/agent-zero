---
name: orchestrator
description: "Delegate to external coding CLIs: A0 headless, Codex, Claude Code and others."
triggers:
  - "terminal agent"
  - "external coding agent"
  - "delegate to codex"
  - "delegate to claude code"
  - "delegate to cursor"
  - "delegate to cursor cli"
  - "delegate to gemini cli"
  - "delegate to grok build"
  - "delegate to a0 headless"
  - "delegate to hermes"
  - "delegate to opencode"
allowed_tools:
  - code_execution_tool
  - code_execution_remote
  - memory
---

# Orchestrator

Use shell/code execution to run external terminal agents. There is no `terminal_agent` tool: this skill exists so these heavy delegation instructions load only when the task needs them.

Prefer the user's own host-machine CLI when that is what they mean. Container-installed agents are the pal scenario: useful and supported, but secondary.

## Rules

- For Codex, Claude Code, Cursor CLI, Gemini CLI, Grok Build, Hermes Agent, and OpenCode, first decide the execution place: the user's local machine through A0 CLI, or the Agent Zero Docker/container shell.
- If the user did not specify local/host versus container, check memory for this coding agent's execution-place preference. If no current preference is known, ask: "Do you want me to use your own local <agent> through A0 CLI, or the <agent> installed inside the Agent Zero container?"
- After the user chooses, save a stable per-agent preference with `memory` action=save, for example: "For orchestrator, the user prefers Claude Code to run on the host machine through A0 CLI by default." If memory tools are unavailable, continue without saving.
- Never use Computer Use to drive coding-agent terminals, menus, or TUIs. Use headless CLI commands through `code_execution_remote` or `code_execution_tool`; if that is not possible, stop and ask.
- ACP may be available as a community plugin, but do not assume it is installed. Mention it only if the user explicitly asks for ACP or the direct CLI path is unsuitable.
- For Codex, Claude Code, Cursor CLI, Gemini CLI, Grok Build, Hermes Agent, and OpenCode, setup is part of the workflow: check whether the CLI is installed, install only the requested CLI if missing, probe its version/help, run a tiny smoke prompt, then run the real task.
- Keep authentication human-in-the-loop. You may start the CLI login/setup command, relay the exact URL, device code, browser step, or prompt to the user, then wait for the user to confirm completion before retrying the smoke prompt.
- Never start a full-screen CLI/TUI as a login fallback. If you accidentally opened one and see welcome, theme, provider, or unreadable menu output, reset the terminal session instead of sending keys into it.
- If login/setup shows a menu or provider choices, show those choices to the user in chat and ask which one to select. Keep the terminal session open, then send the user's selected number/key back to that session.
- Never ask the user to paste secrets into chat unless there is no safer path. Prefer browser/device login, the CLI's own prompt, or an environment variable set outside chat.
- Always choose an explicit working directory for repository work. Prefer the user's project path over Agent Zero's default workdir.
- Optional command defaults may be stored in `/a0/usr/plugins/_orchestrator/config.json`. Read only the adapter block you need, and never print secrets.
- For long-running commands, start the CLI in a shell session and poll that session's output. Do not add your own timeout wrapper around the terminal agent.
- Pass a self-contained task brief: goal, target files or repo path, constraints, verification commands, and expected output.
- After the terminal agent finishes, inspect its output and verify important changes yourself before reporting success.

## Host CLI Flow

Use this when the user wants their own local Claude Code, Codex, Cursor CLI, Gemini CLI, Grok Build, Hermes Agent, or OpenCode.

1. Use `code_execution_remote`, not `code_execution_tool`, because paths, shell, login, and installed CLIs belong to the A0 CLI host machine.
2. If `code_execution_remote` is unavailable or reports no connected CLI / remote execution disabled, tell the user exactly:

```text
To use your local coding agents, open a terminal on your computer and install A0 CLI if needed.

macOS / Linux:
curl -LsSf https://cli.agent-zero.ai/install.sh | sh

Windows PowerShell:
irm https://cli.agent-zero.ai/install.ps1 | iex

If A0 CLI is already installed but not running, open a terminal and run:
a0

Connect it to this Agent Zero instance. Select the chat/session, or type the Agent Zero URL manually if this is a remote/VPS instance. In A0 CLI, press F4 to allow Remote Code Execution. Press F3 too if the task needs host file writes. Then ask me again to use your local <agent>.
```

3. Once remote execution is available, optionally load `host-code-execution` for host-shell safety rules.
4. Read the relevant agent reference file. Run the same install/probe, smoke, auth, and real-task commands with `code_execution_remote`.
5. Keep workdir semantics host-side: `cd` to the host project path, not `/a0/usr/workdir`, unless the user explicitly wants the container workspace.

## Container Pal Flow

Use this when the user chooses the Agent Zero container or explicitly wants a pal agent inside Docker.

For Agent Zero Headless, read `references/a0.md` and follow its target-selection flow instead of the non-A0 setup loop.

For every non-A0 container adapter:

1. Read only the relevant reference file:

```bash
# Use skills_tool action=read_file on the matching file under references/.
```

2. Check install with the reference command.
3. If missing, install only that requested CLI with the command listed in its reference, then run the install check again.
4. Probe `--version` or `--help`.
5. Run the reference smoke prompt.
6. If the smoke prompt reports missing auth, run only the login/setup command named in that reference; do not run the bare CLI as a login fallback. Relay URLs, device codes, prompts, and visible menu choices to the user in chat, then wait. If a prior command left a TUI open, reset the terminal session before continuing.
7. After the user confirms, rerun the smoke prompt. Only then run the real task.

You can consult both host and container agents in one workflow. Keep their shell sessions separate, label which agent/location produced each answer, and compare results before acting.

## Reference Files

- Agent Zero Headless: `references/a0.md`
- Codex CLI: `references/codex.md`
- Claude Code: `references/claude.md`
- Cursor CLI: `references/cursor.md`
- Gemini CLI: `references/gemini.md`
- Grok Build: `references/grok.md`
- Hermes Agent: `references/hermes.md`
- OpenCode: `references/opencode.md`

Keep generic orchestration rules here. Put agent-specific commands, auth quirks, install hints, and smoke prompts in the matching reference file.
