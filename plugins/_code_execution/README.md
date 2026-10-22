# Code Execution

Run terminal commands and execute Python or Node.js code through Agent Zero using persistent shell sessions.

## What It Does

This plugin provides the code execution tool used by agents for development tasks. It supports:

- **Terminal commands** in interactive shell sessions
- **Python execution** through `ipython -c`
- **Node.js execution** through `node /exe/node_eval.js`
- **Persistent sessions** keyed by session number
- **Session reset and output retrieval**
- **Local or SSH-backed execution** depending on plugin configuration

## Main Behavior

- **Persistent shells**
  - Maintains per-session shell state in agent data so subsequent calls can reuse the same terminal session.
  - Groups multi-line terminal input in the current shell so only the final prompt marks the command complete.
- **Multiple runtimes**
  - Dispatches requests based on `runtime`: `terminal`, `python`, `nodejs`, `output`, or `reset`.
- **Remote execution support**
  - Can open SSH interactive sessions instead of local shells when configured.
- **Streaming output**
  - Continuously reads shell output, updates the current log item, and detects progress while commands are running.
  - Detects local shell exit and SSH channel termination when strict mode, `exit`, or a lost connection prevents a final prompt from appearing.
- **Long-running work**
  - Keeps normal command execution responsive while giving the `output` runtime longer polling windows for builds, installs, servers, tests, and training jobs.
- **Safety around running sessions**
  - Tracks whether a shell is currently busy and can prevent overlapping commands unless explicitly allowed.

## Key Files

- **Tool**
  - `tools/code_execution_tool.py` contains runtime dispatch, session lifecycle, and streaming output logic.
- **Helpers**
  - `helpers/shell_local.py` provides the local interactive shell implementation.
  - `helpers/shell_ssh.py` provides the SSH-backed interactive shell implementation.
- **Configuration**
  - `default_config.yaml` defines execution, prompt, and timeout settings.
- **Prompts**
  - `prompts/` contains the response templates shown to the agent.

## Configuration Scope

- **Settings section**: `agent`
- **Per-project config**: `true`
- **Per-agent config**: `true`
- **Always enabled**: `false`

## Plugin Metadata

- **Name**: `_code_execution`
- **Title**: `Code Execution`
- **Description**: Code execution tool supporting terminal, Python, and Node.js runtimes via local TTY or SSH.

## Durable jobs

With PostgreSQL durability, code execution uses detached, noninteractive POSIX jobs with stable identities. The submitted command is fingerprinted before launch. Recovery reads its receipt or shared encrypted result; a missing or unreachable receipt holds the run and never launches that command again. The existing interactive session path remains available when durability is off; SQLite durability requires the shared resource tier before code jobs can run.

- Terminal, Python (`ipython -c`) and Node.js (`node /exe/node_eval.js`) retain their existing command runtimes. `output` reads the session's last job; a wait timeout returns a running job ID. `reset` requests cancellation and clears known session state after completion, without undoing effects. An authoritative Stop can best-effort signal matching jobs; loss of a worker/session never counts as Stop, and already dispatched effects may still complete.
- Session snapshots preserve the working directory and exported environment delta. Managed-workspace paths in this state use logical workspace references and bind to the current materialization. Unmanaged absolute working directories or exported host paths hold after migration. The adapter does not rewrite raw commands; the shared tool boundary resolves declared workspace/resource references. PTY interaction, stdin continuation, aliases, functions and arbitrary shell-memory state require separate adapters.
- Local supervisors survive the framework worker and can append one encrypted shared result using a scoped job capability. An unfinished job still depends on its execution host; losing that host is uncertainty. Completed shared results remain readable from another worker. Command environments exclude the supervisor's `A0_DURABILITY_*` database, encryption and capability variables. This mechanism is not an operating-system sandbox.
- SSH jobs require Python 3, Bash and a trusted host key on the configured target. `durability_ssh_known_hosts` may specify the worker's known-hosts file; empty uses the system files. Unknown or changed keys fail closed. A reconnect fetches the existing remote job receipt and never resubmits its command. PostgreSQL credentials and job capabilities are not forwarded to the SSH target.

Every worker needs the same environment-only `A0_DURABILITY_RESOURCE_KEY` for private resource bytes. Local scratch receipts use owner-only directories under `usr/durability/execution` (override with `A0_DURABILITY_EXECUTION_ROOT`); set `A0_DURABILITY_EXECUTION_HOST_ID` only to a stable identity for that execution host. SSH scratch receipts use `~/.a0-durable-jobs`. Stop/reset jobs explicitly before removing scratch data; deleting a submitted receipt does not authorize replay. Disabling the plugin does not undo or silently terminate already submitted commands. Completed scratch directories may be removed after their shared result is verified; runtime secrets must not be included in exported backups or public artifacts.
