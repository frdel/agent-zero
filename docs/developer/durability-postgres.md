# PostgreSQL workers

The `postgres` durability backend coordinates framework processes on separate
hosts through one database. Input identities, checkpoints, outcomes, typed
documents, recovery decisions, command receipts, scheduler projections, and large
JSON payloads share that authority. Workers do not need a shared SQLite volume or
another host's `chat.json` to resume compatible portable work.

This is an execution and recovery boundary. It does not turn a shell process,
workspace, browser, SSH connection, MCP session, or arbitrary plugin object into
portable state. Runs using local projects or attachments require a resource
adapter. Source/configuration drift and unresolved external effects still hold
for review. Plain inference and audited portable tools retain the existing
recovery rules.

## Deployment

Use a dedicated PostgreSQL database and a private schema namespace per deployment.
Workers sharing a namespace must run the same source and compatible model,
profile, extension, and policy configuration. Provider credentials are configured
on each eligible worker; they are never stored in recovery checkpoints. Configure
worker authentication, encrypted database transport, database storage encryption,
backups, and access privileges as deployment infrastructure.

Set the following before starting each worker:

```sh
export A0_SET_DURABILITY_BACKEND=postgres
export A0_DURABILITY_POSTGRES_NAMESPACE=agent_zero
export A0_DURABILITY_POSTGRES_DSN='host=db.example dbname=agent_zero user=agent_zero sslmode=verify-full sslrootcert=/run/secrets/pg-ca.crt passfile=/run/secrets/pgpass'
python run_ui.py
```

Keep the password file private and use your platform's secret mount. The DSN is
an environment-only configuration value, never a returned settings field. Saved
`durability_backend` values take precedence over defaults; update an existing saved
value and restart. The declared `psycopg[binary]` dependency also has a framework
startup migration for self-updated instances.

The store requires server `fsync` and `full_page_writes`, and forces synchronous
commit for its session. For automatic database-primary failover, configure a
single writer and synchronous replication consistent with your recovery-point
requirements; switching to a stale replica can lose acknowledged intent records
and is a database restore event requiring review, not safe worker takeover.

Use direct PostgreSQL connections or a pooler in **session** mode. Transaction
pooling cannot preserve a worker's session ownership. A worker does not silently
reconnect a lost database session under its old claims. Restart that worker after
restoring connectivity. Session lock lifetime follows the [PostgreSQL locking contract](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS). Database failures hold execution rather than enabling the
legacy path.

An existing local SQLite ledger is not silently abandoned when changing backends.
Use a fresh deployment root for a new PostgreSQL deployment. Migrating existing
local recovery data requires an explicit offline migration; changing a setting is
not a data migration. Likewise, disabling the backend while its DSN remains
configured opens shared state with execution disabled, preserving held work.
Remove database configuration only after stopping all shared work; an older
framework cannot enforce this rollback boundary.

## Ownership and recovery

Each run has one pinned PostgreSQL session claim and an increasing fence token.
A live claimant excludes competing workers. Claim loss prevents the old worker
from starting calls or advancing outcomes/checkpoints. PostgreSQL session locks
are released when their session ends; elapsed wall-clock time is never permission
to repeat an effect. The database must detect a disconnected session before a
successor can claim its runs.

Periodic scans claim and audit constructor hooks before constructing a live context, so another process does
not overwrite its local registry with a remote worker's context. A successor reads
the shared checkpoint, verifies portability and source/configuration, then resumes
a supported phase or records a hold. Losing ownership cannot retract an HTTP
request already sent: an unresolved tool/provider intent remains uncertain and
requires the existing review/reconciliation policy. Exactly-once external effects
still require target-side idempotency.

Short ledger mutations serialize through a database transaction advisory lock.
Provider and tool calls execute outside that transaction. PostgreSQL owns shared timestamps and retention cutoffs; journal admission sequences determine conversation order even when worker clocks differ. This preserves the
existing admission, generation, document CAS, review version, and retention
invariants across writers. Large values use verified database bytes in the same
transaction as their references; no worker-local blob directory is authoritative.
One verified current checkpoint per chat is retained independently of old run payloads, so terminal journal retention cannot erase the conversation required for its next turn. Deletion scrubs this checkpoint too. Execution has two slots **per worker**. This is not a deployment-wide provider
rate or concurrency limit.

## Core integration rationale

| Boundary | Why shared execution changes it |
| --- | --- |
| Recovery service factory and runner saves | Backend selection must happen before startup restoration or admission. A claimant must be established before reconstructing a context, and an acknowledged command must survive the next worker snapshot. These checks cannot be supplied by a post-dispatch hook. |
| Shared API context lookup and message/pause/reset handlers | A requester host's in-memory registry cannot prove ownership. Existing chat messages route to shared admission or the owner inbox before requester-side hooks/logging; new chats retain first-Send creation. Mutation paths refuse stale shadows. |
| Chat persistence | A host's `chat.json` cannot overwrite shared history, configuration or deletion policy. Shared projections require claim ownership and revision CAS; recovery constructs contexts from the ledger. Local files remain compatibility projections. |
| Scheduler persistence and framework job loop | Independent task files and pollers can launch duplicate work. Shared definitions/projections need CAS; pinned roles elect due-task and integration pollers, and occurrence claims arbitrate execution. |
| Dependency declarations and startup migration | New images and self-updated instances both need the PostgreSQL driver and its binary extra. Backend import stays lazy; an unavailable driver holds PostgreSQL mode without changing the local/off execution path. |

