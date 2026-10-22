# Durable execution policy and batch compatibility

`supports` accepts source/code-identical bundled code and input implementations,
including the core dynamic tool loader, with bounded typed args. Subclasses,
instance overrides and unsupported modes receive no recovery permission.
`can_resume` and `reconcile` select the persistent interactive adapter by default
while keeping existing batch identities on their original protocol.

The compatibility batch path launches detached POSIX supervisors or pinned SSH
receipt jobs. Submission identity is committed before spawn; absence of a known
receipt never authorizes relaunch. Local append-only job capabilities can commit
encrypted output after framework death. Batch restoration preserves cwd/export
deltas only; callers needing stdin/functions use the default interactive tier.

`cancel_sessions` checks authoritative cancelled status and current generation,
then signals only matching jobs. Worker disappearance, changed ownership, reset
and later generations do not acquire Stop authority. Already dispatched effects
can finish; cancellation acknowledgments are not fabricated terminal results.

See `interactive.py.dox.md` for the shared queue/PTY, managed file and SSH relay
contracts. Verify `tests/test_durable_execution.py`, `test_code_execution_pager.py`
and `test_shell_ssh_io.py` in the framework runtime with an explicitly disposable
PostgreSQL DSN for shared tests.
