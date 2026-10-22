# Durable interactive execution

`reconcile(tool, args)` admits a stable code/input/output/reset request through
claim-fenced resource manifests and one-use PostgreSQL job capabilities.
`can_resume` permits committed descriptors or proven absence of any dispatch
grant; it never grants a second delivery for a running job. `cancel_sessions`
wakes matching current-generation sessions only after authoritative Stop.

The detached relay owns a pinned database role, not a workflow claim. Before
touching a terminal it consumes `begin_resource_job`. Its private PTY daemon
fsyncs a local send intent and immutable result. Relay/worker replacement reads
those receipts; missing evidence for a running delivery blocks later sends and
reads that could otherwise mistake a new empty shell for completion. Read-only
output snapshots have separate identities and never settle the foreground job.

Encrypted descriptors carry resolved input and scoped append-only capabilities.
SSH targets receive neither database credentials/key nor job capabilities: a
framework-side relay stages private files and uses host-key-pinned SFTP/SSH to
the standalone `plugins/_code_execution/helpers/durable_pty.py` daemon.
The daemon keeps the live PTY, stdin, aliases, functions and variables across
framework-worker loss. Prompt snapshots permit reconstruction only when known
receipts and captured state prove it safe; jobs, traps, changed descriptors,
readonly declarations or external host paths prevent unsupported migration.

Managed input trees are restored to fresh private execution directories under a
running job capability. Rebinding requires a settled portable prompt. Results
and previews include a coherent encrypted workspace capture; the claimed
workflow imports it before its checkpoint. SSH export rejects links/special
files and verifies metadata plus two content reads within existing workspace
bounds. Unsafe capture preserves the known command result and holds
reconciliation. Stdout/state canonicalize the actual execution workspace and
declared resource paths before crossing hosts.

Private scratch is under `A0_DURABILITY_EXECUTION_ROOT` or
`usr/durability/execution`; remote scratch is `~/.a0-durable-pty`. This mechanism
does not sandbox authorized shell code. Do not remove uncertain receipts or
interpret process/claim loss as cancellation. Verify with the disposable-PG
behavior tests in `tests/test_durable_execution.py`, including actual process
termination, stdin, file handoff and SSH receipt loss, plus legacy shell tests.
