# Code Execution Plugin DOX

## Purpose

- Own terminal, Python, and Node.js code execution through persistent local or SSH-backed sessions.

## Ownership

- `tools/` owns the code execution and input tools.
- `helpers/` owns local shell, SSH shell, and TTY session management.
- `prompts/` owns execution prompt and runtime response fragments.
- `default_config.yaml`, `plugin.yaml`, `extensions/`, and `webui/` own settings, metadata, hooks, and UI config.

## Local Contracts

- `extensions/webui/get_process_step_types/code-exe-types.js` registers `code_exe` as a process-step type so raw-log grouping matches the plugin's message renderer.

- Keep session concurrency, timeout, streaming, and reset behavior predictable.
- A direct parallel code job retains its worker and loop-bound shell until the command ends or is cancelled. Output timeouts publish model-facing progress to the registered job and continue polling; callers use parallel job IDs. Close parallel shells explicitly on that worker loop on completion or cancellation, including partially connected shells. Top-level sessions retain their ordinary timeout/output/reset behavior.
- Execute multi-line terminal input as one current-shell compound so intermediate prompts cannot mark queued work complete; preserve `cd`, exports, and other shell state.
- Treat local process exit and SSH channel termination as definitive command completion even when no final prompt is emitted; recreate terminated sessions before their next command.
- Terminal reset/close must not hang on foreground commands or shells that ignore SIGTERM.
- POSIX PTY I/O is nonblocking. The existing write/drain interface buffers partial writes and yields while the terminal is full; cancellation discards the shell only while POSIX input bytes remain unsent. Fully drained sends retain the shell and its state.
- SSH command writes must send every byte without blocking the event loop. Cancelling an in-flight SSH send closes its connection so a partial command cannot contaminate subsequent input.
- TTY destruction uses best-effort kill, never nested event-loop execution; explicit close retains awaited cleanup.
- Windows cleanup uses the native process methods without looking up POSIX-only signals; the pywinpty adapter passes SIGTERM for forced termination. POSIX close retains process-group TERM-then-KILL escalation.
- Local and SSH session wrappers must synchronously release their owned process or connection resources when discarded.
- Explicitly target local versus SSH execution runtimes.
- The `input` tool logs a prefix-free `icon://keyboard Using tool 'input'` heading and forwards keyboard input through the code execution tool and its log.
- The tool's `allow_running` flag is framework-set (for example by the `input` tool's terminal dispatch); it is not a model-facing arg and stays undocumented in prompts.
- Do not hardcode secrets, SSH credentials, or local user paths.

## Work Guidance

- Preserve long-running command output retrieval and busy-session guards when changing execution flow.

## Verification

- Smoke-test terminal, Python, Node.js, output polling, and reset paths after tool changes.

## Child DOX Index

No child DOX files.
