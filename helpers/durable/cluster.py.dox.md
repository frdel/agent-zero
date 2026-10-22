# Distributed coordinator

`ClusterRecoveryService` executes PostgreSQL runs only after a pinned-session claim. Periodic scans discover remote admissions and controls; notifications are unnecessary for correctness. Session loss never reconnects or certifies an unknown effect. Existing continuation audits still hold uncertain phases and unaudited targets after migration.

`RunHandle` waits on immutable shared run identity, so a parent can join a child owned by another host. Child waits yield the worker's execution capacity; capacity is two executing runs per worker, not a deployment-wide limit. Read-only join timeouts do not cancel children.

Commands carry stable request IDs. Workers apply pause/intervention checkpoint changes and acknowledge atomically; review commands are revalidated on the claimed worker and return a fixed safe rejection receipt when stale or unsupported. Pause remains authoritative during subsequent snapshots. Stop/reset/delete fence database state immediately; scans cancel the local coroutine when that decision arrives.

Shared chat admission orders history by journal admission sequence rather than host timestamps. A saved genesis lets another host admit the first message; admission removes that obsolete projection. Current chat heads survive run retention, and reset-to-next-input admission checks its generation. Reconstruction requires a claim, verified resource materialization and source-audited constructor hooks. Managed workspaces redirect project reads only within the worker execution scope; attachments resolve from encrypted context resources. Unknown plugin state still holds. Distributed scheduler tasks use database projection CAS and a session role for due polling. The existing local backend retains its filesystem rules.

Verify with `tests/test_durable_cluster.py` against an explicitly disposable PostgreSQL DSN and the framework runtime; retain the process-kill and local recovery suites. No deployment DSN or live user state is required.
