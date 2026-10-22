# Code Execution Plugin DOX

## Purpose

- Own terminal, Python, and Node.js code execution through persistent local or SSH-backed sessions.

## Ownership

- `tools/` owns the code execution and input tools.
- `helpers/` owns local shell, SSH shell, and TTY session management. `durable_pty.py` is the standalone, database-free PTY receipt daemon copied to pinned SSH targets.
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
- PostgreSQL durability routes the audited code/input tools through `helpers/durable/execution.py` and `interactive.py`. A detached relay holds a pinned database role, reads an owner-published encrypted queue and consumes one-use job grants before sending. The PTY daemon fsyncs intent before bytes and results before acknowledgments; neither layer resends an unknown operation. Framework worker loss preserves live shell/stdin/aliases/functions. An SSH relay keeps database credentials and capabilities on the framework host, and uses only host-key-pinned, private remote receipts.
- Settled prompt snapshots capture cwd, changed declarations/exported values, aliases, functions and shell options. Restoring after execution-process/host loss requires known terminal receipts, a portable managed cwd, unchanged descriptor/readonly state, and no jobs/traps or unsupported host paths. Unknown foreground work holds. A live anchored PTY can continue through framework-host changes without reconstructing its memory.
- Framing and restore commands cannot be user-overridden in portable snapshots. Aliases/functions for `builtin`, `command`, `set`, `shopt`, `declare`, `alias`, `cd`, `unset`, `source` and framing file commands, or changed/unset `PROMPT_COMMAND`, make a snapshot nonportable. Revalidate the declarations before spawning a restored shell, independently of the stored portable flag; reconstruction must never execute those prior effects again.
- Managed project digests cross the relay in both directions: stage verified encrypted files privately before a changed-input command, rebind a settled portable prompt, and publish a coherent output tree before the workflow checkpoint. SSH export rejects links/special files and verifies both metadata and bytes. Never checkpoint a successor's stale local copy over the execution host's edits. Inconsistent/unsafe trees hold while retaining the known command result.
- Authoritative Stop signalling is best effort and distinct from worker/claim loss; a reset can stop the live session without undoing prior effects. Existing batch journals remain on their original protocol; `durability_interactive: false` explicitly selects new batch jobs. Local/off legacy sessions retain their existing behavior.
- The tool's `allow_running` flag is framework-set (for example by the `input` tool's terminal dispatch); it is not a model-facing arg and stays undocumented in prompts.
- Do not hardcode secrets, SSH credentials, or local user paths.

## Work Guidance

- Preserve long-running command output retrieval and busy-session guards when changing execution flow.

## Verification

- Smoke-test terminal, Python, Node.js, output polling, and reset paths after tool changes.
- `tests/test_durable_execution.py` uses a disposable PostgreSQL database, real worker/relay/PTY termination and pinned loopback SSH. Verify stdin exactly once, shell declaration restoration, managed file handoff and unknown-send holds; retain legacy shell I/O checks.

## Child DOX Index

No child DOX files.