The PostgreSQL adapter reuses strict JSON, generation, review, document, retry and
retention business rules instead of maintaining a second execution engine. Its SQL
translation is limited to the repository's static store statements; native
PostgreSQL schema, transaction, blob and ownership semantics remain explicit.

## Commands, children, and scheduler

Remote input/control/review commands commit before acknowledgment. UI input preparation runs only on the claimed worker, with its own intent/result and source fingerprint; an uncertain preparation hook is held rather than repeated. UI interventions into a live remote turn require an input-preparation adapter and are rejected explicitly until one is available; plain programmatic interventions retain the durable inbox path. Stable request
IDs deduplicate delivery; the owner applies commands under its snapshot lock and
records a separate receipt. A queued decision is not an applied decision. The
Recovery modal's explicit **Refresh** checks pending/applied/rejected receipts.
The worker revalidates the original review version and current policy; queueing
never upgrades a stale authorization. Pause prevents new effect dispatch after
application; an already-sent request can still finish. Reset requests retain stable client IDs and atomically recorded receipts; retrying a lost acknowledgment cannot reset a newer run. Reset clears the next admission's history under a generation check. Stop/reset generation fences
apply in shared storage even when the requesting host has no local task to kill.

Child joins await shared run identities rather than requiring the originating
process's `DeferredTask`. Known child results can be collected from another host.
Waiting parents yield their local execution slot. Timeouts leave background work
alive and are recorded separately from successful collection.

Built-in scheduler definitions and occurrence projections use a versioned database
projection. A session role elects the scheduler poller; failover reads shared task
state. Per-run claims still arbitrate actual execution. Concurrent scheduler edits
must pass projection CAS. A separate pinned `job-loop` role excludes simultaneous integration pollers while their database sessions are healthy. Plugin polling effects, delivery cursors and in-flight disconnect reconciliation still require each integration's adapter; they are not journaled workflow outcomes. Local JSON/YAML task files remain authoritative only for
the local/off backends; they are not replicated scheduler storage.

Normal chat snapshots read committed logs and task metadata from shared storage on
any host without creating an executable context. A shared revision watermark
invalidates local WebSocket projections after another worker commits. Updates to
existing log items retain their cursor contract; a new run/reset changes the
projection generation. Cross-host views show saved progress, not replicated
provisional streaming tokens. Host-local notifications remain local.

The API refuses operations that would mutate a stale remote `AgentContext`.
Shared recovery status and registered documents can be read from committed masked
state. Editing a document requires the owning masking/policy context; a remote
edit is held rather than storing unmasked content. Remote chat/provider deletion
also holds when the credential-capable owner and deletion opt-out cannot be
verified. A successful local shadow reset must never be reported as deletion of a
remote provider response.

## Backup and restore

Use PostgreSQL's consistent native backup tools with database-owned retention and
custody. The SQLite `LocalStore.backup()` file API is not a PostgreSQL backup API.
SQL deletion does not erase independent backups, WAL archives, or replicas.

Stop every worker before restoring a database. After restoring, rotate its
recovery deployment epoch and require explicit selection of restored runs before
starting workers:

```python
import os
from helpers.durable.postgres import PostgresStore

with PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"],
                   namespace=os.environ.get("A0_DURABILITY_POSTGRES_NAMESPACE", "agent_zero")) as store:
    store.begin_restore_review()
```

This maintenance operation refuses live worker claims or roles. Then use explicit
per-run restore selection in Recovery & documents. Never attach workers to an old snapshot as though it were the
current live database: previously sent external effects may have no outcome in
that snapshot. Retry grants and prior restore selections cannot authorize replay
in the new deployment epoch. Workspace/configuration/credentials have their own
backup and consistency requirements.

## Verification

Use a disposable PostgreSQL database and the framework Python environment. The
integration tests run only when an explicit test DSN is present; they never fall
back to the deployment DSN:

```sh
export A0_TEST_DURABILITY_POSTGRES_DSN='host=127.0.0.1 port=5432 dbname=a0_test user=a0_test'
python -m pytest tests/test_durable_postgres.py tests/test_durable_cluster.py tests/test_durable_cluster_api.py tests/test_durable_postgres_process.py -q
node --test tests/test_durability_ui.mjs
```

The process tests kill actual framework workers at committed model/tool
boundaries, exclude a competing live claimant, and recover in a fresh process
with an independent empty chat directory. They check known-result reuse and
uncertainty holds with synthetic providers. Database session termination tests
check stale-writer fencing. These tests establish process isolation and shared
custody locally; they are not a live multi-region deployment or network-partition
acceptance test.
