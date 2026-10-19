# Orchestrator

Load-on-demand guidance for orchestrating external **terminal coding agents**
from Agent Zero without keeping a large delegation tool in every agent prompt.

The plugin provides:

- an `orchestrator` skill that tells Agent Zero how to use external CLIs
  through the user's A0 CLI host bridge or the normal container shell;
- a Settings > External Services status screen for configured binaries and
  detected auth state;
- adapter metadata for Agent Zero headless, OpenAI Codex CLI, Claude Code,
  Cursor CLI, Gemini CLI, Grok Build, Hermes Agent, OpenCode, and future terminal agents.

There is intentionally no `terminal_agent` tool and no settings-screen install
button. When the user explicitly asks for a terminal agent, the skill first
decides whether to use the user's own host CLI through A0 CLI or a pal agent
inside the Agent Zero container.

Host CLI is the primary everyday flow: the user's Claude Code, Codex, Cursor
CLI, and other coding agents stay installed and logged in on their own
computer. Container agents remain useful when the user explicitly wants the
Docker runtime.

## Supported Agents

| Agent | CLI | Login |
| --- | --- | --- |
| Agent Zero (headless) | `a0` | Instance `/login` session; `A0_USERNAME`/`A0_PASSWORD` in the shell for protected hosts |
| OpenAI Codex | `codex` | ChatGPT device login from settings or external CLI login |
| Claude Code | `claude` | External `claude` login or `ANTHROPIC_API_KEY` |
| Cursor CLI | `agent` | `CURSOR_API_KEY`, `NO_OPEN_BROWSER=1 agent login`, or cached Cursor login |
| Gemini CLI | `gemini` | Cached Google login, `GEMINI_API_KEY`, or Vertex AI credentials |
| Grok Build | `grok` | `XAI_API_KEY`, `grok login --device-auth`, or cached Grok login |
| Hermes Agent | `hermes` | External Hermes/provider setup, `~/.hermes/.env`, `~/.hermes/auth.json`, or provider env vars |
| OpenCode | `opencode` | External `opencode auth login`, provider env vars, or `~/.local/share/opencode/auth.json` |

The `a0` adapter targets the local Agent Zero instance
(`http://localhost:80` inside the container) when no `host`/`AGENT_ZERO_HOST`
is configured, or another Agent Zero instance when you set a host. This lets A0
delegate to another runtime, and also lets the same runtime ask itself a focused
question as a secondary use case. A0 is the setup exception: if the user did
not specify a target, Agent Zero should ask whether to use the same instance or
another/spun-up instance instead of running a generic login flow. The skill
tells the target A0 instance to answer directly and not delegate back through
terminal agents.

## Skill Usage

Ask Agent Zero to load/use the `orchestrator` skill before delegating coding
work to one of these CLIs. The skill keeps the global setup loop in
`skills/orchestrator/SKILL.md` and reads one per-agent reference from
`skills/orchestrator/references/` before acting.

If the user does not specify host versus container, Agent Zero asks and saves a
per-agent preference with `memory` action=save. Local/host mode uses the connector's
`code_execution_remote` tool and may load `host-code-execution`; container mode
uses `code_execution_tool`.

For local/host coding agents, the user should run A0 CLI on their own machine:

```bash
# macOS / Linux
curl -LsSf https://cli.agent-zero.ai/install.sh | sh
```

```powershell
# Windows PowerShell
irm https://cli.agent-zero.ai/install.ps1 | iex
```

If A0 CLI is installed but not running, open a terminal and run `a0`, connect it
to the Agent Zero instance, choose the chat/session or enter the remote/VPS URL,
then press `F4` for Remote Code Execution. Press `F3` too when host file writes
are needed. After that, asking Agent Zero to use local Claude Code/Codex/etc.
will run commands on the host machine instead of inside Docker.

The skill must not use Computer Use to drive coding-agent terminals or TUIs.
It uses headless CLI commands. The ACP community plugin can be a separate path
when explicitly requested or when direct CLI automation is unsuitable.

The reference files contain the copy-ready commands, for example Codex:

```bash
cd "$WORKDIR"
codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox "$TASK"
```

Claude Code defaults to skip permissions for non-interactive runs:

```bash
cd "$WORKDIR"
if [ "$(id -u)" -eq 0 ]; then
  claude -p "$TASK" --output-format json
else
  claude -p "$TASK" --output-format json --permission-mode bypassPermissions --allowedTools Bash,Read,Edit
fi
```

When Claude Code is not authenticated, use `claude auth login` for the
human-in-the-loop login step. Do not start plain `claude`; that opens the
first-run TUI and can trap the agent in theme/provider menus.
Ask the user to choose the auth mode first: Claude subscription
(`--claudeai`), Anthropic Console/API billing (`--console`), SSO (`--sso`), or
an externally set `ANTHROPIC_API_KEY`. In Agent Zero, the user can add that
key from **Settings > External Services > Secrets Management**; the runtime
file is `/a0/usr/.env`, not the workdir `.env`.
If a plain `claude` TUI is already open, reset the terminal session instead of
sending Enter or `/login`, then use one of the explicit auth commands.

If a non-A0 CLI is missing or asks for login/browser confirmation, Agent Zero
can install the requested CLI, start its setup/login command, relay the exact
human step, wait for the user to confirm, then retry a smoke prompt before
running the real task. If setup shows provider/menu choices, Agent Zero should
show those options in chat and ask which one to select, not send the user to a
Docker shell just to choose from a menu. It should not ask the user to paste
secrets into chat unless there is no safer path.

## Login And Status

Open **Settings > External Services > Orchestrator** to see registered
adapters, binary paths, installed status, and detected auth source. The screen
can refresh status and disconnect credentials only when an adapter can safely
remove a known credential store.

Codex still supports plugin-owned device-code login from the settings screen.
Those tokens are stored under the plugin data directory (`data/codex/auth.json`,
mode 600), and the skill can point Codex at that home when needed. If you have
already logged in with `codex login`, the status screen detects the external
credentials too.

> Tokens are password-equivalent credentials. Never share one rotating
> refresh-token auth file between two clients; plugin-owned Codex credentials
> stay separate from other tools.

## Configuration (`default_config.yaml`)

```yaml
a0:
  binary: a0          # falls back to /opt/venv/bin/a0 in Agent Zero Docker
  host: ""           # empty = AGENT_ZERO_HOST env, else local instance
codex:
  binary: codex
  model: ""
  bypass_sandbox: true
claude:
  binary: claude
  model: ""
  permission_mode: bypassPermissions
  allowed_tools: "Bash,Read,Edit"
  bare: false
cursor:
  binary: agent
  output_format: text
  force: true
gemini:
  binary: gemini
  model: ""
grok:
  binary: grok
  model: ""
  output_format: json
  always_approve: true
  no_auto_update: true
hermes:
  binary: hermes
  model: ""
  provider: ""
  toolsets: ""
  yolo: true
opencode:
  binary: opencode
  model: ""
  agent: ""
  auto: true
```

## Adding A New Agent

1. Create `helpers/adapters/<name>.py` subclassing `TerminalAgentAdapter`
   (`helpers/adapters/base.py`) and implement `auth_status()`. Add optional
   safe disconnect or device-login support only when the credential store is
   known.
2. Register an instance in `helpers/registry.py`.
3. Add a config block in `default_config.yaml`.
4. Add concise command guidance to
   `skills/orchestrator/references/<name>.md`.
5. Add the reference to `skills/orchestrator/SKILL.md` and update generic
   skill guidance only when the global orchestration loop changes.

The status API and settings UI pick registered adapters up automatically.
