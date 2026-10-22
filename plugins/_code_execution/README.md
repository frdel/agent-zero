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

## Durable sessions

With PostgreSQL durability, the code and input tools use a detached persistent PTY broker. The live shell remains on its execution host while framework workers on other hosts enqueue commands through the shared database. Aliases, functions, shell variables, cwd, exported values and foreground stdin survive a framework worker being killed. Terminal, Python (`ipython -c`), Node.js (`node /exe/node_eval.js`), output and reset retain their normal runtimes. A timeout returns output and a running job ID; the input tool continues the same foreground program.

Each operation has an immutable identity and encrypted descriptor. A pinned database role admits a send once; a private daemon fsyncs its send intent before writing to the PTY. Known results are reused. If a relay, daemon or host disappears during delivery, recovery reads existing receipts and never blindly sends those bytes again. An authoritative Stop is best effort and cannot retract effects already dispatched. Reset stops a live session and starts clean shell state without undoing earlier effects.

After a daemon or execution host is lost at a known prompt, the adapter can restore captured declarations, aliases, functions, options, cwd and exported values. This requires a portable managed workspace and no unresolved foreground send, background jobs, traps, changed file descriptors, new readonly declarations or unsupported absolute host dependencies. A running broker preserves its real process state instead. Arbitrary process memory, file descriptors and external services are not reconstructed from shell text.

Managed project files travel with the session: changed input trees are staged into a fresh private execution directory and a settled portable shell is rebound there; output trees are captured into encrypted shared resources and imported before the framework commits its checkpoint. A successor therefore cannot publish its stale local workspace over the actual execution host's edits. A changing, unsafe or unsupported tree holds recovery while retaining the known command outcome. Output paths use logical workspace identities and are resolved in the receiving worker's current materialization.

SSH uses a detached daemon on the configured, host-key-verified target. A framework-host relay reconnects to its private queue and receipts, including after the first relay is killed. Database credentials, the shared encryption key, job capabilities and SSH passwords are never uploaded to that target. Managed input files and declared resource attachments are staged through SFTP; output files must be bounded regular files and pass the same workspace validation. SSH targets need Python 3, Bash, POSIX PTYs and a trusted host key. `durability_ssh_known_hosts` selects a worker-local known-hosts file; empty uses the system files. Unknown or changed keys fail closed.

Every framework worker needs the same environment-only `A0_DURABILITY_RESOURCE_KEY`. Local private queues and receipts live under `usr/durability/execution` (override with `A0_DURABILITY_EXECUTION_ROOT`); `A0_DURABILITY_EXECUTION_HOST_ID` must identify the actual execution host consistently. SSH queues use `~/.a0-durable-pty`. Stop sessions before removing their scratch directories; deleting uncertain receipts never authorizes replay. This is not an operating-system sandbox. Runtime credentials and private scratch state must not enter public artifacts.

The default `durability_interactive: true` enables this broker for new sessions. Existing batch identities remain readable through their original detached-job protocol; setting the option to false selects new batch jobs, which preserve only cwd and exported environment deltas. Durability off retains the original local/SSH session implementation. SQLite durability requires the shared resource tier for these execution adapters.
